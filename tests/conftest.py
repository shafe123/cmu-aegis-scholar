"""Integration test configuration and shared fixtures.

This module provides session-scoped fixtures for integration testing:

Container Fixtures:
- docker_network: Shared Docker network for inter-container communication
- neo4j_container: Spins up a Neo4j testcontainer (session scope)
- graph_db_container: Builds and starts Graph DB service container (session scope)

URL Fixtures:
- graph_db_url: Returns the Graph DB service URL from the container
- vector_db_url: Returns the Vector DB service URL (defaults to localhost:8002)
- main_api_url: Returns the main API URL (defaults to localhost:8000)

Utility Fixtures:
- http_client: Async HTTP client for API requests (function scope)
- sample_integration_data: Sample data for cross-component testing

Fixture Patterns:
1. Container fixtures (*_container) return the DockerContainer object
2. URL fixtures (*_url) return string URLs derived from containers or defaults
3. Service fixtures that need containers should depend on *_container fixtures
4. Tests making HTTP calls should use *_url fixtures

Docker Networking:
All testcontainers are connected to a shared Docker bridge network to enable
inter-container communication. This is critical for the Graph DB service to
connect to Neo4j in CI environments. Containers use their container names
(e.g., "neo4j-test") for DNS resolution within the network.

Note: The neo4j_container and graph_db_container are session-scoped to avoid
slow container startup between tests. They are automatically torn down after
all tests complete.
"""

import os
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

LDAP_IMAGE = "symas/openldap:latest"
LDAP_PORT = int(os.getenv("LDAP_PORT", "1389"))
LDAP_BASE_DN = os.getenv("LDAP_BASE_DN", "dc=example,dc=org")
LDAP_ADMIN_PASSWORD = os.getenv("LDAP_ADMIN_PASSWORD", "testpassword")


@pytest.fixture(scope="session")
def docker_network():
    """Creates a shared Docker network for testcontainers to communicate.
    
    This enables inter-container communication in CI environments where
    containers can't reach each other via host networking.
    """
    import docker
    
    client = docker.from_env()
    network_name = "aegis-test-network"
    
    # Create network
    network = client.networks.create(network_name, driver="bridge")
    
    yield network_name
    
    # Cleanup
    try:
        network.remove()
    except Exception:
        pass  # Network may already be removed


