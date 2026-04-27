"""Integration test configuration and shared fixtures.

This module provides session-scoped fixtures for integration testing:

Container Fixtures:
- neo4j_container: Spins up a Neo4j testcontainer (session scope)
- graph_db_container: Builds and starts Graph DB service container (session scope)

URL Fixtures:
- graph_db_url: Returns the Graph DB service URL from the container
- vector_db_url: Returns the Vector DB service URL (defaults to localhost:8002)
- base_api_url: Returns the main API URL (defaults to localhost:8000)

Utility Fixtures:
- http_client: Async HTTP client for API requests (function scope)
- sample_integration_data: Sample data for cross-component testing

Fixture Patterns:
1. Container fixtures (*_container) return the DockerContainer object
2. URL fixtures (*_url) return string URLs derived from containers or defaults
3. Service fixtures that need containers should depend on *_container fixtures
4. Tests making HTTP calls should use *_url fixtures

Note: The neo4j_container and graph_db_container are session-scoped to avoid
slow container startup between tests. They are automatically torn down after
all tests complete.
"""

import os
import sys
import gzip
import json
import time
import socket
import logging
import warnings
import subprocess
from pathlib import Path

import pytest
import httpx
from neo4j import GraphDatabase
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


@pytest.fixture(scope="function")
async def http_client():
    """Async HTTP client for making API requests in tests.
    
    Scope: Function (new client for each test to avoid state leakage)
    """
    async with httpx.AsyncClient() as client:
        yield client


@pytest.fixture(scope="function")
def sample_integration_data():
    """Sample data for integration testing across components.
    
    Scope: Function (fresh data for each test)
    """
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


@pytest.fixture(scope="function")
def sample_search_query():
    """Sample search query for end-to-end tests.
    
    Scope: Function (fresh query for each test)
    """
    return {
        "query": "machine learning artificial intelligence",
        "filters": {
            "year_min": 2020,
            "year_max": 2026,
            "author_affiliation": "Carnegie Mellon University",
        },
        "limit": 20,
    }


# --- Utility Functions ---


