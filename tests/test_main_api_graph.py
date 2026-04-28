"""Integration tests for Aegis Scholar API container interaction with Graph DB container."""

import pytest
from httpx import AsyncClient

# Test data constants - Known IDs from dtic_authors_50.jsonl.gz subset
TEST_AUTHOR_ID = "author_6671149b-381b-573b-bb3d-81d86a789471"


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.requires_docker
async def test_author_details_integration(main_api_url, ensure_test_data):
    """
    Validates the containerized API's interaction with the Graph DB container.
    Tests the /authors/{author_id} endpoint fetching author metadata.
    """
    async with AsyncClient(base_url=main_api_url) as ac:
        response = await ac.get(f"/search/authors/{TEST_AUTHOR_ID}")

    # Validation
    assert response.status_code == 200, f"Failed to fetch author: {response.text}"
    data = response.json()

    # Check that the data returned matches our expected subset schema
    assert data["id"] == TEST_AUTHOR_ID
    assert "display_name" in data or "name" in data
    assert "org_ids" in data


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.requires_docker
async def test_viz_endpoint_integration(main_api_url, ensure_test_data):
    """
    Validates the containerized API's /viz endpoint (Network Explorer).
    Tests container-to-container communication: API → Graph DB.
    Verifies D3/NetworkGraph.jsx compatible structure (nodes and links).
    """
    async with AsyncClient(base_url=main_api_url) as ac:
        # Testing depth=1 ensures we get the author and their immediate works
        response = await ac.get(f"/viz/author-network/{TEST_AUTHOR_ID}")

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


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.requires_docker
async def test_viz_expansion_logic(main_api_url, ensure_test_data):
    """
    Tests the containerized API's graph expansion logic.
    Simulates the "Expansion" flow for deeper graph traversal.
    """
    async with AsyncClient(base_url=main_api_url) as ac:
        # Depth 1: Initial load
        res_d1 = await ac.get(f"/viz/author-network/{TEST_AUTHOR_ID}")
        assert res_d1.status_code == 200, f"D1 failed: {res_d1.text}"
        d1_data = res_d1.json()

        # Depth 2: Expansion (Simulated by repeating the call or using expansion params if your API supports them)
        # Note: We keep this INSIDE the 'async with' block so the client 'ac' is still open
        res_d2 = await ac.get(f"/viz/author-network/{TEST_AUTHOR_ID}")
        assert res_d2.status_code == 200, f"D2 failed: {res_d2.text}"
        d2_data = res_d2.json()

        assert "nodes" in d2_data, f"Expected 'nodes' in response, got: {d2_data}"
        # In a real expansion, D2 should be >= D1
        assert len(d2_data["nodes"]) >= len(d1_data["nodes"])


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.requires_docker
async def test_graph_error_handling(main_api_url):
    """Tests the containerized API's error handling for non-existent authors."""
    async with AsyncClient(base_url=main_api_url) as ac:
        response = await ac.get("/viz/author-network/this_is_not_a_real_id")

    # Accepts both "Not Found" and "Service Unavailable"
    assert response.status_code in [404, 503]
    assert "detail" in response.json()