@pytest.fixture(scope="session")
def neo4j_container(docker_network):
    """
    Starts a Neo4j container for integration tests.

    Waits for Bolt connectivity with 120 retries (60s timeout) to ensure
    the database is fully ready before returning.
    """
    container = (
        DockerContainer("neo4j:latest")
        .with_exposed_ports(NEO4J_BOLT_PORT, NEO4J_HTTP_PORT)
        .with_env("NEO4J_AUTH", f"{NEO4J_USER}/{NEO4J_PASSWORD}")
        .with_name("neo4j-test")
    )
    
    # Connect to the shared network
    container._kwargs["network"] = docker_network

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
def graph_db_container(neo4j_container, docker_network):
    """
    Starts a Graph DB container that connects to the Neo4j testcontainer.

    - Builds the Docker image using subprocess with BuildKit enabled
    - Configures Neo4j connection via environment variables
    - Uses Docker network for inter-container communication
    - Waits for HTTP readiness AND Neo4j connectivity before yielding
    """
    # Give Neo4j a moment to fully stabilize
    time.sleep(3)

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    graph_db_path = os.path.join(project_root, "services", "graph-db")

    # Use the container name for inter-container communication
    # This works in both local and CI environments when on same network
    neo4j_uri = f"bolt://neo4j-test:{NEO4J_BOLT_PORT}"

    # Build the Docker image with BuildKit support for cache mount directives
    env = os.environ.copy()
    env["DOCKER_BUILDKIT"] = "1"

    # Use GitHub Actions cache if available (CI environment)
    build_cmd = [
        "docker", "build", 
        "-t", "graph-db:test",
        "--cache-from", "type=gha,scope=graph-db",
        "--cache-to", "type=gha,mode=max,scope=graph-db",
        graph_db_path
    ]
    
    subprocess.run(
        build_cmd,
        check=True,
        env=env,
        capture_output=True,
    )

    # Start the Graph DB service container on the same network
    container = (
        DockerContainer("graph-db:test")
        .with_name("graph-db-test")  # Named container for DNS resolution
        .with_exposed_ports(GRAPH_DB_PORT)
        .with_env("NEO4J_URI", neo4j_uri)
        .with_env("NEO4J_USER", NEO4J_USER)
        .with_env("NEO4J_PASSWORD", NEO4J_PASSWORD)
    )
    
    # Connect to the shared network
    container._kwargs["network"] = docker_network

    with container:
        # Wait for the Graph DB service to be ready
        host = container.get_container_host_ip()
        port = container.get_exposed_port(GRAPH_DB_PORT)
        graph_db_url = f"http://{host}:{port}"

        # Poll until service responds to /docs endpoint
        time.sleep(3)  # Initial delay for service startup
        for attempt in range(200):  # 20 seconds total polling (more time in CI)
            try:
                response = httpx.get(f"{graph_db_url}/docs", timeout=3.0)
                if response.status_code == 200:
                    break
            except (httpx.RequestError, httpx.TimeoutException):
                pass

            if attempt < 199:
                time.sleep(0.1)
        else:
            raise RuntimeError(
                f"Graph DB service at {graph_db_url} failed to start. "
                f"Neo4j URI was configured as: {neo4j_uri}"
            )

        # Additional health check: verify Graph DB can actually connect to Neo4j
        time.sleep(2)
        for attempt in range(30):  # 15 seconds for Neo4j connectivity
            try:
                health_response = httpx.get(f"{graph_db_url}/health", timeout=3.0)
                if health_response.status_code == 200:
                    health_data = health_response.json()
                    if health_data.get("status") == "healthy":
                        break
            except Exception:
                pass
            
            if attempt < 29:
                time.sleep(0.5)
        else:
            # Log the last health check for debugging
            try:
                health_response = httpx.get(f"{graph_db_url}/health", timeout=3.0)
                print(f"\n[Warning] Graph DB health check status: {health_response.json()}")
            except Exception as e:
                print(f"\n[Warning] Could not check Graph DB health: {e}")

        yield graph_db_url


