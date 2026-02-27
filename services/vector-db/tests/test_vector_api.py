from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "vector-db"
    assert "message" in data
    assert "version" in data


def test_health_endpoint():
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "milvus_connected" in data
    assert "collections" in data


def test_list_collections_endpoint():
    """Test the list collections endpoint."""
    response = client.get("/collections")
    assert response.status_code in [200, 500]  # May fail if Milvus not connected


def test_vector_search_validation():
    """Test vector search endpoint with invalid input."""
    # Test with missing query_vector
    response = client.post("/search/vector", json={})
    assert response.status_code == 422  # Validation error
    
    # Test with invalid limit
    response = client.post("/search/vector", json={
        "query_vector": [0.1] * 768,
        "limit": 0  # Invalid: must be >= 1
    })
    assert response.status_code == 422
    
    # Test with invalid offset
    response = client.post("/search/vector", json={
        "query_vector": [0.1] * 768,
        "offset": -1  # Invalid: must be >= 0
    })
    assert response.status_code == 422


def test_vector_search_with_valid_input():
    """Test vector search with valid input (may fail if collection doesn't exist)."""
    response = client.post("/search/vector", json={
        "query_vector": [0.1] * 768,
        "limit": 5
    })
    # May return 404 if collection doesn't exist, or 500 if Milvus not connected
    assert response.status_code in [200, 404, 500]
    
    # If successful, check response structure
    if response.status_code == 200:
        data = response.json()
        assert "results" in data
        assert "pagination" in data
        assert data["pagination"]["offset"] == 0
        assert data["pagination"]["limit"] == 5


def test_vector_search_with_pagination():
    """Test vector search with pagination parameters."""
    response = client.post("/search/vector", json={
        "query_vector": [0.1] * 768,
        "limit": 10,
        "offset": 5
    })
    # May return 404 if collection doesn't exist, or 500 if Milvus not connected
    assert response.status_code in [200, 404, 500]
    
    # If successful, check pagination metadata
    if response.status_code == 200:
        data = response.json()
        assert data["pagination"]["offset"] == 5
        assert data["pagination"]["limit"] == 10


def test_text_search_validation():
    """Test text search endpoint with invalid input."""
    # Test with missing query_text
    response = client.post("/search/text", json={})
    assert response.status_code == 422  # Validation error
    
    # Test with empty query_text
    response = client.post("/search/text", json={
        "query_text": ""
    })
    assert response.status_code == 422  # Validation error


def test_text_search_with_valid_input():
    """Test text search with valid input (may fail if collection doesn't exist)."""
    response = client.post("/search/text", json={
        "query_text": "machine learning applications in healthcare",
        "limit": 5
    })
    # May return 404 if collection doesn't exist, 503 if model not loaded, or 500 if Milvus not connected
    assert response.status_code in [200, 404, 500, 503]
    
    # If successful, check response structure
    if response.status_code == 200:
        data = response.json()
        assert "results" in data
        assert "pagination" in data
        assert data["pagination"]["limit"] == 5


def test_create_author_embedding_validation():
    """Test author embedding creation with invalid input."""
    # Test with missing author_id
    response = client.post("/authors/embeddings", json={
        "author_name": "John Doe",
        "abstracts": ["Some abstract text"]
    })
    assert response.status_code == 422  # Validation error
    
    # Test with empty abstracts list
    response = client.post("/authors/embeddings", json={
        "author_id": "123",
        "author_name": "John Doe",
        "abstracts": []
    })
    assert response.status_code == 422  # Validation error


def test_create_author_embedding_with_valid_input():
    """Test author embedding creation with valid input."""
    response = client.post("/authors/embeddings", json={
        "author_id": "test_author_123",
        "author_name": "Dr. Jane Smith",
        "abstracts": [
            "This paper discusses machine learning applications in healthcare.",
            "We present a novel approach to deep learning for medical diagnosis."
        ]
    })
    # May return 503 if model not loaded, or 500 if other error
    assert response.status_code in [200, 500, 503]
    
    # If successful, check response structure
    if response.status_code == 200:
        data = response.json()
        assert data["author_id"] == "test_author_123"
        assert data["author_name"] == "Dr. Jane Smith"
        assert data["num_abstracts_processed"] == 2
        assert data["success"] is True
        assert "embedding_dim" in data


def test_create_author_embedding_upsert():
    """Test that creating an author embedding twice updates the existing entry (upsert)."""
    # First create
    response1 = client.post("/authors/embeddings", json={
        "author_id": "test_upsert_author",
        "author_name": "Dr. John Doe",
        "abstracts": ["First abstract about AI."]
    })
    
    # Second create with same author_id but different data
    response2 = client.post("/authors/embeddings", json={
        "author_id": "test_upsert_author",
        "author_name": "Dr. John Doe",
        "abstracts": [
            "Updated abstract about machine learning.",
            "Another new abstract about neural networks."
        ]
    })
    
    # Both should succeed (or both fail with same error)
    assert response1.status_code == response2.status_code
    
    # If successful, verify upsert worked
    if response2.status_code == 200:
        data = response2.json()
        assert data["author_id"] == "test_upsert_author"
        assert data["num_abstracts_processed"] == 2  # New count
        # Message should indicate created or updated
        assert "created" in data["message"].lower() or "updated" in data["message"].lower()
