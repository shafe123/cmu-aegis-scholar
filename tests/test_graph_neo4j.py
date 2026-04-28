"""
Service-layer integration tests for graph-db API against a live Neo4j container.

These tests spin up both our graph-db service container and a Neo4j container,
then validate that our API correctly stores and retrieves graph data.
"""

import pytest
import httpx

# ---------------------------------------------------------------------------
# Fixtures  
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def graph_api_url(graph_db_url):
    """Return the base URL for the graph-db service container from conftest."""
    return graph_db_url


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.requires_docker
def test_graph_db_service_is_healthy(graph_api_url):
    """Our graph-db service should report healthy when Neo4j is available."""
    response = httpx.get(f"{graph_api_url}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["neo4j"] == "connected"


@pytest.mark.integration
@pytest.mark.requires_docker
def test_upsert_author_via_api(graph_api_url, sample_authors):
    """POST /authors should create an Author node via our service."""
    author = sample_authors[0]
    payload = {
        "id": author["id"],
        "name": author["name"],
        "h_index": author.get("h_index", 0),
        "works_count": author.get("works_count", 0),
    }
    response = httpx.post(f"{graph_api_url}/authors", json=payload)
    assert response.status_code == 200
    assert response.json()["id"] == author["id"]


@pytest.mark.integration
@pytest.mark.requires_docker
def test_upsert_work_via_api(graph_api_url, sample_works):
    """POST /works should create a Work node via our service."""
    work = sample_works[0]
    payload = {
        "id": work["id"],
        "title": work["title"],
        "year": work.get("publication_date", "2024-01-01")[:4],
        "citation_count": work.get("citation_count", 0),
    }
    response = httpx.post(f"{graph_api_url}/works", json=payload)
    assert response.status_code == 200
    assert response.json()["id"] == work["id"]


@pytest.mark.integration
@pytest.mark.requires_docker
def test_link_author_work_via_api(graph_api_url, sample_authors, sample_works):
    """POST /relationships/authored should link Author to Work."""
    author = sample_authors[0]
    work = sample_works[0]

    # Ensure both exist first
    httpx.post(f"{graph_api_url}/authors", json={
        "id": author["id"], "name": author["name"],
        "h_index": 0, "works_count": 0,
    })
    httpx.post(f"{graph_api_url}/works", json={
        "id": work["id"], "title": work["title"],
        "year": "2024", "citation_count": 0,
    })

    response = httpx.post(f"{graph_api_url}/relationships/authored", json={
        "author_id": author["id"],
        "work_id": work["id"],
    })
    assert response.status_code == 200
    assert response.json()["status"] == "linked"


@pytest.mark.integration
@pytest.mark.requires_docker
def test_collaborator_discovery_via_api(graph_api_url, sample_authors, sample_works):
    """GET /authors/{id}/collaborators should return co-authors via our service."""
    author1 = sample_authors[0]
    author2 = sample_authors[1]
    work = sample_works[0]

    # Ingest both authors and a shared work
    for author in [author1, author2]:
        httpx.post(f"{graph_api_url}/authors", json={
            "id": author["id"], "name": author["name"],
            "h_index": 0, "works_count": 0,
        })
    httpx.post(f"{graph_api_url}/works", json={
        "id": work["id"], "title": work["title"],
        "year": "2024", "citation_count": 0,
    })
    httpx.post(f"{graph_api_url}/relationships/authored", json={
        "author_id": author1["id"], "work_id": work["id"],
    })
    httpx.post(f"{graph_api_url}/relationships/authored", json={
        "author_id": author2["id"], "work_id": work["id"],
    })

    response = httpx.get(f"{graph_api_url}/authors/{author1['id']}/collaborators")
    assert response.status_code == 200
    collaborators = response.json()
    collab_ids = [c["id"] for c in collaborators]
    assert author2["id"] in collab_ids


@pytest.mark.integration
@pytest.mark.requires_docker
def test_viz_network_via_api(graph_api_url, sample_authors, sample_works):
    """GET /viz/author-network/{id} should return nodes and edges."""
    author = sample_authors[0]
    work = sample_works[0]

    httpx.post(f"{graph_api_url}/authors", json={
        "id": author["id"], "name": author["name"],
        "h_index": 0, "works_count": 0,
    })
    httpx.post(f"{graph_api_url}/works", json={
        "id": work["id"], "title": work["title"],
        "year": "2024", "citation_count": 0,
    })
    httpx.post(f"{graph_api_url}/relationships/authored", json={
        "author_id": author["id"], "work_id": work["id"],
    })

    response = httpx.get(f"{graph_api_url}/viz/author-network/{author['id']}")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data
    node_ids = [n["id"] for n in data["nodes"]]
    assert author["id"] in node_ids