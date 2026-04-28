"""
Service-layer integration tests for vector-db API against a live Milvus container.

These tests spin up both our vector-db service container and a Milvus container,
then validate that our API correctly stores and retrieves vector embeddings.

Uses actual data from dtic_test_subset for realistic testing.
"""

import pytest
import httpx
from conftest import load_test_author, load_test_work

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.requires_docker
def test_vector_db_service_is_healthy(vector_db_url):
    """Our vector-db service should report healthy when Milvus is available."""
    response = httpx.get(f"{vector_db_url}/health", timeout=30)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["milvus_connected"] is True


@pytest.mark.integration
@pytest.mark.requires_docker
def test_default_collection_created(vector_db_url):
    """The default aegis_vectors collection should be created on startup."""
    response = httpx.get(f"{vector_db_url}/collections", timeout=30)
    assert response.status_code == 200
    collections = response.json()
    names = [c["name"] for c in collections]
    assert "aegis_vectors" in names


@pytest.mark.integration
@pytest.mark.requires_docker
def test_create_author_embedding_via_api(vector_db_url):
    """POST /authors/embeddings should create an embedding from abstracts."""
    author = load_test_author(0)
    work = load_test_work(0)
    
    # Use the actual abstract from the work
    abstracts = [work.get("abstract", "")] if work.get("abstract") else [
        "Research in advanced materials and systems."
    ]

    payload = {
        "author_id": author["id"],
        "author_name": author["name"],
        "abstracts": abstracts,
        "citation_count": author.get("citation_count", 0),
    }
    response = httpx.post(
        f"{vector_db_url}/authors/embeddings",
        json=payload,
        timeout=60,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["author_id"] == author["id"]
    assert data["embedding_dim"] == 384


@pytest.mark.integration
@pytest.mark.requires_docker
def test_text_search_returns_results(vector_db_url):
    """POST /search/text should return ranked results after embeddings are loaded."""
    import time
    author = load_test_author(0)
    work = load_test_work(0)
    
    # Use the actual abstract or a default
    abstract = work.get("abstract", "Research in carbon dioxide adsorption on ice.")
    abstracts = [abstract]

    response = httpx.post(
        f"{vector_db_url}/authors/embeddings",
        json={
            "author_id": author["id"],
            "author_name": author["name"],
            "abstracts": abstracts,
        },
        timeout=60,
    )
    assert response.status_code == 200

    # Give Milvus a moment to index the newly inserted embedding
    time.sleep(3)

    # Search for keywords from the abstract
    response = httpx.post(
        f"{vector_db_url}/search/text",
        json={"query_text": "carbon dioxide ice adsorption", "limit": 5},
        timeout=30,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) > 0
    assert data["results"][0]["author_id"] == author["id"]


@pytest.mark.integration
@pytest.mark.requires_docker
def test_models_endpoint(vector_db_url):
    """GET /models should return available embedding models."""
    response = httpx.get(f"{vector_db_url}/models", timeout=30)
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert len(data["models"]) > 0
    assert "default_model" in data