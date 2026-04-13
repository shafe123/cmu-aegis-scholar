import pytest
import os
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# 1. Update imports to point to the app folder
from app import main
from app.main import app, UserRecord

client = TestClient(app)

# ---------------------------------------------------------
# Fixtures
# ---------------------------------------------------------

@pytest.fixture
def mock_ldap_conn():
    """Mocks the LDAP Connection context manager."""
    with patch("app.main.Connection") as mock_conn_cls:
        mock_conn = MagicMock()
        mock_conn_cls.return_value.__enter__.return_value = mock_conn
        yield mock_conn

@pytest.fixture
def mock_ldap_server():
    """Mocks the LDAP Server."""
    with patch("app.main.Server") as mock_server:
        yield mock_server

# ---------------------------------------------------------
# Utility Function Tests
# ---------------------------------------------------------

def test_count_records_file_exists():
    with patch("app.main.os.path.exists", return_value=True):
        with patch("app.main.gzip.open") as mock_gzip:
            mock_file = MagicMock()
            mock_file.__iter__.return_value = iter([b"1\n", b"2\n", b"3\n"])
            mock_gzip.return_value.__enter__.return_value = mock_file
            assert main.count_records("dummy.gz") == 3

def test_count_records_no_file():
    with patch("app.main.os.path.exists", return_value=False):
        assert main.count_records("dummy.gz") == 0

def test_generate_email():
    email = main.generate_email("Test Name")
    assert "@" in email
    assert email.split("@")[1] in main.DOMAINS

def test_generate_org():
    with patch("app.main.org_names", ["MockOrg1", "MockOrg2"]):
        org = main.generate_org()
        assert org in ["MockOrg1", "MockOrg2"]
        
    with patch("app.main.org_names", []):
        assert main.generate_org() == "DefaultOrg"

def test_generate_org_list():
    # Test valid parsing
    with patch("app.main.os.path.exists", return_value=True):
        with patch("app.main.gzip.open") as mock_gzip:
            mock_file = MagicMock()
            # Valid JSON, Invalid JSON, Missing 'name' key
            mock_file.__iter__.return_value = iter([
                b'{"name": "ValidOrg"}\n',
                b'not json\n',
                b'{"other_key": "value"}\n'
            ])
            mock_gzip.return_value.__enter__.return_value = mock_file
            orgs = main.generate_org_list("dummy.gz")
            assert "ValidOrg" in orgs
            assert len(orgs) == 1

    # Test Exception block (e.g. permission denied)
    with patch("app.main.os.path.exists", return_value=True):
        with patch("app.main.gzip.open", side_effect=Exception("Read Error")):
            orgs = main.generate_org_list("dummy.gz")
            assert orgs == ["DefaultOrg"]

def test_perform_upsert(mock_ldap_conn):
    record_add = UserRecord(username="jdoe", name="John Doe", email="j@d.com")
    record_mod = UserRecord(username="asmith", name="Alice SingleWord", email="a@a.com")
    record_no_email = UserRecord(username="b", name="Bob", email=None)

    # 1. Test ADD branch (entries not found)
    mock_ldap_conn.entries = []
    main.perform_upsert(mock_ldap_conn, record_add)
    assert mock_ldap_conn.add.called
    
    # 2. Test MODIFY branch (entries found, has email)
    mock_ldap_conn.entries = ["existing"]
    main.perform_upsert(mock_ldap_conn, record_mod)
    assert mock_ldap_conn.modify.called

    # 3. Test MODIFY skipped (entries found, but no email)
    mock_ldap_conn.modify.reset_mock()
    main.perform_upsert(mock_ldap_conn, record_no_email)
    mock_ldap_conn.modify.assert_not_called()

# ---------------------------------------------------------
# Batch Sync Tests
# ---------------------------------------------------------

