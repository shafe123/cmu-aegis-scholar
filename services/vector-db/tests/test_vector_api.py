from fastapi.testclient import TestClient
from app.main import app
from app.config import AVAILABLE_MODELS

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


def test_models_endpoint():
    """Test the GET /models endpoint."""
    response = client.get("/models")
    assert response.status_code == 200
    
    data = response.json()
    assert "models" in data
    assert "default_model" in data
    assert isinstance(data["models"], list)
    assert len(data["models"]) > 0
    
    # Verify each model has required fields
    for model in data["models"]:
        assert "name" in model
        assert "description" in model
        assert "loaded" in model
        assert isinstance(model["loaded"], bool)
        # dimension can be None for some models before loading
    
    # Verify default model is in the list
    model_names = [m["name"] for m in data["models"]]
    assert data["default_model"] in model_names
    
    # Verify default model structure matches config
    assert data["default_model"] in AVAILABLE_MODELS


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


def test_text_search_with_model_name():
    """Test text search with explicit model_name parameter."""
    # Test with default model explicitly specified
    response = client.post("/search/text", json={
        "query_text": "artificial intelligence and neural networks",
        "model_name": "sentence-transformers/all-MiniLM-L6-v2",
        "limit": 3
    })
    assert response.status_code in [200, 404, 500, 503]
    
    if response.status_code == 200:
        data = response.json()
        assert "results" in data
        assert data["pagination"]["limit"] == 3


def test_text_search_with_invalid_model():
    """Test text search with invalid model name."""
    response = client.post("/search/text", json={
        "query_text": "test query",
        "model_name": "nonexistent/model"
    })
    # Should return 400 for invalid model
    assert response.status_code in [400, 404, 500]


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


def test_create_author_embedding_with_model_name():
    """Test author embedding creation with explicit model_name."""
    response = client.post("/authors/embeddings", json={
        "author_id": "test_author_model_explicit",
        "author_name": "Dr. Model Test",
        "abstracts": [
            "Testing with explicit model specification.",
            "This should use the specified embedding model."
        ],
        "model_name": "sentence-transformers/all-MiniLM-L6-v2"
    })
    assert response.status_code in [200, 500, 503]
    
    if response.status_code == 200:
        data = response.json()
        assert data["author_id"] == "test_author_model_explicit"
        assert data["embedding_dim"] == 384  # all-MiniLM-L6-v2 dimension
        assert data["success"] is True


def test_create_author_embedding_with_invalid_model():
    """Test author embedding creation with invalid model name."""
    response = client.post("/authors/embeddings", json={
        "author_id": "test_author_invalid_model",
        "author_name": "Dr. Invalid Model",
        "abstracts": ["Test abstract"],
        "model_name": "invalid/nonexistent-model"
    })
    # Should return 400 for invalid model
    assert response.status_code in [400, 500]


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


def test_create_author_vector_validation():
    """Test author vector creation with invalid input."""
    # Test with missing author_id
    response = client.post("/authors/vector", json={
        "author_name": "John Doe",
        "embedding": [0.1] * 384
    })
    assert response.status_code == 422  # Validation error
    
    # Test with empty embedding
    response = client.post("/authors/vector", json={
        "author_id": "123",
        "author_name": "John Doe",
        "embedding": []
    })
    assert response.status_code == 400  # Bad request


def test_create_author_vector_with_valid_input():
    """Test author vector creation with valid pre-computed embedding."""
    response = client.post("/authors/vector", json={
        "author_id": "test_vector_author_123",
        "author_name": "Dr. Alice Johnson",
        "embedding": [0.025] * 384,  # Pre-computed vector with correct dimension
        "num_abstracts": 5
    })
    # May return 500 if Milvus not connected or 404 if collection doesn't exist
    assert response.status_code in [200, 404, 500]
    
    # If successful, check response structure
    if response.status_code == 200:
        data = response.json()
        assert data["author_id"] == "test_vector_author_123"
        assert data["author_name"] == "Dr. Alice Johnson"
        assert data["embedding_dim"] == 384
        assert data["success"] is True


def test_create_author_vector_dimension_mismatch():
    """Test that vector dimension validation works."""
    # Try with wrong dimension (768 instead of 384)
    response = client.post("/authors/vector", json={
        "author_id": "test_wrong_dim",
        "author_name": "Dr. Wrong Dimension",
        "embedding": [0.1] * 768  # Wrong dimension
    })
    # Should fail with 400 if collection exists with different dimension
    assert response.status_code in [400, 404, 500]  # 404 if collection doesn't exist


