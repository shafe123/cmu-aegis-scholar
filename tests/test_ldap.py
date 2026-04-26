"""Integration tests for Identity Service using a live OpenLDAP container."""

import pytest
from ldap3 import ALL, SUBTREE, Connection, Server
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs

# ---------------------------------------------------------------------------
# OpenLDAP container fixture — starts once for all tests in this module
# ---------------------------------------------------------------------------

LDAP_IMAGE = "symas/openldap:latest"
LDAP_PORT = 1389
LDAP_ADMIN_DN = "cn=admin,dc=example,dc=org"
LDAP_ADMIN_PASSWORD = "admin"
LDAP_BASE_DN = "dc=example,dc=org"

@pytest.fixture(scope="module")
def ldap_container():
    """Start a real OpenLDAP container for integration testing."""
    container = (
        DockerContainer(image=LDAP_IMAGE)
        .with_exposed_ports(LDAP_PORT)
        .with_env("LDAP_ROOT", LDAP_BASE_DN)
        .with_env("LDAP_ADMIN_USERNAME", "admin")
        .with_env("LDAP_ADMIN_PASSWORD", LDAP_ADMIN_PASSWORD)
        .with_env("LDAP_PORT_NUMBER", str(LDAP_PORT))
    )
    with container:
        wait_for_logs(container, "slapd starting", timeout=60)
        yield container

@pytest.fixture(scope="module")
def ldap_container():
    """Start a real OpenLDAP container for integration testing."""
    container = (
        DockerContainer(image=LDAP_IMAGE)
        .with_exposed_ports(LDAP_PORT)
        .with_env("LDAP_ADMIN_USERNAME", "admin")
        .with_env("LDAP_ADMIN_PASSWORD", LDAP_ADMIN_PASSWORD)
        .with_env("LDAP_ROOT", LDAP_BASE_DN)
    )
    with container:
        wait_for_logs(container, "slapd starting", timeout=60)
        yield container


@pytest.fixture(scope="module")
def ldap_server_url(ldap_container):
    """Return the LDAP URL for the test container."""
    host = ldap_container.get_container_host_ip()
    port = ldap_container.get_exposed_port(LDAP_PORT)
    return f"ldap://{host}:{port}"


@pytest.fixture(scope="module")
def ldap_connection(ldap_server_url):
    """Provide a connected ldap3 connection to the test container."""
    server = Server(ldap_server_url, get_info=ALL)
    conn = Connection(server, user=LDAP_ADMIN_DN, password=LDAP_ADMIN_PASSWORD, auto_bind=True)

    # Create the ou=users organizational unit
    users_ou = f"ou=users,{LDAP_BASE_DN}"
    conn.add(users_ou, ["organizationalUnit", "top"], {"ou": "users"})

    yield conn
    conn.unbind()


@pytest.fixture(autouse=True)
def clean_users(ldap_connection):
    """Delete all user entries before each test for a clean slate."""
    search_base = f"ou=users,{LDAP_BASE_DN}"
    ldap_connection.search(search_base, "(objectClass=inetOrgPerson)", attributes=["cn"])
    for entry in ldap_connection.entries:
        ldap_connection.delete(entry.entry_dn)


# ---------------------------------------------------------------------------
# Helpers — mirror the identity service ingestion logic
# ---------------------------------------------------------------------------

def add_user(conn: Connection, uid: str, name: str, email: str | None = None, org: str = "TestOrg") -> bool:
    """Add a single inetOrgPerson entry to the LDAP directory."""
    parts = name.split()
    sn = parts[-1] if parts else name
    dn = f"uid={uid},ou=users,{LDAP_BASE_DN}"
    attrs = {"sn": sn, "cn": name, "o": org}
    if email:
        attrs["mail"] = email
    return bool(conn.add(dn, ["inetOrgPerson", "top"], attrs))


def search_by_name(conn: Connection, name: str) -> list:
    """Search for users by exact CN match."""
    search_base = f"ou=users,{LDAP_BASE_DN}"
    conn.search(search_base, f"(cn={name})", attributes=["cn", "mail", "uid", "o"])
    return conn.entries


