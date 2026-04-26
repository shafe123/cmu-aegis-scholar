"""Integration test configuration and shared fixtures."""

import os
import time
import logging
import warnings
import subprocess
import pytest
import httpx
from testcontainers.core.container import DockerContainer

# Suppress third-party deprecation warnings
logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)
logging.getLogger("pyasn1.codec.ber.encoder").setLevel(logging.ERROR)

# Suppress pyasn1 deprecation warnings from ldap3
warnings.filterwarnings(
    "ignore",
    message="tagMap is deprecated",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    message="typeMap is deprecated",
    category=DeprecationWarning,
)

# --- Test Environment Configuration ---
# These values can be overridden via environment variables
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j_password")
NEO4J_BOLT_PORT = 7687
NEO4J_HTTP_PORT = 7474

GRAPH_DB_PORT = 8003
GRAPH_DB_DEFAULT_URL = f"http://localhost:{GRAPH_DB_PORT}"

VECTOR_DB_PORT = 8002
VECTOR_DB_DEFAULT_URL = f"http://localhost:{VECTOR_DB_PORT}"

API_PORT = 8000
API_DEFAULT_URL = f"http://localhost:{API_PORT}"


@pytest.fixture(scope="session")
def neo4j_container():
    """
    Starts a Neo4j container for integration tests.

    Waits for Bolt connectivity with 120 retries (60s timeout) to ensure
    the database is fully ready before returning.
    """
    container = (
        DockerContainer("neo4j:latest")
        .with_exposed_ports(NEO4J_BOLT_PORT, NEO4J_HTTP_PORT)
        .with_env("NEO4J_AUTH", f"{NEO4J_USER}/{NEO4J_PASSWORD}")
    )

    with container:
        # Wait for Neo4j to be fully ready by verifying Bolt connectivity
        host = container.get_container_host_ip()
        port = container.get_exposed_port(NEO4J_BOLT_PORT)

        for attempt in range(120):  # 60 seconds with 500ms intervals
            try:
                from neo4j import GraphDatabase

                driver = GraphDatabase.driver(
                    f"bolt://{host}:{port}",
                    auth=(NEO4J_USER, NEO4J_PASSWORD),
                    connection_timeout=1.0,
                )
                driver.verify_connectivity()
                driver.close()
                break
            except Exception:
                time.sleep(0.5)
                if attempt == 119:
                    raise RuntimeError(f"Neo4j failed to start at {host}:{port}")

        yield container


@pytest.fixture(scope="session")
def graph_db_container(neo4j_container):
    """
    Starts a Graph DB container that connects to the Neo4j testcontainer.

    - Builds the Docker image using subprocess with BuildKit enabled
    - Configures Neo4j connection via environment variables
    - Waits for HTTP readiness before yielding the container URL
    """
    # Give Neo4j a moment to fully stabilize
    time.sleep(2)

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    graph_db_path = os.path.join(project_root, "services", "graph-db")

    neo4j_host = neo4j_container.get_container_host_ip()
    neo4j_port = neo4j_container.get_exposed_port(NEO4J_BOLT_PORT)

    # For Docker Desktop (localhost), use host.docker.internal for inter-container communication
    # For Linux/CI, use the actual host IP address
    if neo4j_host in ("localhost", "127.0.0.1"):
        neo4j_uri = f"bolt://host.docker.internal:{neo4j_port}"
    else:
        neo4j_uri = f"bolt://{neo4j_host}:{neo4j_port}"

    # Build the Docker image with BuildKit support for cache mount directives
    env = os.environ.copy()
    env["DOCKER_BUILDKIT"] = "1"

    subprocess.run(
        ["docker", "build", "-t", "graph-db:test", graph_db_path],
        check=True,
        env=env,
        capture_output=True,
    )

    # Start the Graph DB service container
    container = (
        DockerContainer("graph-db:test")
        .with_exposed_ports(GRAPH_DB_PORT)
        .with_env("NEO4J_URI", neo4j_uri)
        .with_env("NEO4J_USER", NEO4J_USER)
        .with_env("NEO4J_PASSWORD", NEO4J_PASSWORD)
    )

    with container:
        # Wait for the Graph DB service to be ready
        host = container.get_container_host_ip()
        port = container.get_exposed_port(GRAPH_DB_PORT)
        graph_db_url = f"http://{host}:{port}"

        # Poll until service responds to /docs endpoint
        time.sleep(2)  # Initial delay for service startup
        for attempt in range(150):  # 15 seconds total polling
            try:
                response = httpx.get(f"{graph_db_url}/docs", timeout=2.0)
                if response.status_code == 200:
                    break
            except (httpx.RequestError, httpx.TimeoutException):
                pass

            if attempt < 149:
                time.sleep(0.1)
        else:
            raise RuntimeError(
                f"Graph DB service at {graph_db_url} failed to start. "
                f"Neo4j URI was configured as: {neo4j_uri}"
            )

        yield graph_db_url


@pytest.fixture(scope="session")
def graph_db_url(graph_db_container):
    """Provides the Graph DB service URL from the testcontainer."""
    return graph_db_container


@pytest.fixture(scope="session")
def vector_db_url():
    """Provides the Vector DB service URL (default: localhost:8002)."""
    return VECTOR_DB_DEFAULT_URL


@pytest.fixture(scope="session")
def base_api_url():
    """Provides the base API URL (default: localhost:8000)."""
    return API_DEFAULT_URL


@pytest.fixture
async def http_client():
    """Async HTTP client for making API requests in tests."""
    async with httpx.AsyncClient() as client:
        yield client


@pytest.fixture
def sample_integration_data():
    """Sample data for integration testing across components."""
    return {
        "authors": [
            {
                "id": "A123456",
                "display_name": "Dr. Jane Smith",
                "affiliation": "Carnegie Mellon University",
            },
            {
                "id": "A234567",
                "display_name": "Dr. John Doe",
                "affiliation": "MIT",
            },
        ],
        "works": [
            {
                "id": "W789012",
                "title": "Advanced AI Research",
                "authors": ["A123456", "A234567"],
                "year": 2025,
            }
        ],
        "organizations": [
            {
                "id": "O111111",
                "display_name": "Carnegie Mellon University",
                "type": "education",
            }
        ],
    }


@pytest.fixture
def sample_search_query():
    """Sample search query for end-to-end tests."""
    return {
        "query": "machine learning artificial intelligence",
        "filters": {
            "year_min": 2020,
            "year_max": 2026,
            "author_affiliation": "Carnegie Mellon University",
        },
        "limit": 20,
    }
