"""Test configuration and shared fixtures."""

from unittest.mock import AsyncMock, Mock

import pytest


@pytest.fixture
def mock_milvus_client():
    """Mock Milvus client for testing."""
    client = Mock()
    client.search = AsyncMock(return_value=[])
    client.insert = AsyncMock(return_value={"insert_count": 1})
    return client


@pytest.fixture
def mock_embedding_model():
    """Mock embedding model for testing."""
    model = Mock()
    model.embed = Mock(return_value=[[0.1] * 384])  # 384-dim vector
    return model


@pytest.fixture
def sample_vector():
    """Sample embedding vector for testing."""
    return [0.1] * 384


@pytest.fixture
def sample_search_params():
    """Sample search parameters."""
    return {"query": "machine learning research", "limit": 10, "metric_type": "L2"}


@pytest.fixture
def sample_document():
    """Sample document for insertion."""
    return {
        "id": "doc123",
        "title": "Research Paper Title",
        "abstract": "This is a research paper about machine learning...",
        "authors": ["John Doe"],
        "year": 2025,
    }
