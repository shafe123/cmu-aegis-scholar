import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def reset_org_cache():
    main._ORG_LIST_CACHE = None
    yield
    main._ORG_LIST_CACHE = None


@pytest.fixture
def mock_ldap_conn():
    with patch("app.main.Connection") as mock_conn_cls:
        mock_conn = MagicMock()
        mock_conn_cls.return_value.__enter__.return_value = mock_conn
        yield mock_conn


@pytest.fixture
def mock_ldap_server():
    with patch("app.main.Server") as mock_server:
        yield mock_server


def test_mask_config_value():
    assert main._mask_config_value("secret") == "<set>"
    assert main._mask_config_value("") == "<not set>"


def test_log_startup_config():
    with patch.object(main.logger, "info") as mock_info:
        asyncio.run(main.log_startup_config())
        mock_info.assert_called_once()


def test_clean_uid():
    assert main.clean_uid("John Doe!") == "johndoe"
    assert main.clean_uid("Jane.Doe-123") == "jane.doe-123"
    assert main.clean_uid("!@#") == ""


def test_get_org_list_loads_and_caches():
    mock_file = MagicMock()
    mock_file.__iter__.return_value = iter(
        [
            b'{"name": "Org1"}\n',
            b"not json\n",
            b'{"name": "Org2"}\n',
            b'{"other_key": "value"}\n',
        ]
    )

    with patch("app.main.os.path.exists", return_value=True):
        with patch("app.main.gzip.open") as mock_gzip:
            mock_gzip.return_value.__enter__.return_value = mock_file
            first = main.get_org_list()
            second = main.get_org_list()

    assert set(first) == {"Org1", "Org2"}
    assert second == first
    assert mock_gzip.call_count == 1


def test_get_org_list_defaults_when_missing_or_unreadable():
    with patch("app.main.os.path.exists", return_value=False):
        assert main.get_org_list() == ["DefaultOrg"]

    main._ORG_LIST_CACHE = None
    with patch("app.main.os.path.exists", return_value=True):
        with patch("app.main.gzip.open", side_effect=OSError("boom")):
            assert main.get_org_list() == ["DefaultOrg"]


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "identity"


def test_stats_endpoint_success(mock_ldap_server, mock_ldap_conn):
    sample_entry = SimpleNamespace(cn="user")

    def search_side_effect(*args, **kwargs):
        if args[1] == "(objectClass=inetOrgPerson)":
            mock_ldap_conn.entries = [sample_entry, sample_entry, sample_entry]
        elif args[1] == "(mail=*)":
            mock_ldap_conn.entries = [sample_entry, sample_entry]
        return True

    mock_ldap_conn.search.side_effect = search_side_effect

    response = client.get("/stats")
    assert response.status_code == 200
    assert response.json() == {
        "total_in_ldap": 3,
        "with_email": 2,
        "without_email": 1,
    }


def test_stats_endpoint_exception(mock_ldap_server, mock_ldap_conn):
    mock_ldap_conn.search.side_effect = Exception("LDAP down")

    response = client.get("/stats")
    assert response.status_code == 500
    assert "LDAP Error" in response.json()["detail"]


def test_sync_file_endpoint():
    with patch("app.main.process_and_sync_file"):
        response = client.post("/sync-file")

    assert response.status_code == 200
    assert response.json() == {"message": "Sync started. Check docker logs for progress."}


def test_process_and_sync_file_not_found():
    with patch("app.main.os.path.exists", return_value=False):
        with patch.object(main.logger, "error") as mock_error:
            main.process_and_sync_file()
            mock_error.assert_called_once()


def test_process_and_sync_file_skips_when_directory_already_populated(mock_ldap_server, mock_ldap_conn):
    def search_side_effect(*args, **kwargs):
        if args[1] == "(ou=users)":
            mock_ldap_conn.entries = [SimpleNamespace(cn="users")]
        elif args[1] == "(objectClass=inetOrgPerson)":
            mock_ldap_conn.entries = [SimpleNamespace(cn="user")] * 1001
        return True

    mock_ldap_conn.search.side_effect = search_side_effect

    with patch("app.main.os.path.exists", return_value=True):
        with patch("app.main.gzip.open") as mock_gzip:
            main.process_and_sync_file()
            mock_gzip.assert_not_called()


