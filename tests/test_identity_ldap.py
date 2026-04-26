"""
Service-layer integration tests for identity service against a live OpenLDAP container.

These tests spin up both our identity service container and an OpenLDAP container,
then validate that our API correctly queries and returns identity data.
"""

import pytest
import httpx
import docker
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs

# ---------------------------------------------------------------------------
# Container configuration
# ---------------------------------------------------------------------------

LDAP_IMAGE = "symas/openldap:latest"
LDAP_PORT = 1389
LDAP_BASE_DN = "dc=example,dc=org"
LDAP_ADMIN_PASSWORD = "testpassword"
IDENTITY_IMAGE = "aegis-identity-test:latest"
IDENTITY_PORT = 8000


# ---------------------------------------------------------------------------
# Helper — get internal Docker bridge IP
# ---------------------------------------------------------------------------

def get_internal_ip(container) -> str:
    """Get the internal Docker bridge IP of a running container."""
    client = docker.from_env()
    docker_container = client.containers.get(
        container.get_wrapped_container().id
    )
    networks = docker_container.attrs["NetworkSettings"]["Networks"]
    return next(iter(networks.values()))["IPAddress"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

NETWORK_NAME = "aegis-identity-test-net"

@pytest.fixture(scope="module")
def docker_network():
    """Create a shared Docker network for container-to-container communication."""
    client = docker.from_env()
    network = client.networks.create(NETWORK_NAME, driver="bridge")
    yield network
    network.remove()

@pytest.fixture(scope="module")
def ldap_container(docker_network):
    """Start a real OpenLDAP container on the shared test network."""
    container = (
        DockerContainer(image=LDAP_IMAGE)
        .with_exposed_ports(LDAP_PORT)
        .with_env("LDAP_ROOT", LDAP_BASE_DN)
        .with_env("LDAP_ADMIN_USERNAME", "admin")
        .with_env("LDAP_ADMIN_PASSWORD", LDAP_ADMIN_PASSWORD)
        .with_env("LDAP_PORT_NUMBER", str(LDAP_PORT))
        .with_kwargs(network=NETWORK_NAME, hostname="ldap-server")
    )
    with container:
        wait_for_logs(container, "slapd starting", timeout=60)
        yield container


@pytest.fixture(scope="module")
def identity_container(ldap_container, docker_network):
    """
    Start our identity service container on the same network as OpenLDAP.
    The entrypoint hardcodes ldap-server:1389 so we use a shared network
    with the LDAP container assigned that hostname.
    """
    container = (
        DockerContainer(image=IDENTITY_IMAGE)
        .with_exposed_ports(IDENTITY_PORT)
        .with_env("LDAP_SERVER", f"ldap://ldap-server:{LDAP_PORT}")
        .with_env("LDAP_ADMIN_DN", f"cn=admin,{LDAP_BASE_DN}")
        .with_env("LDAP_ADMIN_PASSWORD", LDAP_ADMIN_PASSWORD)
        .with_env("LDAP_BASE_DN", LDAP_BASE_DN)
        .with_kwargs(network=NETWORK_NAME)
    )
    with container:
        wait_for_logs(container, "Starting FastAPI Gateway", timeout=60)
        yield container


@pytest.fixture(scope="module")
def identity_api_url(identity_container):
    """Return the base URL for the identity service container."""
    host = identity_container.get_container_host_ip()
    port = identity_container.get_exposed_port(IDENTITY_PORT)
    return f"http://{host}:{port}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.requires_docker
def test_identity_service_is_healthy(identity_api_url):
    """Our identity service should report healthy when LDAP is available."""
    response = httpx.get(f"{identity_api_url}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "identity"


@pytest.mark.integration
@pytest.mark.requires_docker
def test_lookup_returns_empty_for_unknown_name(identity_api_url):
    """Lookup for a name not in LDAP should return no exact match."""
    response = httpx.get(f"{identity_api_url}/lookup", params={"name": "Nobody Known"})
    assert response.status_code == 200
    data = response.json()
    assert data["exact_match"] is None


@pytest.mark.integration
@pytest.mark.requires_docker
def test_stats_endpoint(identity_api_url):
    """Stats endpoint should return LDAP population counts."""
    response = httpx.get(f"{identity_api_url}/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_in_ldap" in data
    assert "with_email" in data
    assert "without_email" in data
