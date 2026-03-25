"""
Additional tests targeting uncovered branches in app/main.py.
Uses unittest.mock to simulate Milvus responses without a live database.
"""
import numpy as np
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from fastapi.testclient import TestClient
from fastapi import HTTPException

import app.main as main_module
from app.main import (
    app,
    get_or_load_model,
    get_model_dimension,
    get_milvus_connection,
    disconnect_milvus,
    initialize_default_collection,
    _upsert_author_embedding,
)
from app.config import settings, AVAILABLE_MODELS

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_collection_caches():
    """Snapshot and restore module-level Milvus caches around each test."""
    original_cols = dict(main_module._loaded_collections)
    original_schema = dict(main_module._collection_schema_cache)
    yield
    main_module._loaded_collections.clear()
    main_module._loaded_collections.update(original_cols)
    main_module._collection_schema_cache.clear()
    main_module._collection_schema_cache.update(original_schema)


# ---------------------------------------------------------------------------
# Simple endpoints (no Milvus required)
# ---------------------------------------------------------------------------

def test_favicon_endpoint():
    """GET /favicon.ico should return 200 with SVG content."""
    response = client.get("/favicon.ico")
    assert response.status_code == 200


def test_docs_endpoint():
    """GET /docs should return the custom Swagger UI HTML page."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_redoc_endpoint():
    """GET /redoc should return the custom ReDoc HTML page."""
    response = client.get("/redoc")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


# ---------------------------------------------------------------------------
# Author embedding – input edge cases
# ---------------------------------------------------------------------------

def test_create_author_embedding_all_whitespace_abstracts():
    """Abstracts that are all whitespace should return 400."""
    response = client.post("/authors/embeddings", json={
        "author_id": "whitespace_author",
        "author_name": "Test Author",
        "abstracts": ["   ", "\t\n", "  "],
    })
    assert response.status_code == 400
    assert "No valid abstracts" in response.json()["detail"]


def test_create_author_embedding_invalid_model_returns_400():
    """An unrecognised model name should return 400."""
    response = client.post("/authors/embeddings", json={
        "author_id": "bad_model_author",
        "author_name": "Test Author",
        "abstracts": ["Some research abstract here."],
        "model_name": "invalid/nonexistent-model-xyz",
    })
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Author embedding – general server error path
# ---------------------------------------------------------------------------

def test_create_author_embedding_general_server_error():
    """If _upsert_author_embedding raises an unexpected exception, return 500."""
    fake_vec = np.array([0.1] * 384)

    with patch("app.main.get_or_load_model") as mock_load, \
         patch("app.main._upsert_author_embedding") as mock_upsert:

        mock_model = MagicMock()
        mock_model.embed.return_value = iter([fake_vec])
        mock_load.return_value = mock_model

        mock_upsert.side_effect = RuntimeError("unexpected DB error")

        response = client.post("/authors/embeddings", json={
            "author_id": "err_author",
            "author_name": "Error Author",
            "abstracts": ["Valid abstract text here."],
        })

    assert response.status_code == 500
    assert "Failed to create author embedding" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Author vector – server error and validation paths
# ---------------------------------------------------------------------------

def test_create_author_vector_general_server_error():
    """If _upsert_author_embedding raises an unexpected exception, return 500."""
    with patch("app.main._upsert_author_embedding") as mock_upsert:
        mock_upsert.side_effect = RuntimeError("unexpected DB error")

        response = client.post("/authors/vector", json={
            "author_id": "err_vector_author",
            "author_name": "Error Author",
            "embedding": [0.1] * 384,
        })

    assert response.status_code == 500
    assert "Failed to create author vector" in response.json()["detail"]


def test_create_author_vector_dimension_mismatch_with_valid_model():
    """Providing an embedding whose length doesn't match the model's dimension returns 400."""
    response = client.post("/authors/vector", json={
        "author_id": "dim_mismatch_author",
        "author_name": "Mismatch Author",
        "embedding": [0.1] * 100,  # all-MiniLM-L6-v2 expects 384
        "model_name": "sentence-transformers/all-MiniLM-L6-v2",
    })
    assert response.status_code == 400
    assert "mismatch" in response.json()["detail"].lower()


def test_create_author_vector_invalid_model_returns_400():
    """An unrecognised model_name for dimension validation returns 400."""
    response = client.post("/authors/vector", json={
        "author_id": "invalid_model_vector",
        "author_name": "Test Author",
        "embedding": [0.1] * 384,
        "model_name": "invalid/no-such-model-xyz",
    })
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /collections  – error path
# ---------------------------------------------------------------------------

def test_list_collections_milvus_error():
    """If utility.list_collections raises, the endpoint returns 500."""
    with patch("app.main.utility") as mock_util:
        mock_util.list_collections.side_effect = Exception("Milvus down")
        response = client.get("/collections")

    assert response.status_code == 500
    assert "Failed to list collections" in response.json()["detail"]


# ---------------------------------------------------------------------------
# GET /collections/{name}  – all paths
# ---------------------------------------------------------------------------

def test_get_collection_info_not_found():
    """A non-existent collection name returns 404."""
    with patch("app.main.utility") as mock_util:
        mock_util.has_collection.return_value = False
        response = client.get("/collections/nonexistent_xyz")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_collection_info_success():
    """A valid collection name returns 200 with collection metadata."""
    with patch("app.main.utility") as mock_util, \
         patch("app.main.Collection") as mock_col_cls:

        mock_util.has_collection.return_value = True
        mock_col = MagicMock()
        mock_col.num_entities = 99
        mock_col.description = "My test collection"
        mock_col_cls.return_value = mock_col

        response = client.get("/collections/my_test_collection")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "my_test_collection"
    assert data["num_entities"] == 99


def test_get_collection_info_milvus_error():
    """If utility.has_collection raises, the endpoint returns 500."""
    with patch("app.main.utility") as mock_util:
        mock_util.has_collection.side_effect = Exception("Milvus error")
        response = client.get("/collections/any_collection")

    assert response.status_code == 500
    assert "Failed to get collection info" in response.json()["detail"]


# ---------------------------------------------------------------------------
# POST /search/vector  – mocked Milvus paths
# ---------------------------------------------------------------------------

def test_vector_search_collection_not_found_mocked():
    """Vector search returns 404 when the target collection does not exist."""
    with patch("app.main.utility") as mock_util:
        mock_util.has_collection.return_value = False
        response = client.post("/search/vector", json={
            "query_vector": [0.1] * 384,
            "collection_name": "missing_col",
        })

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def _make_mock_hit(distance: float, fields: dict) -> MagicMock:
    """Helper to build a pymilvus-like hit mock."""
    hit = MagicMock()
    hit.distance = distance
    entity = MagicMock()
    entity.fields = list(fields.keys())
    entity.get.side_effect = lambda f: fields[f]
    hit.entity = entity
    return hit


def test_vector_search_success_mocked():
    """Vector search returns results when Milvus is happy."""
    hit = _make_mock_hit(0.12, {"author_id": "a1", "author_name": "Alice", "num_abstracts": 3})

    with patch("app.main.utility") as mock_util, \
         patch("app.main.Collection") as mock_col_cls:

        mock_util.has_collection.return_value = True
        mock_col = MagicMock()
        mock_col.search.return_value = [[hit]]
        mock_col_cls.return_value = mock_col

        response = client.post("/search/vector", json={
            "query_vector": [0.1] * 384,
            "limit": 5,
        })

    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert len(data["results"]) == 1
    assert data["results"][0]["distance"] == pytest.approx(0.12)
    assert data["pagination"]["limit"] == 5


def test_vector_search_has_more_pagination():
    """has_more flag is True when there are more results beyond the requested page."""
    # limit=2 → total_needed=3; return 3 hits so has_more is True
    hits = [
        _make_mock_hit(i * 0.1, {"author_id": f"a{i}", "author_name": f"Author {i}", "num_abstracts": i + 1})
        for i in range(3)
    ]

    with patch("app.main.utility") as mock_util, \
         patch("app.main.Collection") as mock_col_cls:

        mock_util.has_collection.return_value = True
        mock_col = MagicMock()
        mock_col.search.return_value = [hits]
        mock_col_cls.return_value = mock_col

        response = client.post("/search/vector", json={
            "query_vector": [0.1] * 384,
            "limit": 2,
            "offset": 0,
        })

    assert response.status_code == 200
    data = response.json()
    assert data["pagination"]["has_more"] is True
    assert len(data["results"]) == 2


def test_vector_search_milvus_error():
    """A Milvus error during search returns 500."""
    with patch("app.main.utility") as mock_util, \
         patch("app.main.Collection") as mock_col_cls:

        mock_util.has_collection.return_value = True
        mock_col = MagicMock()
        mock_col.search.side_effect = Exception("Search failed")
        mock_col_cls.return_value = mock_col

        response = client.post("/search/vector", json={
            "query_vector": [0.1] * 384,
        })

    assert response.status_code == 500
    assert "Failed to perform search" in response.json()["detail"]


# ---------------------------------------------------------------------------
# POST /search/text  – mocked model + Milvus paths
# ---------------------------------------------------------------------------

def test_text_search_invalid_model_returns_400():
    """Text search with an unrecognised model name returns 400."""
    response = client.post("/search/text", json={
        "query_text": "neural networks",
        "model_name": "invalid/no-such-model-xyz",
    })
    assert response.status_code == 400


def test_text_search_collection_not_found_mocked():
    """Text search returns 404 when the target collection does not exist."""
    with patch("app.main.get_or_load_model") as mock_load, \
         patch("app.main.utility") as mock_util:

        mock_load.return_value = MagicMock()
        mock_util.has_collection.return_value = False

        response = client.post("/search/text", json={
            "query_text": "machine learning",
            "collection_name": "missing_text_col",
        })

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_text_search_success_mocked():
    """Text search returns results when model and Milvus are available."""
    fake_embedding = np.array([0.1] * 384)
    hit = _make_mock_hit(0.05, {"author_id": "b1", "author_name": "Bob", "num_abstracts": 4})

    with patch("app.main.get_or_load_model") as mock_load, \
         patch("app.main.utility") as mock_util, \
         patch("app.main.Collection") as mock_col_cls:

        mock_model = MagicMock()
        mock_model.embed.return_value = iter([fake_embedding])
        mock_load.return_value = mock_model

        mock_util.has_collection.return_value = True

        mock_col = MagicMock()
        mock_col.search.return_value = [[hit]]
        mock_col_cls.return_value = mock_col

        response = client.post("/search/text", json={
            "query_text": "machine learning research",
            "limit": 5,
        })

    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "pagination" in data
    assert len(data["results"]) == 1
    assert data["pagination"]["limit"] == 5


def test_text_search_milvus_error():
    """A Milvus error during text search returns 500."""
    fake_embedding = np.array([0.1] * 384)

    with patch("app.main.get_or_load_model") as mock_load, \
         patch("app.main.utility") as mock_util, \
         patch("app.main.Collection") as mock_col_cls:

        mock_model = MagicMock()
        mock_model.embed.return_value = iter([fake_embedding])
        mock_load.return_value = mock_model

        mock_util.has_collection.return_value = True

        mock_col = MagicMock()
        mock_col.search.side_effect = Exception("Search error")
        mock_col_cls.return_value = mock_col

        response = client.post("/search/text", json={
            "query_text": "machine learning",
        })

    assert response.status_code == 500
    assert "Failed to perform search" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Health check – reconnection path
# ---------------------------------------------------------------------------

def test_health_check_reconnects_when_no_connection():
    """Health check should attempt reconnect when has_connection returns False."""
    with patch("app.main.connections") as mock_conn, \
         patch("app.main.utility") as mock_util:

        mock_conn.has_connection.return_value = False
        # After reconnect, list_collections succeeds
        mock_util.list_collections.return_value = ["aegis_vectors"]

        response = client.get("/health")

    # Either healthy (if reconnect succeeded) or unhealthy – both are valid.
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "milvus_connected" in data


# ===========================================================================
# Direct unit tests for helper / lifecycle functions
# ===========================================================================

# ---------------------------------------------------------------------------
# get_or_load_model – RuntimeError path
# ---------------------------------------------------------------------------

def test_get_or_load_model_raises_runtime_error_on_load_failure():
    """If TextEmbedding raises during load, get_or_load_model wraps it in RuntimeError."""
    # Remove the model from cache so it will be re-loaded
    original = main_module.embedding_models.pop(
        "sentence-transformers/all-MiniLM-L6-v2", None
    )
    try:
        with patch("app.main.TextEmbedding", side_effect=Exception("ONNX load error")):
            with pytest.raises(RuntimeError, match="Failed to load model"):
                get_or_load_model("sentence-transformers/all-MiniLM-L6-v2")
    finally:
        if original is not None:
            main_module.embedding_models["sentence-transformers/all-MiniLM-L6-v2"] = original


# ---------------------------------------------------------------------------
# get_model_dimension – fallthrough to get_sentence_embedding_dimension
# ---------------------------------------------------------------------------

def test_get_model_dimension_uses_get_sentence_embedding_dimension():
    """When dimension is None in config, load the model and call get_sentence_embedding_dimension."""
    model_name = "sentence-transformers/all-MiniLM-L6-v2"

    # Temporarily set dimension to None in AVAILABLE_MODELS and clear caches
    original_dim = AVAILABLE_MODELS[model_name]["dimension"]
    AVAILABLE_MODELS[model_name]["dimension"] = None
    main_module.model_dimensions.pop(model_name, None)
    main_module.embedding_models.pop(model_name, None)

    try:
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        with patch("app.main.TextEmbedding", return_value=mock_model):
            dim = get_model_dimension(model_name)
        assert dim == 384
        mock_model.get_sentence_embedding_dimension.assert_called_once()
    finally:
        AVAILABLE_MODELS[model_name]["dimension"] = original_dim
        main_module.model_dimensions.pop(model_name, None)
        main_module.embedding_models.pop(model_name, None)


# ---------------------------------------------------------------------------
# get_milvus_connection – exception path
# ---------------------------------------------------------------------------

def test_get_milvus_connection_returns_false_on_error():
    """If connections.connect raises, get_milvus_connection returns False."""
    with patch("app.main.connections") as mock_conn:
        mock_conn.connect.side_effect = Exception("Connection refused")
        result = get_milvus_connection()
    assert result is False


# ---------------------------------------------------------------------------
# disconnect_milvus – both paths
# ---------------------------------------------------------------------------

def test_disconnect_milvus_success():
    """disconnect_milvus calls connections.disconnect without raising."""
    with patch("app.main.connections") as mock_conn:
        disconnect_milvus()  # should not raise
        mock_conn.disconnect.assert_called_once_with("default")


def test_disconnect_milvus_handles_exception():
    """disconnect_milvus swallows exceptions from connections.disconnect."""
    with patch("app.main.connections") as mock_conn:
        mock_conn.disconnect.side_effect = Exception("Disconnect error")
        disconnect_milvus()  # should not raise


# ---------------------------------------------------------------------------
# initialize_default_collection –
# ---------------------------------------------------------------------------

def test_initialize_default_collection_already_exists():
    """When collection already exists, the function logs and returns without creating."""
    with patch("app.main.utility") as mock_util:
        mock_util.has_collection.return_value = True
        initialize_default_collection()  # should not raise


def test_initialize_default_collection_creates_new():
    """When collection does not exist, it creates schema and index."""
    with patch("app.main.utility") as mock_util, \
         patch("app.main.Collection") as mock_col_cls:

        mock_util.has_collection.return_value = False
        main_module.model_dimensions[settings.default_embedding_model] = 384

        mock_col = MagicMock()
        mock_col_cls.return_value = mock_col

        initialize_default_collection()

        mock_col.create_index.assert_called_once()


def test_initialize_default_collection_skips_when_model_fails():
    """If model cannot be loaded, initialization returns early without creating collection."""
    with patch("app.main.utility") as mock_util, \
         patch("app.main.get_or_load_model", side_effect=RuntimeError("no model")):

        mock_util.has_collection.return_value = False
        # Remove dimension from cache so fallback to loading the model is attempted
        main_module.model_dimensions.pop(settings.default_embedding_model, None)

        initialize_default_collection()  # should not raise; returns early


def test_initialize_default_collection_outer_exception():
    """If utility.has_collection raises, the outer except catches it without crashing."""
    with patch("app.main.utility") as mock_util:
        mock_util.has_collection.side_effect = Exception("Milvus gone")
        initialize_default_collection()  # should not raise


# ---------------------------------------------------------------------------
# lifespan – collection pre-load path
# ---------------------------------------------------------------------------

def test_lifespan_preloads_collection_when_it_exists():
    """Lifespan caches collection + schema when the default collection exists at startup."""
    main_module._loaded_collections.clear()
    main_module._collection_schema_cache.clear()

    mock_col = MagicMock()
    mock_col.schema.to_dict.return_value = {
        "fields": [{"name": "embedding", "params": {"dim": 384}}]
    }

    with patch("app.main.get_milvus_connection"), \
         patch("app.main.initialize_default_collection"), \
         patch("app.main.utility") as mock_util, \
         patch("app.main.Collection", return_value=mock_col):

        mock_util.has_collection.return_value = True

        with TestClient(app) as c:
            resp = c.get("/")
            assert resp.status_code == 200

    # Schema should have been cached during startup
    assert settings.default_collection in main_module._collection_schema_cache


def test_lifespan_handles_preload_exception():
    """Lifespan does not crash when pre-loading the collection raises an exception."""
    main_module._loaded_collections.clear()
    main_module._collection_schema_cache.clear()

    with patch("app.main.get_milvus_connection"), \
         patch("app.main.initialize_default_collection"), \
         patch("app.main.utility") as mock_util:

        mock_util.has_collection.side_effect = Exception("preload boom")

        with TestClient(app) as c:
            resp = c.get("/")
            assert resp.status_code == 200


def test_lifespan_model_load_failure_at_startup():
    """Lifespan continues even if the default model fails to load at startup."""
    main_module._loaded_collections.clear()
    main_module._collection_schema_cache.clear()

    with patch("app.main.get_milvus_connection"), \
         patch("app.main.get_or_load_model", side_effect=RuntimeError("no onnx")), \
         patch("app.main.initialize_default_collection"), \
         patch("app.main.utility") as mock_util:

        mock_util.has_collection.return_value = False

        with TestClient(app) as c:
            resp = c.get("/health")
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# _upsert_author_embedding – uncovered branches
# ---------------------------------------------------------------------------

def _make_collection_mock(dim: int = 384, query_result=None) -> MagicMock:
    """Build a fully-spec'd Collection mock for _upsert_author_embedding."""
    col = MagicMock()
    col.schema.to_dict.return_value = {
        "fields": [{"name": "embedding", "params": {"dim": dim}}]
    }
    col.query.return_value = query_result if query_result is not None else []
    return col