@patch("app.main.TOTAL_ESTIMATED_RECORDS", 1000)
@patch("app.main.os.replace")
@patch("app.main.os.path.exists", return_value=True)
def test_process_and_sync_file_success(mock_exists, mock_replace, mock_ldap_server, mock_ldap_conn):
    with patch("app.main.gzip.open") as mock_gzip_open:
        mock_in = MagicMock()
        mock_out = MagicMock()
        
        # We need exactly 1000 records to hit the `if count % 1000 == 0:` logger branch safely
        lines = [
            b' \n',                                                       # Empty line
            b'{"uid": "missing_name"}\n',                                 # Missing name
            b'{"name": "Bob"}\n',                                         # 'B' -> NO_CONTACT
            b'{"name": "Adam"}\n',                                        # 'A' -> CONTACT (needs email gen)
            b'{"name": "Charlie", "email": "c@c.com", "org_name": "Org, A"}\n' # 'C' -> SIMILAR_CONTACT
        ]
        lines.extend([b'{"name": "Adam"}\n'] * 995) 
        
        mock_in.__iter__.return_value = iter(lines)

        # Handle the two contexts (rb and wb)
        def gzip_side_effect(filename, mode, **kwargs):
            cm = MagicMock()
            cm.__enter__.return_value = mock_in if mode == 'rb' else mock_out
            return cm

        mock_gzip_open.side_effect = gzip_side_effect

        main.process_and_sync_file()
        
        assert mock_replace.called
        assert mock_ldap_conn.add.called

@patch("app.main.os.path.exists", side_effect=[True, True]) 
@patch("app.main.os.remove")
def test_process_and_sync_file_exception(mock_remove, mock_exists):
    # Mock Connection instead of Server, because Connection is inside the try...except block
    with patch("app.main.Connection", side_effect=Exception("Connection failure")):
        main.process_and_sync_file()
        assert mock_remove.called

def test_process_and_sync_file_not_found():
    with patch("app.main.os.path.exists", return_value=False):
        main.process_and_sync_file()

# ---------------------------------------------------------
# Endpoint Tests
# ---------------------------------------------------------

def test_upsert_endpoint_success(mock_ldap_server, mock_ldap_conn):
    payload = [
        {"username": "1", "name": "Adam"}, 
        {"username": "2", "name": "Bob"},  
        {"username": "3", "name": ""}      
    ]
    response = client.post("/upsert", json=payload)
    assert response.status_code == 200
    assert response.json()["success"] == True

def test_upsert_endpoint_exception(mock_ldap_server, mock_ldap_conn):
    mock_ldap_conn.search.side_effect = Exception("LDAP Error")
    payload = [{"username": "1", "name": "Adam"}]
    response = client.post("/upsert", json=payload)
    assert response.status_code == 500

def test_search_endpoint_found(mock_ldap_server, mock_ldap_conn):
    entry = MagicMock()
    entry.uid = "asmith"
    entry.cn = "Adam Smith"
    entry.mail = "adam@dtic.mil"
    mock_ldap_conn.entries = [entry]
    
    response = client.get("/search?name=Adam Smith")
    assert response.status_code == 200
    assert response.json()["username"] == "asmith"

def test_search_endpoint_not_found(mock_ldap_server, mock_ldap_conn):
    mock_ldap_conn.entries = []
    response = client.get("/search?name=Missing")
    assert response.status_code == 404

def test_similar_emails_endpoint_success(mock_ldap_server, mock_ldap_conn):
    entry1 = MagicMock()
    entry1.cn = "Charlie Test"  
    entry1.mail = "charlie@dtic.mil"
    
    entry2 = MagicMock()
    entry2.cn = "Adam" 
    entry2.mail = "adam@dtic.mil"
    
    entry3 = MagicMock()
    entry3.cn = "Frank NoEmail" 
    entry3.mail = None

    mock_ldap_conn.entries = [entry1, entry2, entry3]

    response = client.get("/similar-emails?name=Charli")
    assert response.status_code == 200
    data = response.json()
    assert len(data["similar_emails"]) == 1
    assert data["similar_emails"][0]["name"] == "Charlie Test"

def test_similar_emails_endpoint_no_candidates(mock_ldap_server, mock_ldap_conn):
    mock_ldap_conn.entries = []
    response = client.get("/similar-emails?name=Charli")
    assert response.status_code == 200
    assert response.json()["similar_emails"] == []

def test_similar_emails_endpoint_low_score(mock_ldap_server, mock_ldap_conn):
    entry = MagicMock()
    entry.cn = "Charlie"
    entry.mail = "c@dtic.mil"
    mock_ldap_conn.entries = [entry]
    
    response = client.get("/similar-emails?name=Xylophone")
    assert response.status_code == 200
    assert response.json()["similar_emails"] == []

def test_similar_emails_endpoint_exception(mock_ldap_server, mock_ldap_conn):
    mock_ldap_conn.search.side_effect = Exception("Search error")
    response = client.get("/similar-emails?name=Test")
    assert response.status_code == 500

def test_sync_file_endpoint():
    with patch("app.main.process_and_sync_file") as mock_sync:
        response = client.post("/sync-file")
        assert response.status_code == 200
        assert response.json() == {"message": "Background sync started."}