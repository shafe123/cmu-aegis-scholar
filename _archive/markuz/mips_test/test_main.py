import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app) #

def test_bulk_upsert_generates_emails():
    """Verify that records without emails are accepted and processed."""
    payload = [
        {"username": "test_jdoe", "name": "John Doe"},
        {"username": "test_asmith", "name": "Alice Smith"}
    ]
    response = client.post("/upsert", json=payload)
    assert response.status_code == 200 #
    assert response.json()["success"] is True

def test_search_finds_generated_record():
    """Confirm the generated record is searchable and has an email."""
    # Ensure the user exists first
    client.post("/upsert", json=[{"username": "search_test", "name": "Search Test"}])
    
    response = client.get("/search?name=Search%20Test")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Search Test"
    assert "email" in data and data["email"] is not None # Verifies generation

def test_sync_file_endpoint():
    """Test that the sync-file background task is triggered correctly."""
    response = client.post("/sync-file")
    assert response.status_code == 200
    assert "Background sync started" in response.json()["message"]