def search_with_email(conn: Connection) -> list:
    """Return all users that have an email address."""
    search_base = f"ou=users,{LDAP_BASE_DN}"
    conn.search(
        search_base,
        "(&(objectClass=inetOrgPerson)(mail=*))",
        attributes=["cn", "mail", "o"],
    )
    return conn.entries


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.requires_docker
def test_ldap_container_is_healthy(ldap_connection):
    """Verify the OpenLDAP container starts and accepts connections."""
    assert ldap_connection.bound is True


@pytest.mark.integration
@pytest.mark.requires_docker
def test_ou_users_exists(ldap_connection):
    """The ou=users organizational unit should exist after setup."""
    ldap_connection.search(LDAP_BASE_DN, "(ou=users)", SUBTREE)
    assert len(ldap_connection.entries) > 0


@pytest.mark.integration
@pytest.mark.requires_docker
def test_user_added_successfully(ldap_connection):
    """A user entry should be addable and retrievable by name."""
    result = add_user(ldap_connection, "jsmith", "Jane Smith", email="jane@army.mil")
    assert result is True

    entries = search_by_name(ldap_connection, "Jane Smith")
    assert len(entries) == 1
    assert str(entries[0].cn) == "Jane Smith"


@pytest.mark.integration
@pytest.mark.requires_docker
def test_user_with_email_appears_in_email_search(ldap_connection):
    """Users with email should appear in mail-filtered searches."""
    add_user(ldap_connection, "jsmith", "Jane Smith", email="jane@army.mil")
    add_user(ldap_connection, "jdoe", "John Doe")  # no email

    entries = search_with_email(ldap_connection)
    names = [str(e.cn) for e in entries]

    assert "Jane Smith" in names
    assert "John Doe" not in names


@pytest.mark.integration
@pytest.mark.requires_docker
def test_user_without_email_not_in_email_search(ldap_connection):
    """Users without email should be excluded from mail-filtered searches."""
    add_user(ldap_connection, "noemail", "No Email User")

    entries = search_with_email(ldap_connection)
    names = [str(e.cn) for e in entries]
    assert "No Email User" not in names


@pytest.mark.integration
@pytest.mark.requires_docker
def test_duplicate_user_not_added(ldap_connection):
    """Adding the same UID twice should not create a duplicate entry."""
    add_user(ldap_connection, "jsmith", "Jane Smith", email="jane@army.mil")
    second_result = add_user(ldap_connection, "jsmith", "Jane Smith", email="jane@army.mil")

    assert second_result is False

    entries = search_by_name(ldap_connection, "Jane Smith")
    assert len(entries) == 1


@pytest.mark.integration
@pytest.mark.requires_docker
def test_multiple_users_added(ldap_connection):
    """Multiple distinct users should all be retrievable."""
    users = [
        ("jsmith", "Jane Smith", "jane@army.mil"),
        ("jdoe", "John Doe", "john@navy.mil"),
        ("alee", "Alice Lee", "alice@af.mil"),
    ]
    for uid, name, email in users:
        add_user(ldap_connection, uid, name, email=email)

    entries = search_with_email(ldap_connection)
    assert len(entries) == 3


@pytest.mark.integration
@pytest.mark.requires_docker
def test_exact_name_lookup(ldap_connection):
    """Exact name search should return only the matching entry."""
    add_user(ldap_connection, "jsmith", "Jane Smith", email="jane@army.mil")
    add_user(ldap_connection, "jdoe", "John Doe", email="john@navy.mil")

    entries = search_by_name(ldap_connection, "Jane Smith")
    assert len(entries) == 1
    assert str(entries[0].cn) == "Jane Smith"


@pytest.mark.integration
@pytest.mark.requires_docker
def test_nonexistent_user_returns_empty(ldap_connection):
    """Searching for a user that does not exist should return empty results."""
    entries = search_by_name(ldap_connection, "Nobody Here")
    assert len(entries) == 0


@pytest.mark.integration
@pytest.mark.requires_docker
def test_org_field_stored_correctly(ldap_connection):
    """Organization field should be stored and retrievable correctly."""
    add_user(ldap_connection, "jsmith", "Jane Smith", org="Carnegie Mellon University")

    ldap_connection.search(
        f"ou=users,{LDAP_BASE_DN}",
        "(cn=Jane Smith)",
        attributes=["o"],
    )
    assert len(ldap_connection.entries) == 1
    assert str(ldap_connection.entries[0].o) == "Carnegie Mellon University"