def test_process_and_sync_file_success(mock_ldap_server, mock_ldap_conn):
    mock_file = MagicMock()
    mock_file.__iter__.return_value = iter(
        [
            b"\n",
            b"not json\n",
            b'{"other": "value"}\n',
            b'{"name": "Alice Example", "email": "alice@example.com", "org_name": "CMU"}\n',
        ]
    )

    def search_side_effect(*args, **kwargs):
        mock_ldap_conn.entries = []
        return True

    mock_ldap_conn.search.side_effect = search_side_effect

    with patch("app.main.os.path.exists", return_value=True):
        with patch("app.main.gzip.open") as mock_gzip:
            with patch("app.main.random.choice", side_effect=lambda seq: seq[0]):
                mock_gzip.return_value.__enter__.return_value = mock_file
                main.process_and_sync_file(force=True)

    assert mock_ldap_conn.add.called


def test_process_and_sync_file_connection_exception(mock_ldap_server):
    with patch("app.main.os.path.exists", return_value=True):
        with patch("app.main.Connection", side_effect=Exception("Connection failure")):
            with patch.object(main.logger, "error") as mock_error:
                main.process_and_sync_file()
                mock_error.assert_called_once()


def test_lookup_exact_match_and_suggestions(mock_ldap_server, mock_ldap_conn):
    exact = SimpleNamespace(uid="jdoe", cn="John Doe", mail="john@example.com", o="CMU")
    similar = SimpleNamespace(cn="Jon Doe", mail="jon@example.com", o="CMU")

    def search_side_effect(*args, **kwargs):
        if args[1] == "(cn=John Doe)":
            mock_ldap_conn.entries = [exact]
        else:
            mock_ldap_conn.entries = [exact, similar]
        return True

    mock_ldap_conn.search.side_effect = search_side_effect

    with patch("app.main.process.extract", return_value=[("John Doe", 100), ("Jon Doe", 88.8)]):
        response = client.get("/lookup", params={"name": "John Doe"})

    assert response.status_code == 200
    data = response.json()
    assert data["exact_match"]["username"] == "jdoe"
    assert data["similar_records"][0]["name"] == "Jon Doe"
    assert data["message"] == "Exact match and suggestions provided."


def test_lookup_exact_match_only(mock_ldap_server, mock_ldap_conn):
    exact = SimpleNamespace(uid="jdoe", cn="John Doe", mail="john@example.com", o="CMU")

    def search_side_effect(*args, **kwargs):
        mock_ldap_conn.entries = [exact]
        return True

    mock_ldap_conn.search.side_effect = search_side_effect

    with patch("app.main.process.extract", return_value=[("John Doe", 100)]):
        response = client.get("/lookup", params={"name": "John Doe"})

    assert response.status_code == 200
    assert response.json()["message"] == "Exact match only."
    assert response.json()["similar_records"] == []


def test_lookup_suggestions_only(mock_ldap_server, mock_ldap_conn):
    candidate = SimpleNamespace(cn="Jane Doe", mail="jane@example.com", o="Research")

    def search_side_effect(*args, **kwargs):
        if args[1] == "(cn=Jan)":
            mock_ldap_conn.entries = []
        else:
            mock_ldap_conn.entries = [candidate]
        return True

    mock_ldap_conn.search.side_effect = search_side_effect

    with patch("app.main.process.extract", return_value=[("Jane Doe", 79.4)]):
        response = client.get("/lookup", params={"name": "Jan"})

    assert response.status_code == 200
    data = response.json()
    assert data["exact_match"] is None
    assert len(data["similar_records"]) == 1
    assert data["message"] == "Suggestions provided."


def test_lookup_no_results_and_lookup_error(mock_ldap_server, mock_ldap_conn):
    mock_ldap_conn.entries = []

    with patch("app.main.process.extract", return_value=[]):
        response = client.get("/lookup", params={"name": "Nobody"})

    assert response.status_code == 200
    assert response.json()["exact_match"] is None
    assert response.json()["similar_records"] == []

    mock_ldap_conn.search.side_effect = Exception("Search failed")
    error_response = client.get("/lookup", params={"name": "Nobody"})
    assert error_response.status_code == 500