@pytest.fixture(scope="session")
def aegis_scholar_api_container(docker_network, graph_db_container):
    """Builds and starts the main Aegis Scholar API as a Docker container.
    
    Returns the API base URL for making HTTP requests.
    
    This container:
    - Builds from services/aegis_scholar_api/Dockerfile
    - Connects to the shared Docker network
    - Configures GRAPH_DB_URL to use container name (graph-db-test)
    - Exposes port 8000 for API requests
    """
    # Get the absolute path to the aegis_scholar_api service
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    api_service_path = os.path.join(project_root, "services", "aegis_scholar_api")
    
    # Build the Docker image with BuildKit support and GitHub Actions cache
    env = os.environ.copy()
    env["DOCKER_BUILDKIT"] = "1"
    
    # Use GitHub Actions cache if available (CI environment)
    build_cmd = [
        "docker", "build",
        "-t", "aegis-scholar-api:test",
        "--cache-from", "type=gha,scope=aegis-scholar-api",
        "--cache-to", "type=gha,mode=max,scope=aegis-scholar-api",
        api_service_path
    ]
    
    subprocess.run(
        build_cmd,
        check=True,
        env=env,
        capture_output=True,
    )
    
    # Graph DB URL for inter-container communication
    graph_db_internal_url = "http://graph-db-test:8003"
    
    # Build and configure the container
    container = (
        DockerContainer("aegis-scholar-api:test")
        .with_name("aegis-api-test")
        .with_exposed_ports(8000)
        .with_env("GRAPH_DB_URL", graph_db_internal_url)
        .with_env("VECTOR_DB_URL", VECTOR_DB_DEFAULT_URL)
        .with_env("LOG_LEVEL", "DEBUG")
    )
    
    # Connect to shared network
    container._kwargs["network"] = docker_network
    
    with container:
        # Wait for API to be ready
        host = container.get_container_host_ip()
        port = container.get_exposed_port(8000)
        api_url = f"http://{host}:{port}"
        
        # Step 1: Wait for API server to start responding to /docs
        time.sleep(3)
        for attempt in range(200):  # 20 seconds
            try:
                response = httpx.get(f"{api_url}/docs", timeout=5.0)
                if response.status_code == 200:
                    break
            except (httpx.RequestError, httpx.TimeoutException):
                pass
            
            if attempt < 199:
                time.sleep(0.1)
        else:
            raise RuntimeError(
                f"Aegis Scholar API at {api_url} failed to start. "
                f"Check container logs for details."
            )
        
        # Step 2: Wait for API to successfully connect to dependencies (Graph DB)
        # The /health endpoint checks downstream services
        print(f"\n[Setup] Aegis Scholar API started at {api_url}, waiting for Graph DB connectivity...")
        for attempt in range(100):  # 10 seconds
            try:
                health_response = httpx.get(f"{api_url}/health", timeout=5.0)
                if health_response.status_code == 200:
                    health_data = health_response.json()
                    # Check if dependencies are initialized (even if unreachable, API should respond)
                    if "dependencies" in health_data or health_data.get("status") == "healthy":
                        print(f"[Setup] API health check passed: {health_data}")
                        break
            except Exception:
                pass
            
            if attempt < 99:
                time.sleep(0.1)
        else:
            print("[Warning] API /health endpoint did not stabilize, but proceeding...")
        
        # Step 3: Warm up the connection with a real request to ensure Graph DB is accessible
        print("[Setup] Warming up API -> Graph DB connection...")
        for attempt in range(30):  # 15 seconds
            try:
                # Try the root endpoint of the API which should be fast
                warmup_response = httpx.get(f"{api_url}/", timeout=10.0)
                if warmup_response.status_code == 200:
                    print("[Setup] Warmup successful, API is ready for tests")
                    break
            except Exception as e:
                if attempt == 29:
                    print(f"[Warning] Warmup request failed: {e}, proceeding anyway...")
                pass
            
            if attempt < 29:
                time.sleep(0.5)
        
        yield api_url


