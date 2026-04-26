"""
Service-layer integration tests for vector-db API against a live Milvus container.

These tests spin up both our vector-db service container and a Milvus container,
then validate that our API correctly stores and retrieves vector embeddings.
"""

import pytest
import httpx
import docker
from testcontainers.milvus import MilvusContainer
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs

# ---------------------------------------------------------------------------
# Container configuration
# ---------------------------------------------------------------------------

MILVUS_IMAGE = "milvusdb/milvus:v2.4.4"
VECTOR_DB_IMAGE = "aegis-vector-db-test:latest"
VECTOR_DB_PORT = 8002
NETWORK_NAME = "aegis-vector-test-net"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def docker_network():
    """Create a shared Docker network for container-to-container communication."""
    client = docker.from_env()
    network = client.networks.create(NETWORK_NAME, driver="bridge")
    yield network
    network.remove()


@pytest.fixture(scope="module")
def milvus_container(docker_network):
    """Start a real Milvus container on the shared test network."""
    container = MilvusContainer(image=MILVUS_IMAGE)
    container.with_kwargs(network=NETWORK_NAME, hostname="milvus-standalone")
    with container:
        yield container


@pytest.fixture(scope="module")
def vector_db_container(milvus_container, docker_network):
    """
    Start our vector-db service container pointed at the Milvus test container.
    Mounts a model cache to avoid re-downloading the embedding model each run.
    """
    import os
    model_cache = os.path.expanduser("~/.cache/aegis-model-cache")
    os.makedirs(model_cache, exist_ok=True)

    container = (
        DockerContainer(image=VECTOR_DB_IMAGE)
        .with_exposed_ports(VECTOR_DB_PORT)
        .with_env("MILVUS_HOST", "milvus-standalone")
        .with_env("MILVUS_PORT", "19530")
        .with_env("DEFAULT_COLLECTION", "aegis_vectors")
        .with_volume_mapping(model_cache, "/app/.cache", "rw")
        .with_kwargs(network=NETWORK_NAME)
    )
    with container:
        wait_for_logs(container, "Application startup complete.", timeout=180)
        yield container


@pytest.fixture(scope="module")
def vector_api_url(vector_db_container):
    """Return the base URL for the vector-db service container."""
    host = vector_db_container.get_container_host_ip()
    port = vector_db_container.get_exposed_port(VECTOR_DB_PORT)
    return f"http://{host}:{port}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.requires_docker
def test_vector_db_service_is_healthy(vector_api_url):
    """Our vector-db service should report healthy when Milvus is available."""
    response = httpx.get(f"{vector_api_url}/health", timeout=30)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["milvus_connected"] is True


@pytest.mark.integration
@pytest.mark.requires_docker
def test_default_collection_created(vector_api_url):
    """The default aegis_vectors collection should be created on startup."""
    response = httpx.get(f"{vector_api_url}/collections", timeout=30)
    assert response.status_code == 200
    collections = response.json()
    names = [c["name"] for c in collections]
    assert "aegis_vectors" in names


@pytest.mark.integration
@pytest.mark.requires_docker
def test_create_author_embedding_via_api(vector_api_url, sample_authors, sample_works):
    """POST /authors/embeddings should create an embedding from abstracts."""
    author = sample_authors[0]
    works_for_author = [
        w for w in sample_works
        if any(a["author_id"] == author["id"] for a in w.get("authors", []))
    ]
    abstracts = [w["abstract"] for w in works_for_author if w.get("abstract")]

    if not abstracts:
        abstracts = ["Defense research in advanced materials and systems."]

    payload = {
        "author_id": author["id"],
        "author_name": author["name"],
        "abstracts": abstracts,
        "citation_count": author.get("citation_count", 0),
    }
    response = httpx.post(
        f"{vector_api_url}/authors/embeddings",
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
def test_text_search_returns_results(vector_api_url, sample_authors, sample_works):
    """POST /search/text should return ranked results after embeddings are loaded."""
    import time
    author = sample_authors[0]
    abstracts = ["Defense research in advanced materials and hypersonic systems."]

    response = httpx.post(
        f"{vector_api_url}/authors/embeddings",
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

    response = httpx.post(
        f"{vector_api_url}/search/text",
        json={"query_text": "defense materials research", "limit": 5},
        timeout=30,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) > 0
    assert data["results"][0]["author_id"] == author["id"]


@pytest.mark.integration
@pytest.mark.requires_docker
def test_models_endpoint(vector_api_url):
    """GET /models should return available embedding models."""
    response = httpx.get(f"{vector_api_url}/models", timeout=30)
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert len(data["models"]) > 0
    assert "default_model" in data