def test_upsert_uses_cached_collection_with_reconnect():
    """When cached collection.num_entities raises, the collection is reloaded."""
    col_name = "test_reconnect_col"
    main_module._collection_schema_cache[col_name] = {"embedding_dim": 384}

    stale_col = MagicMock()
    # Accessing .num_entities raises (simulates lost connection)
    type(stale_col).num_entities = PropertyMock(side_effect=Exception("lost connection"))

    fresh_col = _make_collection_mock(dim=384)

    main_module._loaded_collections[col_name] = stale_col

    with patch("app.main.Collection", return_value=fresh_col):
        is_update, action = _upsert_author_embedding(
            col_name, "auth1", "Author One", [0.1] * 384, 3
        )

    assert action in ("created", "updated")
    # Cache should now point at the fresh collection
    assert main_module._loaded_collections[col_name] is fresh_col


def test_upsert_loads_uncached_collection():
    """When collection is not in cache, it is loaded and cached."""
    col_name = "test_uncached_col"
    # Ensure not in cache
    main_module._loaded_collections.pop(col_name, None)
    main_module._collection_schema_cache[col_name] = {"embedding_dim": 384}

    mock_col = _make_collection_mock(dim=384)

    with patch("app.main.utility") as mock_util, \
         patch("app.main.Collection", return_value=mock_col):

        mock_util.has_collection.return_value = True
        is_update, action = _upsert_author_embedding(
            col_name, "auth2", "Author Two", [0.2] * 384, 5
        )

    assert col_name in main_module._loaded_collections
    assert action in ("created", "updated")