@pytest.fixture(scope="session")
def identity_container(docker_network):
    """
    Starts an Identity Service container with OpenLDAP backend.
    
    - Builds the identity service Docker image
    - Starts OpenLDAP container for testing
    - Configures identity service to connect to LDAP
    - Returns the identity service URL
    """
    # Start OpenLDAP container first
    ldap_container = (
        DockerContainer(LDAP_IMAGE)
        .with_exposed_ports(LDAP_PORT)
        .with_env("LDAP_ROOT", LDAP_BASE_DN)
        .with_env("LDAP_ADMIN_USERNAME", "admin")
        .with_env("LDAP_ADMIN_PASSWORD", LDAP_ADMIN_PASSWORD)
        .with_env("LDAP_PORT_NUMBER", str(LDAP_PORT))
        .with_kwargs(hostname="ldap-server")
    )
    
    ldap_container._kwargs["network"] = docker_network
    ldap_container.start()
    
    try:
        # Wait for LDAP to be ready - verify it's accepting connections via ldapsearch
        # Initial delay for container startup
        time.sleep(3)
        
        max_attempts = 60  # 60 seconds total
        for attempt in range(max_attempts):
            try:
                result = ldap_container.exec(
                    f"ldapsearch -x -H ldap://127.0.0.1:{LDAP_PORT} "
                    f"-D 'cn=admin,{LDAP_BASE_DN}' -w '{LDAP_ADMIN_PASSWORD}' "
                    f"-b '{LDAP_BASE_DN}' -s base"
                )
                if result[0] == 0:  # Success
                    break
            except Exception:
                pass
            
            if attempt < max_attempts - 1:
                time.sleep(1)
        else:
            raise RuntimeError(
                f"LDAP server failed to become ready after {max_attempts} seconds"
            )
        
        # Build identity service Docker image
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        identity_path = os.path.join(project_root, "services", "identity")
        
        env = os.environ.copy()
        env["DOCKER_BUILDKIT"] = "1"
        
        build_cmd = [
            "docker", "build",
            "-t", "identity:test",
            "--cache-from", "type=gha,scope=identity",
            "--cache-to", "type=gha,mode=max,scope=identity",
            identity_path
        ]
        
        subprocess.run(build_cmd, check=True, env=env, capture_output=True)
        
        # Create a temporary directory for identity data volume
        import tempfile
        temp_data_dir = tempfile.mkdtemp(prefix="identity_test_data_")
        
        # Start identity service container
        identity_container = (
            DockerContainer("identity:test")
            .with_name("identity-test")
            .with_exposed_ports(8000)
            .with_env("LDAP_SERVER", f"ldap://ldap-server:{LDAP_PORT}")
            .with_env("LDAP_ADMIN_DN", f"cn=admin,{LDAP_BASE_DN}")
            .with_env("LDAP_ADMIN_PASSWORD", LDAP_ADMIN_PASSWORD)
            .with_env("LDAP_BASE_DN", LDAP_BASE_DN)
            .with_volume_mapping(temp_data_dir, "/data", "rw")
        )
        
        identity_container._kwargs["network"] = docker_network
        identity_container.start()
        
        try:
            # Wait for service to start (look for any FastAPI startup message)
            time.sleep(3)
            
            host = identity_container.get_container_host_ip()
            port = identity_container.get_exposed_port(8000)
            identity_url = f"http://{host}:{port}"
            
            # Poll /docs endpoint first (FastAPI auto-generated docs)
            docs_ready = False
            for attempt in range(60):  # 30 seconds
                try:
                    response = httpx.get(f"{identity_url}/docs", timeout=3.0)
                    if response.status_code == 200:
                        docs_ready = True
                        break
                except Exception:
                    pass
                
                if attempt < 59:
                    time.sleep(0.5)
            
            # Then verify /health endpoint is responding
            health_ready = False
            for attempt in range(30):  # 15 seconds
                try:
                    response = httpx.get(f"{identity_url}/health", timeout=3.0)
                    if response.status_code == 200:
                        health_ready = True
                        break
                except Exception as e:
                    if attempt == 29:
                        print(f"Health check attempt {attempt + 1} failed: {e}")
                
                if attempt < 29:
                    time.sleep(0.5)
            
            if not health_ready:
                raise RuntimeError(
                    f"Identity service health check failed after 45 seconds. "
                    f"Docs ready: {docs_ready}, Health ready: {health_ready}"
                )
            
            yield identity_url
            
        finally:
            identity_container.stop()
            # Clean up temp directory
            import shutil
            try:
                shutil.rmtree(temp_data_dir)
            except Exception:
                pass
    finally:
        ldap_container.stop()


