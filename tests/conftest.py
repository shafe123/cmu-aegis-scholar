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

IDENTITY_PORT = 8000
IDENTITY_DEFAULT_URL = f"http://localhost:{IDENTITY_PORT}"

# Container names for Docker network DNS resolution
NEO4J_CONTAINER_NAME = "neo4j-test"
GRAPH_DB_CONTAINER_NAME = "graph-db-test"
IDENTITY_CONTAINER_NAME = "identity-test"
VECTOR_DB_CONTAINER_NAME = "vector-db-test"
AEGIS_API_CONTAINER_NAME = "aegis-api-test"
LDAP_CONTAINER_NAME = "ldap-server"
MILVUS_CONTAINER_NAME = "milvus-standalone"


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
        .with_name(NEO4J_CONTAINER_NAME)
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
    neo4j_uri = f"bolt://{NEO4J_CONTAINER_NAME}:{NEO4J_BOLT_PORT}"

    # Build the Docker image with BuildKit support for cache mount directives
    env = os.environ.copy()
    env["DOCKER_BUILDKIT"] = "1"

    # Use GitHub Actions cache if available (CI environment)
    build_cmd = [
        "docker",
        "build",
        "-t",
        "graph-db:test",
        "--cache-from",
        "type=gha,scope=graph-db",
        "--cache-to",
        "type=gha,mode=max,scope=graph-db",
        graph_db_path,
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
        .with_name(GRAPH_DB_CONTAINER_NAME)  # Named container for DNS resolution
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
                print(
                    f"\n[Warning] Graph DB health check status: {health_response.json()}"
                )
            except Exception as e:
                print(f"\n[Warning] Could not check Graph DB health: {e}")

        yield graph_db_url


@pytest.fixture(scope="session")
def aegis_scholar_api_container(
    docker_network, graph_db_container, identity_container, vector_db_container
):
    """Builds and starts the main Aegis Scholar API as a Docker container.

    Returns the API base URL for making HTTP requests.

    Dependencies:
    - Depends on graph_db_container, identity_container, and vector_db_container
      to ensure those services start first (we don't use their returned URLs since
      the main API needs internal Docker network URLs, not external host URLs)

    This container:
    - Builds from services/aegis_scholar_api/Dockerfile
    - Connects to the shared Docker network
    - Configures service URLs to use internal container names (using port constants)
    - Exposes API_PORT for API requests
    """
    # Note: We depend on service fixtures above for startup ordering only
    # The returned URLs (graph_db_container, etc.) are external host URLs,
    # but we need internal Docker network URLs for inter-container communication

    # Get the absolute path to the aegis_scholar_api service
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    api_service_path = os.path.join(project_root, "services", "aegis_scholar_api")

    # Build the Docker image with BuildKit support and GitHub Actions cache
    env = os.environ.copy()
    env["DOCKER_BUILDKIT"] = "1"

    # Use GitHub Actions cache if available (CI environment)
    build_cmd = [
        "docker",
        "build",
        "-t",
        "aegis-scholar-api:test",
        "--cache-from",
        "type=gha,scope=aegis-scholar-api",
        "--cache-to",
        "type=gha,mode=max,scope=aegis-scholar-api",
        api_service_path,
    ]

    subprocess.run(
        build_cmd,
        check=True,
        env=env,
        capture_output=True,
    )

    # Internal URLs for inter-container communication (using port and container name constants)
    graph_db_internal_url = f"http://{GRAPH_DB_CONTAINER_NAME}:{GRAPH_DB_PORT}"
    identity_internal_url = f"http://{IDENTITY_CONTAINER_NAME}:{IDENTITY_PORT}"
    vector_db_internal_url = f"http://{VECTOR_DB_CONTAINER_NAME}:{VECTOR_DB_PORT}"

    # Build and configure the container
    container = (
        DockerContainer("aegis-scholar-api:test")
        .with_name(AEGIS_API_CONTAINER_NAME)
        .with_exposed_ports(API_PORT)
        .with_env("GRAPH_DB_URL", graph_db_internal_url)
        .with_env("IDENTITY_API_URL", identity_internal_url)
        .with_env("VECTOR_DB_URL", vector_db_internal_url)
        .with_env("LOG_LEVEL", "DEBUG")
    )

    # Connect to shared network
    container._kwargs["network"] = docker_network

    with container:
        # Wait for API to be ready
        host = container.get_container_host_ip()
        port = container.get_exposed_port(API_PORT)
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
        print(
            f"\n[Setup] Aegis Scholar API started at {api_url}, waiting for Graph DB connectivity..."
        )
        for attempt in range(100):  # 10 seconds
            try:
                health_response = httpx.get(f"{api_url}/health", timeout=5.0)
                if health_response.status_code == 200:
                    health_data = health_response.json()
                    # Check if dependencies are initialized (even if unreachable, API should respond)
                    if (
                        "dependencies" in health_data
                        or health_data.get("status") == "healthy"
                    ):
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
        .with_kwargs(hostname=LDAP_CONTAINER_NAME)
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

        # Seed LDAP with test data for identity tests
        ldif_content = f"""dn: ou=users,{LDAP_BASE_DN}
objectClass: organizationalUnit
objectClass: top
ou: users

dn: uid=jsmith,ou=users,{LDAP_BASE_DN}
objectClass: inetOrgPerson
objectClass: top
sn: Smith
cn: Jane Smith
uid: jsmith
mail: jane.smith@example.org
o: Department of Defense
"""
        # Write LDIF content to container and add entries
        ldap_container.exec(
            f"sh -c 'cat > /tmp/test_users.ldif << \"EOF\"\n{ldif_content}\nEOF'"
        )
        result = ldap_container.exec(
            f"ldapadd -c -x -H ldap://127.0.0.1:{LDAP_PORT} "
            f"-D 'cn=admin,{LDAP_BASE_DN}' -w '{LDAP_ADMIN_PASSWORD}' "
            f"-f /tmp/test_users.ldif"
        )
        # Exit code 68 means "already exists" - this is fine for session-scoped fixture
        # The -c flag allows ldapadd to continue processing even when entries exist
        if result[0] != 0 and result[0] != 68:
            print(f"Warning: LDAP seeding failed with exit code: {result[0]}")
            print(f"Output: {result[1]}")

        # Build identity service Docker image
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        identity_path = os.path.join(project_root, "services", "identity")

        env = os.environ.copy()
        env["DOCKER_BUILDKIT"] = "1"

        build_cmd = [
            "docker",
            "build",
            "-t",
            "identity:test",
            "--cache-from",
            "type=gha,scope=identity",
            "--cache-to",
            "type=gha,mode=max,scope=identity",
            identity_path,
        ]

        subprocess.run(build_cmd, check=True, env=env, capture_output=True)

        # Create a temporary directory for identity data volume
        import tempfile

        temp_data_dir = tempfile.mkdtemp(prefix="identity_test_data_")

        # Start identity service container
        identity_container = (
            DockerContainer("identity:test")
            .with_name(IDENTITY_CONTAINER_NAME)
            .with_exposed_ports(IDENTITY_PORT)
            .with_env("LDAP_SERVER", f"ldap://{LDAP_CONTAINER_NAME}:{LDAP_PORT}")
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
            port = identity_container.get_exposed_port(IDENTITY_PORT)
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
    milvus_container.with_kwargs(hostname=MILVUS_CONTAINER_NAME)
    milvus_container._kwargs["network"] = docker_network
    milvus_container.start()

    try:
        # Build vector-db service Docker image
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        vector_db_path = os.path.join(project_root, "services", "vector-db")

        env = os.environ.copy()
        env["DOCKER_BUILDKIT"] = "1"

        build_cmd = [
            "docker",
            "build",
            "-t",
            "vector-db:test",
            "--cache-from",
            "type=gha,scope=vector-db",
            "--cache-to",
            "type=gha,mode=max,scope=vector-db",
            vector_db_path,
        ]

        subprocess.run(build_cmd, check=True, env=env, capture_output=True)

        # Start vector-db service container
        model_cache = os.path.expanduser("~/.cache/aegis-model-cache")
        os.makedirs(model_cache, exist_ok=True)

        vector_container = (
            DockerContainer("vector-db:test")
            .with_name(VECTOR_DB_CONTAINER_NAME)
            .with_exposed_ports(VECTOR_DB_PORT)
            .with_env("MILVUS_HOST", MILVUS_CONTAINER_NAME)
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
            port = vector_container.get_exposed_port(VECTOR_DB_PORT)
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
                        print(
                            f"Vector DB health check attempt {attempt + 1} failed: {e}"
                        )

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


def load_test_author(index=0):
    """Load a specific author from dtic_test_subset.

    Args:
        index: Zero-based index of the author to load

    Returns:
        dict: Author data from dtic_test_subset
    """
    data_dir = Path(__file__).resolve().parent / "dtic_test_subset"
    with gzip.open(data_dir / "dtic_authors_50.jsonl.gz", "rt", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i == index:
                return json.loads(line)
    return None


def load_test_work(index=0):
    """Load a specific work from dtic_test_subset.

    Args:
        index: Zero-based index of the work to load

    Returns:
        dict: Work data from dtic_test_subset
    """
    data_dir = Path(__file__).resolve().parent / "dtic_test_subset"
    with gzip.open(data_dir / "dtic_works_50.jsonl.gz", "rt", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i == index:
                return json.loads(line)
    return None


def find_author_with_zero_works():
    """Find an author with works_count = 0.

    Returns:
        dict: First author with zero works, or None
    """
    data_dir = Path(__file__).resolve().parent / "dtic_test_subset"
    with gzip.open(data_dir / "dtic_authors_50.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            author = json.loads(line)
            if author.get("works_count", 0) == 0:
                return author
    return None


def find_author_with_no_orgs():
    """Find an author with no organization affiliations.

    Returns:
        dict: First author without org_ids, or None
    """
    data_dir = Path(__file__).resolve().parent / "dtic_test_subset"
    with gzip.open(data_dir / "dtic_authors_50.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            author = json.loads(line)
            org_ids = author.get("org_ids", [])
            if not org_ids or len(org_ids) == 0:
                return author
    return None


def find_author_with_zero_citations():
    """Find an author with cited_by_count = 0.

    Returns:
        dict: First author with zero citations, or None
    """
    data_dir = Path(__file__).resolve().parent / "dtic_test_subset"
    with gzip.open(data_dir / "dtic_authors_50.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            author = json.loads(line)
            if author.get("cited_by_count", 0) == 0:
                return author
    return None


def find_author_with_special_characters():
    """Find an author with special characters in name (unicode, apostrophes, etc).

    Returns:
        dict: First author with non-ASCII characters, or None
    """
    data_dir = Path(__file__).resolve().parent / "dtic_test_subset"
    with gzip.open(data_dir / "dtic_authors_50.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            author = json.loads(line)
            name = author.get("display_name", "") or author.get("name", "")
            # Check for non-ASCII characters or special chars
            if any(ord(c) > 127 or c in ["'", "-", ".", ","] for c in name):
                return author
    return None


def find_work_without_authors():
    """Find a work with no author relationships.

    Returns:
        dict: First work without authors, or None
    """
    data_dir = Path(__file__).resolve().parent / "dtic_test_subset"
    with gzip.open(data_dir / "dtic_works_50.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            work = json.loads(line)
            author_ids = work.get("author_ids", [])
            if not author_ids or len(author_ids) == 0:
                return work
    return None


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

    Checks for expected author count. If not 50, clears and reloads:
    - Authors from dtic_authors_50.jsonl.gz
    - Topics from dtic_topics_50.jsonl.gz
    - Works from dtic_works_50.jsonl.gz with relationships

    This fixture ensures a consistent test dataset. Tests that need this data
    should explicitly declare it as a dependency.
    """
    time.sleep(2)

    data_dir = Path(__file__).resolve().parent / "dtic_test_subset"

    with neo4j_driver.session() as session:
        # Check current author count instead of just canary
        count_result = session.run("MATCH (a:Author) RETURN count(a) as count")
        current_count = count_result.single()["count"]
        
        # Only skip loading if we have exactly 50 authors (our expected test set)
        if current_count == 50:
            print(f"\n[Setup] Test data already loaded ({current_count} authors), skipping load.")
            # Still verify edge case author exists
            edge_case_author = find_author_with_zero_works()
            if edge_case_author:
                edge_verify = session.run(
                    "MATCH (a:Author {id: $id}) RETURN a", 
                    id=edge_case_author["id"]
                )
                if edge_verify.single():
                    print(f"[Setup] Verified edge case author exists in Neo4j: {edge_case_author['id'][:20]}...")
                else:
                    print(f"[ERROR] Edge case author {edge_case_author['id'][:20]} not found, will reload data")
                    current_count = 0  # Force reload
        
        if current_count != 50:
            if current_count > 0:
                print(f"\n[Setup] Found {current_count} authors (expected 50), clearing database...")
                session.run("MATCH (n) DETACH DELETE n")
                print("[Setup] Database cleared.")
            
            print(f"\n[Setup] Loading test subset from {data_dir}...")

            load_gz_jsonl(session, data_dir / "dtic_authors_50.jsonl.gz", "Author")
            load_gz_jsonl(session, data_dir / "dtic_topics_50.jsonl.gz", "Topic")
            load_gz_jsonl(session, data_dir / "dtic_works_50.jsonl.gz", "Work")

            print("[Setup] Test data loading complete.")
            
            # Verify the data was actually persisted
            verification_result = session.run("MATCH (a:Author) RETURN count(a) as count")
            author_count = verification_result.single()["count"]
            print(f"[Setup] Verification: {author_count} authors in database")
            
            if author_count == 0:
                raise RuntimeError("[ERROR] Data loading failed - no authors found after load!")
            
            # Verify edge case author exists via direct Neo4j query
            edge_case_author = find_author_with_zero_works()
            if edge_case_author:
                edge_verify = session.run(
                    "MATCH (a:Author {id: $id}) RETURN a", 
                    id=edge_case_author["id"]
                )
                if edge_verify.single():
                    print(f"[Setup] Verified edge case author exists in Neo4j: {edge_case_author['id'][:20]}...")
                else:
                    raise RuntimeError(f"[ERROR] Edge case author not found in DB after loading: {edge_case_author['id']}")


@pytest.fixture(scope="session")
def verify_graph_db_access(ensure_test_data, graph_db_container):
    """Verifies that the graph-db service can access authors loaded by ensure_test_data.
    
    This catches issues where data is loaded directly into Neo4j but the graph-db
    service can't access it due to network/connection problems.
    """
    import httpx
    
    # Get a test author and try to fetch it via the graph-db service
    test_author = find_author_with_zero_works()
    if test_author:
        try:
            response = httpx.get(
                f"{graph_db_container}/authors/{test_author['id']}",
                timeout=5.0
            )
            if response.status_code == 200:
                print(f"[Setup] Graph DB service can access test author: {test_author['id'][:20]}...")
            else:
                print(f"[ERROR] Graph DB returned {response.status_code} for test author {test_author['id'][:20]}")
                print(f"[ERROR] Response: {response.text}")
        except Exception as e:
            print(f"[ERROR] Graph DB service check failed: {e}")


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

    loaded_count = 0
    edge_case_count = {"zero_works": 0, "no_orgs": 0, "zero_citations": 0}
    
    with gzip.open(file_path, "rt", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            try:
                item = json.loads(line)

                if label == "Author":
                    # Track edge cases for debugging
                    if item.get("works_count", 0) == 0:
                        edge_case_count["zero_works"] += 1
                    if not item.get("org_ids") or len(item.get("org_ids", [])) == 0:
                        edge_case_count["no_orgs"] += 1
                    if item.get("cited_by_count", 0) == 0:
                        edge_case_count["zero_citations"] += 1
                    
                    session.execute_write(
                        lambda tx: tx.run(
                            """
                            MERGE (a:Author {id: $id})
                            SET a.name = $name,
                                a.h_index = $h_index,
                                a.works_count = $works_count,
                                a.cited_by_count = $cited_by_count
                            """,
                            id=item["id"],
                            name=item.get("name") or item.get("display_name"),
                            h_index=item.get("h_index", 0),
                            works_count=item.get("works_count", 0),
                            cited_by_count=item.get("cited_by_count", 0),
                        )
                    )
                    loaded_count += 1

                elif label == "Topic":
                    session.execute_write(
                        lambda tx: tx.run(
                            "MERGE (t:Topic {id: $id}) SET t.name = $name",
                            id=item["id"],
                            name=item.get("display_name"),
                        )
                    )
                    loaded_count += 1

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
                    loaded_count += 1
            except Exception as e:
                print(f"[Warning] Error loading {label} at line {line_num}: {e}")
                continue

    print(f"[Setup] Loaded {loaded_count} {label}(s) from {file_path.name}")
    if label == "Author" and any(edge_case_count.values()):
        print(f"[Setup]   Edge cases: {edge_case_count['zero_works']} with zero works, "
              f"{edge_case_count['no_orgs']} with no orgs, "
              f"{edge_case_count['zero_citations']} with zero citations")


# --- Container Log Capture for CI Debugging ---


@pytest.fixture(scope="session", autouse=True)
def capture_container_logs_on_failure(request):
    """Capture container logs on test failure for CI debugging.
    
    Only active in CI environments. Creates test-logs/ directory with logs
    from all containers when tests fail. Useful for debugging container
    startup issues or runtime errors in CI.
    """
    import os
    
    # Only run in CI environment
    if not os.getenv("CI"):
        return
    
    def save_logs():
        """Save all container logs to test-logs/ directory."""
        # Only save logs if tests failed
        if request.session.testsfailed == 0:
            return
            
        logs_dir = Path(__file__).resolve().parent / "test-logs"
        logs_dir.mkdir(exist_ok=True)
        
        # Access session-scoped container fixtures
        # We'll try to get them from the session namespace
        container_names = [
            ("neo4j", "neo4j_container"),
            ("milvus", "milvus_container"),
            ("ldap", "ldap_container"),
            ("graph-db", "graph_db_container"),
            ("vector-db", "vector_db_container"),
            ("identity", "identity_container"),
            ("aegis-api", "aegis_scholar_api_container"),
        ]
        
        for log_name, fixture_name in container_names:
            try:
                # Try to get container from pytest internals
                container = request.getfixturevalue(fixture_name)
                if container and hasattr(container, "get_logs"):
                    logs = container.get_logs()
                    if logs:
                        log_file = logs_dir / f"{log_name}.log"
                        with open(log_file, "w", encoding="utf-8") as f:
                            f.write(logs)
                        print(f"[CI] Saved logs to {log_file}")
            except Exception as e:
                # Container might not exist or fixture might not be available
                print(f"[CI] Could not save {log_name} logs: {e}")
                continue
        
        print(f"[CI] Container logs saved to {logs_dir}")
    
    # Register cleanup function
    request.addfinalizer(save_logs)
