""" Integration test for aegis_scholar_api <-> identiy_api"""
import os
import time
import socket
import subprocess
import pytest
import httpx
import sys
from ldap3 import Server, Connection, ALL

# Import testcontainers 
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs

# =====================================================================
# PATH FIX: We ONLY add Aegis to sys.path to prevent 'app' collisions
# =====================================================================
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AEGIS_DIR = os.path.join(PROJECT_ROOT, "services", "aegis_scholar_api")
IDENTITY_DIR = os.path.join(PROJECT_ROOT, "services", "identity")

sys.path.insert(0, AEGIS_DIR)

import app.main as main_api
from app.config import settings

def get_free_port():
    """Finds a free port on the host to run our Identity test server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]

@pytest.fixture(scope="session")
def ldap_container():
    """Spins up an ephemeral OpenLDAP server using Testcontainers."""
    with DockerContainer("osixia/openldap:1.5.0") \
            .with_exposed_ports(389) \
            .with_env("LDAP_ORGANIZATION", "Example") \
            .with_env("LDAP_DOMAIN", "example.org") \
            .with_env("LDAP_ADMIN_PASSWORD", "admin") as container:

        wait_for_logs(container, "slapd starting", timeout=30)
        time.sleep(2)
        yield container

@pytest.fixture(scope="session")
def seeded_ldap(ldap_container):
    """Seeds the Testcontainer LDAP instance with a test user."""
    host = ldap_container.get_container_host_ip()
    port = ldap_container.get_exposed_port(389)
    ldap_url = f"ldap://{host}:{port}"

    ldap_user = "cn=admin,dc=example,dc=org"
    ldap_pass = "admin"

    # Seed the LDAP database
    server = Server(ldap_url, get_info=ALL)
    with Connection(server, user=ldap_user, password=ldap_pass, auto_bind=True) as conn:
        conn.add("ou=users,dc=example,dc=org", ["organizationalUnit", "top"], {"ou": "users"})
        conn.add(
            "uid=jsmith,ou=users,dc=example,dc=org",
            ["inetOrgPerson", "top"],
            {
                "sn": "Smith",
                "cn": "Jane Smith",
                "mail": "jane.smith@example.org",
                "o": "Department of Defense"
            }
        )
    return ldap_url

@pytest.fixture(scope="session")
def identity_server(seeded_ldap):
    """Runs the Identity FastAPI app in an ISOLATED background subprocess with logging."""
    port = get_free_port()

    env = os.environ.copy()
    env["LDAP_SERVER"] = seeded_ldap
    env["LDAP_USER"] = "cn=admin,dc=example,dc=org"
    env["LDAP_PASS"] = "admin"
    env["LDAP_BASE_DN"] = "dc=example,dc=org"

    # Capture stdout and stderr to see EXACTLY why it crashes
    process = subprocess.Popen(
        [sys.executable,
         "-m", "uvicorn",
         "app.main:app",
         "--host", "127.0.0.1",
         "--port", str(port)],
        cwd=IDENTITY_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    identity_url = f"http://127.0.0.1:{port}"

    # Poll until uvicorn is ready
    for _ in range(100):  # 10 seconds total
        try:
            # Check if the process crashed prematurely
            if process.poll() is not None:
                out, err = process.communicate()
                raise RuntimeError(
                    f"Identity Server Subprocess Crashed!\nSTDOUT:\n{out}\nSTDERR:\n{err}")

            if httpx.get(f"{identity_url}/docs").status_code == 200:
                break
        except httpx.RequestError:
            time.sleep(0.1)
    else:
        process.terminate()
        out, err = process.communicate()
        raise RuntimeError(f"Identity Server Subprocess Timed Out.\nSTDOUT:\n{out}\nSTDERR:\n{err}")

    settings.identity_api_url = identity_url
    yield identity_url

    process.terminate()
    process.wait()


@pytest.mark.asyncio
async def test_full_identity_lookup_flow(identity_server):
    """
    Test the full chain:
    AsyncClient -> Main API (/identity/lookup) -> Identity API (/lookup) -> LDAP (testcontainer)
    """
    transport = httpx.ASGITransport(app=main_api.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:


        # 1. Lookup the seeded user
        response = await client.get("/identity/lookup", params={"name": "Jane Smith"})

        assert response.status_code == 200
        data = response.json()

        # 2. Assert exact match logic
        assert "exact_match" in data
        exact = data["exact_match"]
        assert exact is not None
        assert exact["name"] == "Jane Smith"
        assert exact["email"] == "jane.smith@example.org"

        # 3. Assert a non-existent user returns 200 but with no exact match
        response_missing = await client.get("/identity/lookup", params={"name": "Ghost User"})
        assert response_missing.status_code == 200
        assert response_missing.json().get("exact_match") is None