@pytest.fixture(scope="session")
def vector_db_container(docker_network):
    """
    Starts a Vector DB service container with Milvus backend.
    
    - Builds the vector-db service Docker image
    - Starts Milvus container for vector storage
    - Configures vector-db service to connect to Milvus
    - Returns the vector-db service URL
    """
    from testcontainers.milvus import MilvusContainer

    MILVUS_IMAGE = "milvusdb/milvus:v2.4.4"
    
    # Start Milvus container first
    milvus_container = MilvusContainer(image=MILVUS_IMAGE)
    milvus_container.with_kwargs(hostname="milvus-standalone")
    milvus_container._kwargs["network"] = docker_network
    milvus_container.start()
    
    try:
        # Build vector-db service Docker image
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        vector_db_path = os.path.join(project_root, "services", "vector-db")
        
        env = os.environ.copy()
        env["DOCKER_BUILDKIT"] = "1"
        
        build_cmd = [
            "docker", "build",
            "-t", "vector-db:test",
            "--cache-from", "type=gha,scope=vector-db",
            "--cache-to", "type=gha,mode=max,scope=vector-db",
            vector_db_path
        ]
        
        subprocess.run(build_cmd, check=True, env=env, capture_output=True)
        
        # Start vector-db service container
        model_cache = os.path.expanduser("~/.cache/aegis-model-cache")
        os.makedirs(model_cache, exist_ok=True)
        
        vector_container = (
            DockerContainer("vector-db:test")
            .with_name("vector-db-test")
            .with_exposed_ports(8002)
            .with_env("MILVUS_HOST", "milvus-standalone")
            .with_env("MILVUS_PORT", "19530")
            .with_env("DEFAULT_COLLECTION", "aegis_vectors")
            .with_volume_mapping(model_cache, "/app/.cache", "rw")
        )
        
        vector_container._kwargs["network"] = docker_network
        vector_container.start()
        
        try:
            # Wait for service to start
            time.sleep(5)
            
            host = vector_container.get_container_host_ip()
            port = vector_container.get_exposed_port(8002)
            vector_url = f"http://{host}:{port}"
            
            # Poll /docs endpoint first (FastAPI auto-generated docs)
            # Vector service may take longer due to model loading
            docs_ready = False
            for attempt in range(120):  # 60 seconds
                try:
                    response = httpx.get(f"{vector_url}/docs", timeout=3.0)
                    if response.status_code == 200:
                        docs_ready = True
                        break
                except Exception:
                    pass
                
                if attempt < 119:
                    time.sleep(0.5)
            
            # Then verify /health endpoint is responding
            health_ready = False
            for attempt in range(60):  # 30 seconds
                try:
                    response = httpx.get(f"{vector_url}/health", timeout=3.0)
                    if response.status_code == 200:
                        health_ready = True
                        break
                except Exception as e:
                    if attempt == 59:
                        print(f"Vector DB health check attempt {attempt + 1} failed: {e}")
                
                if attempt < 59:
                    time.sleep(0.5)
            
            if not health_ready:
                raise RuntimeError(
                    f"Vector DB service health check failed after 90 seconds. "
                    f"Docs ready: {docs_ready}, Health ready: {health_ready}"
                )
            
            yield vector_url
            
        finally:
            vector_container.stop()
    finally:
        milvus_container.stop()


@pytest.fixture(scope="session")
def graph_db_url(graph_db_container):
    """Provides the Graph DB service URL from the testcontainer."""
    return graph_db_container


@pytest.fixture(scope="module")
def identity_api_url(identity_container):
    """Return the base URL for the identity service container from conftest."""
    return identity_container


@pytest.fixture(scope="session")
def vector_db_url(vector_db_container):
    """Provides the Vector DB service URL from the testcontainer."""
    return vector_db_container


@pytest.fixture(scope="session")
def main_api_url(aegis_scholar_api_container):
    """Returns the URL for the containerized Aegis Scholar API.
    
    Scope: Session (same as the underlying container)
    
    This fixture provides the base URL for the main API running in a Docker container.
    Tests should use httpx.AsyncClient to make HTTP requests to this URL.
    
    The API container is configured to communicate with the Graph DB container
    via Docker network using container names.
    """
    return aegis_scholar_api_container



@pytest.fixture(scope="function")
async def http_client():
    """Async HTTP client for making API requests in tests.
    
    Scope: Function (new client for each test to avoid state leakage)
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
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


@pytest.fixture(scope="function")
def sample_authors(sample_integration_data):
    """Extract authors from sample_integration_data for Milvus tests.
    
    Scope: Function (fresh data for each test)
    
    Returns list of dicts with 'id' and 'name' keys, where 'name' comes from
    'display_name' in the integration data to match the expected schema.
    """
    return [
        {"id": author["id"], "name": author["display_name"]}
        for author in sample_integration_data["authors"]
    ]


@pytest.fixture(scope="function")
def sample_works(sample_integration_data):
    """Extract works from sample_integration_data for Neo4j tests.
    
    Scope: Function (fresh data for each test)
    """
    return sample_integration_data["works"]


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


@pytest.fixture(scope="session")
def ensure_test_data(neo4j_driver):
    """Loads DTIC test data into Neo4j if the database is empty.
    
    Scope: Session (runs once when explicitly requested)
    
    Checks for a canary author ID. If not found, loads:
    - Authors from dtic_authors_50.jsonl.gz
    - Topics from dtic_topics_50.jsonl.gz
    - Works from dtic_works_50.jsonl.gz with relationships
    
    This fixture ensures a consistent test dataset. Tests that need this data
    should explicitly declare it as a dependency.
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

