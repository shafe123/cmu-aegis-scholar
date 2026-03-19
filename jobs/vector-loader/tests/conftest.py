"""Test configuration."""
import pytest


@pytest.fixture
def mock_settings():
    """Provide mock settings for tests."""
    from app.config import Settings
    return Settings(
        vector_db_url="http://test:8002",
        data_dir="/tmp/test_data",
        collection_name="test_collection",
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
        skip_if_loaded=True,
        min_entities_threshold=100
    )