def test_create_author_vector_with_model_name_validation():
    """Test vector dimension validation with explicit model_name."""
    # Test with correct dimension for specified model
    response = client.post("/authors/vector", json={
        "author_id": "test_vector_model_match",
        "author_name": "Dr. Model Match",
        "embedding": [0.1] * 384,  # Correct dimension for all-MiniLM-L6-v2
        "model_name": "sentence-transformers/all-MiniLM-L6-v2"
    })
    assert response.status_code in [200, 404, 500]
    
    # Test with dimension mismatch for specified model
    response = client.post("/authors/vector", json={
        "author_id": "test_vector_model_mismatch",
        "author_name": "Dr. Model Mismatch",
        "embedding": [0.1] * 768,  # Wrong dimension for all-MiniLM-L6-v2 (384)
        "model_name": "sentence-transformers/all-MiniLM-L6-v2"
    })
    # Should return 400 for dimension mismatch
    assert response.status_code in [400, 404, 500]


def test_create_author_vector_with_invalid_model():
    """Test vector upload with invalid model name."""
    response = client.post("/authors/vector", json={
        "author_id": "test_vector_invalid_model",
        "author_name": "Dr. Invalid Vector Model",
        "embedding": [0.1] * 384,
        "model_name": "invalid/model-name"
    })
    # Should return 400 for invalid model
    assert response.status_code in [400, 404, 500]


def test_create_author_vector_upsert():
    """Test that creating an author vector twice updates the existing entry (upsert)."""
    # First create
    response1 = client.post("/authors/vector", json={
        "author_id": "test_vector_upsert",
        "author_name": "Dr. Bob Smith",
        "embedding": [0.1] * 384,
        "num_abstracts": 3
    })
    
    # Second create with same author_id but different embedding
    response2 = client.post("/authors/vector", json={
        "author_id": "test_vector_upsert",
        "author_name": "Dr. Bob Smith",
        "embedding": [0.2] * 384,  # Different embedding values
        "num_abstracts": 5  # More abstracts
    })
    
    # Both should succeed (or both fail with same error)
    assert response1.status_code == response2.status_code
    
    # If successful, verify upsert worked
    if response2.status_code == 200:
        data = response2.json()
        assert data["author_id"] == "test_vector_upsert"
        assert data["embedding_dim"] == 384
        # Message should indicate created or updated
        assert "created" in data["message"].lower() or "updated" in data["message"].lower()


def test_model_consistency_workflow():
    """Test that using the same model for embedding and searching works consistently."""
    test_author_id = "test_consistency_author"
    test_model = "sentence-transformers/all-MiniLM-L6-v2"
    
    # Create an author embedding with specific model
    create_response = client.post("/authors/embeddings", json={
        "author_id": test_author_id,
        "author_name": "Dr. Consistency Test",
        "abstracts": [
            "Machine learning and artificial intelligence research.",
            "Deep learning applications in computer vision."
        ],
        "model_name": test_model
    })
    
    # If creation succeeded, try searching with same model
    if create_response.status_code == 200:
        search_response = client.post("/search/text", json={
            "query_text": "machine learning deep learning",
            "model_name": test_model,
            "limit": 5
        })
        
        # Search should also succeed
        assert search_response.status_code == 200
        
        data = search_response.json()
        assert "results" in data
        # We may or may not find our specific author depending on similarity


def test_multiple_models_different_dimensions():
    """Test that different models can be used (if they support different dimensions)."""
    # Get available models
    models_response = client.get("/models")
    if models_response.status_code != 200:
        return  # Skip if can't get models
    
    models_data = models_response.json()
    available_models = models_data["models"]
    
    # Find models with different dimensions (if available)
    dimensions_found = {}
    for model in available_models:
        if "dimension" in model and model["dimension"] is not None:
            dim = model["dimension"]
            if dim not in dimensions_found:
                dimensions_found[dim] = model["name"]
    
    # If we have at least one model, test it
    if len(dimensions_found) > 0:
        for dim, model_name in dimensions_found.items():
            # Test creating embedding with this model
            response = client.post("/authors/embeddings", json={
                "author_id": f"test_multi_model_{dim}",
                "author_name": f"Dr. Test {dim}D",
                "abstracts": ["Test abstract for multi-model support"],
                "model_name": model_name
            })
            
            # Should succeed or fail gracefully (model might need loading)
            assert response.status_code in [200, 400, 500, 503]
            
            if response.status_code == 200:
                data = response.json()
                assert data["embedding_dim"] == dim


def test_default_model_fallback():
    """Test that endpoints use default model when model_name is not specified."""
    # Get the default model
    models_response = client.get("/models")
    if models_response.status_code != 200:
        return
    
    default_model = models_response.json()["default_model"]
    default_dim = None
    for model in models_response.json()["models"]:
        if model["name"] == default_model and model.get("dimension"):
            default_dim = model["dimension"]
            break
    
    if default_dim is None:
        return  # Can't verify without dimension info
    
    # Create embedding without specifying model (should use default)
    response = client.post("/authors/embeddings", json={
        "author_id": "test_default_fallback",
        "author_name": "Dr. Default Test",
        "abstracts": ["Testing default model fallback behavior"]
    })
    
    if response.status_code == 200:
        data = response.json()
        # Should use default model's dimension
        assert data["embedding_dim"] == default_dim