def get_free_port():
    """Finds a free port on the host machine.
    
    Used for dynamically allocating ports to test services to avoid conflicts.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


# --- Neo4j Database Fixtures ---


@pytest.fixture(scope="session")
def neo4j_driver(neo4j_container):
    """Neo4j driver connected to the testcontainer.
    
    Scope: Session (reuses connection across all tests)
    
    Provides direct database access for:
    - Custom test data setup
    - Direct query verification
    - Database state inspection
    
    Uses credentials from NEO4J_USER and NEO4J_PASSWORD constants.
    """
    neo4j_host = neo4j_container.get_container_host_ip()
    neo4j_port = neo4j_container.get_exposed_port(NEO4J_BOLT_PORT)
    bolt_url = f"bolt://{neo4j_host}:{neo4j_port}"

    driver = GraphDatabase.driver(bolt_url, auth=(NEO4J_USER, NEO4J_PASSWORD))
    yield driver
    driver.close()


@pytest.fixture(scope="session", autouse=True)
def ensure_test_data(neo4j_driver):
    """Automatically loads DTIC test data into Neo4j if the database is empty.
    
    Scope: Session (runs once, autouse=True)
    
    Checks for a canary author ID. If not found, loads:
    - Authors from dtic_authors_50.jsonl.gz
    - Topics from dtic_topics_50.jsonl.gz
    - Works from dtic_works_50.jsonl.gz with relationships
    
    This fixture ensures a consistent test dataset across all integration tests.
    """
    time.sleep(2)

    # Use a known author ID as a canary to detect if data is already loaded
    canary_id = "author_703841d2-b558-53e2-8454-11689b6251db"
    data_dir = Path(__file__).resolve().parent / "dtic_test_subset"

    with neo4j_driver.session() as session:
        result = session.run("MATCH (a:Author {id: $id}) RETURN a", id=canary_id)

        if not result.single():
            print(f"\n[Setup] Database empty. Loading test subset from {data_dir}...")

            load_gz_jsonl(session, data_dir / "dtic_authors_50.jsonl.gz", "Author")
            load_gz_jsonl(session, data_dir / "dtic_topics_50.jsonl.gz", "Topic")
            load_gz_jsonl(session, data_dir / "dtic_works_50.jsonl.gz", "Work")

            print("[Setup] Test data loading complete.")


def load_gz_jsonl(session, file_path, label):
    """Loads a gzipped JSONL file into Neo4j.
    
    Handles three node types:
    - Author: MERGE on id, SET name (from 'name' or 'display_name'), h_index, works_count
    - Topic: MERGE on id, SET name from 'display_name'
    - Work: MERGE on id, SET title, create AUTHORED relationships with Authors,
            and HAS_TOPIC relationships with Topics
    
    The Work data format supports both nested objects (authors: [{author_id: ...}])
    and direct arrays (author_ids: [...]) for flexibility across data sources.
    """
    if not file_path.exists():
        print(f"[Warning] Skipping {file_path.name} - file not found.")
        return

    with gzip.open(file_path, "rt", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            try:
                item = json.loads(line)

                if label == "Author":
                    session.execute_write(
                        lambda tx: tx.run(
                            """
                            MERGE (a:Author {id: $id})
                            SET a.name = $name,
                                a.h_index = $h_index,
                                a.works_count = $works_count
                            """,
                            id=item["id"],
                            name=item.get("name") or item.get("display_name"),
                            h_index=item.get("h_index", 0),
                            works_count=item.get("works_count", 0),
                        )
                    )

                elif label == "Topic":
                    session.execute_write(
                        lambda tx: tx.run(
                            "MERGE (t:Topic {id: $id}) SET t.name = $name",
                            id=item["id"],
                            name=item.get("display_name"),
                        )
                    )

                elif label == "Work":
                    # Handle both nested object format and direct array format
                    authors_data = item.get("authors", [])
                    author_ids = (
                        [a.get("author_id") for a in authors_data]
                        if authors_data
                        else item.get("author_ids", [])
                    )

                    topics_data = item.get("topics", [])
                    topic_ids = (
                        [t.get("topic_id") for t in topics_data]
                        if topics_data
                        else item.get("topic_ids", [])
                    )

                    session.execute_write(
                        lambda tx: tx.run(
                            """
                            MERGE (w:Work {id: $id})
                            SET w.title = $title
                            WITH w
                            UNWIND $author_ids AS a_id
                            MATCH (a:Author {id: a_id})
                            MERGE (a)-[:AUTHORED]->(w)
                            WITH w
                            UNWIND $topic_ids AS t_id
                            MATCH (t:Topic {id: t_id})
                            MERGE (w)-[:HAS_TOPIC]->(t)
                            """,
                            id=item["id"],
                            title=item.get("title"),
                            author_ids=author_ids,
                            topic_ids=topic_ids,
                        )
                    )
            except Exception as e:
                print(f"[Warning] Error loading {label} at line {line_num}: {e}")
                continue

    print(f"[Setup] Loaded {label} from {file_path.name}")


# --- Application Client Fixtures ---


@pytest.fixture(scope="function")
def app_client(monkeypatch, graph_db_container):
    """FastAPI test client for aegis_scholar_api with dynamically configured environment.
    
    Scope: Function (recreated for each test to ensure clean environment)
    
    Sets GRAPH_DB_URL and VECTOR_DB_URL to match testcontainer instances.
    Forces module reimport to ensure Pydantic Settings are initialized with updated env vars.
    
    Note: This requires aegis_scholar_api to be in the Python path. Tests using this
    fixture should configure sys.path appropriately in their module or conftest.
    """
    # Configure environment with testcontainer URLs
    monkeypatch.setenv("GRAPH_DB_URL", graph_db_container)
    monkeypatch.setenv("VECTOR_DB_URL", VECTOR_DB_DEFAULT_URL)

    # Force reimport of app modules to pick up updated environment variables.
    # The Pydantic Settings object initializes at module import time, so we must
    # reload the modules after setting environment variables.
    for module_name in ("app.config", "app.services.graph_db", "app.main"):
        if module_name in sys.modules:
            del sys.modules[module_name]

    # Import after path manipulation and module cleanup
    # pylint: disable=import-outside-toplevel
    from app.main import app
    
    return app
