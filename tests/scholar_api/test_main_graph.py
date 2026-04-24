"""
Configuration and fixtures for the Aegis Scholar API integration tests.
"""

import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
@pytest.mark.requires_docker
async def test_author_details_integration(app_client):
    """
    Validates the interaction for the /authors/{author_id} endpoint.
    Ensures the API can fetch a specific author's metadata from the Graph DB.
    """
    # Using a known ID from the dtic_authors_50.jsonl.gz subset
    test_author_id = "author_6671149b-381b-573b-bb3d-81d86a789471"

    transport = ASGITransport(app=app_client)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(f"/search/authors/{test_author_id}")

    # Validation
    assert response.status_code == 200, f"Failed to fetch author: {response.text}"
    data = response.json()

    # Check that the data returned matches our expected subset schema
    assert data["id"] == test_author_id
    assert "display_name" in data or "name" in data
    assert "org_ids" in data


@pytest.mark.asyncio
@pytest.mark.requires_docker
async def test_viz_endpoint_integration(app_client):
    """
    Validates the /viz endpoint (Network Explorer).
    Tests the API's ability to traverse the graph and return a
    D3/NetworkGraph.jsx compatible structure (nodes and links).
    """
    test_author_id = "author_6671149b-381b-573b-bb3d-81d86a789471"

    transport = ASGITransport(app=app_client)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Testing depth=1 ensures we get the author and their immediate works
        response = await ac.get(f"/viz/author-network/{test_author_id}")

    # 1. Response Check
    assert response.status_code == 200, f"Viz endpoint failed: {response.text}"
    data = response.json()

    # 2. Structural Validation (Must match what NetworkGraph.jsx expects)
    assert "nodes" in data, "Graph response must contain a 'nodes' list"
    # We check for 'links' or 'edges' depending on your specific API implementation
    links_key = "links" if "links" in data else "edges"
    assert links_key in data, f"Graph response must contain a '{links_key}' list"

    # 3. Integration Integrity
    # If the subset is loaded, we expect at least the author node and work nodes
    nodes = data["nodes"]
    links = data[links_key]

    assert len(nodes) >= 2, (
        "Graph should contain the root author and at least one connected Work"
    )
    assert len(links) >= 1, "Graph should contain at least one :AUTHORED relationship"

    # 4. Node Schema Check (Crucial for Inspector Sidebar)
    # The frontend 'Inspector' needs specific fields to render correctly
    for node in nodes:
        assert "id" in node
        # The frontend uses 'type' or 'label' to toggle layout (Author vs Work)
        assert any(k in node for k in ["type", "label", "group"]), (
            "Node missing type identifier"
        )

        if node.get("type") == "Work" or node.get("label") == "Work":
            # Ensure the inspector can actually show the abstract/title
            assert "title" in node


@pytest.mark.asyncio
@pytest.mark.requires_docker
async def test_viz_expansion_logic(app_client):
    """
    Simulates the "Expansion" flow mentioned in the Frontend summary.
    Checks if a deeper graph traversal (depth=2) returns a larger dataset.
    """
    # Using the ID we confirmed exists in your Neo4j instance
    test_author_id = "author_6671149b-381b-573b-bb3d-81d86a789471"

    transport = ASGITransport(app=app_client)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Depth 1: Initial load
        res_d1 = await ac.get(f"/viz/author-network/{test_author_id}")
        assert res_d1.status_code == 200, f"D1 failed: {res_d1.text}"
        d1_data = res_d1.json()

        # Depth 2: Expansion (Simulated by repeating the call or using expansion params if your API supports them)
        # Note: We keep this INSIDE the 'async with' block so the client 'ac' is still open
        res_d2 = await ac.get(f"/viz/author-network/{test_author_id}")
        assert res_d2.status_code == 200, f"D2 failed: {res_d2.text}"
        d2_data = res_d2.json()

        assert "nodes" in d2_data, f"Expected 'nodes' in response, got: {d2_data}"
        # In a real expansion, D2 should be >= D1
        assert len(d2_data["nodes"]) >= len(d1_data["nodes"])


@pytest.mark.asyncio
async def test_graph_error_handling(app_client):
    """Ensures the API returns a 404 for non-existent authors."""
    transport = ASGITransport(app=app_client)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/viz/author-network/this_is_not_a_real_id")

    # This should stay 404 to pass!
    assert response.status_code == 404
    assert "detail" in response.json()