def test_upsert_fetches_schema_when_not_cached():
    """When schema is not cached, it is fetched from collection and cached."""
    col_name = "test_schema_fetch_col"
    main_module._loaded_collections.pop(col_name, None)
    main_module._collection_schema_cache.pop(col_name, None)

    mock_col = _make_collection_mock(dim=384)

    with patch("app.main.utility") as mock_util, \
         patch("app.main.Collection", return_value=mock_col):

        mock_util.has_collection.return_value = True
        _upsert_author_embedding(col_name, "auth3", "Author Three", [0.3] * 384, 2)

    assert col_name in main_module._collection_schema_cache
    assert main_module._collection_schema_cache[col_name]["embedding_dim"] == 384


def test_upsert_raises_500_when_schema_missing_embedding_field():
    """If schema has no 'embedding' field, raises HTTP 500."""
    col_name = "test_no_embed_field_col"
    main_module._loaded_collections.pop(col_name, None)
    main_module._collection_schema_cache.pop(col_name, None)

    mock_col = MagicMock()
    mock_col.schema.to_dict.return_value = {"fields": [{"name": "author_id", "params": {}}]}

    with patch("app.main.utility") as mock_util, \
         patch("app.main.Collection", return_value=mock_col):

        mock_util.has_collection.return_value = True
        with pytest.raises(HTTPException) as exc_info:
            _upsert_author_embedding(col_name, "auth4", "Author Four", [0.4] * 384, 1)

    assert exc_info.value.status_code == 500


def test_upsert_query_failure_defaults_to_new_insert():
    """If collection.query raises, is_update defaults to False (treated as new insert)."""
    col_name = "test_query_fail_col"
    main_module._collection_schema_cache[col_name] = {"embedding_dim": 384}

    mock_col = _make_collection_mock(dim=384)
    mock_col.query.side_effect = Exception("query failed")

    main_module._loaded_collections[col_name] = mock_col

    is_update, action = _upsert_author_embedding(
        col_name, "auth5", "Author Five", [0.5] * 384, 4
    )
    assert is_update is False
    assert action == "created"


def test_upsert_returns_is_update_true_for_existing_author():
    """When query finds an existing entity, action is 'updated'."""
    col_name = "test_existing_author_col"
    main_module._collection_schema_cache[col_name] = {"embedding_dim": 384}

    mock_col = _make_collection_mock(dim=384, query_result=[{"id": "existing_auth"}])
    main_module._loaded_collections[col_name] = mock_col

    is_update, action = _upsert_author_embedding(
        col_name, "existing_auth", "Author Six", [0.6] * 384, 7
    )
    assert is_update is True
    assert action == "updated"
