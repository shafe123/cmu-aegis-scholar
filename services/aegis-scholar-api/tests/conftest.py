"""Test configuration and shared fixtures."""

from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def mock_vector_db_client():
    """Mock vector database client for testing."""
    client = AsyncMock()
    client.search.return_value = {"results": [], "total": 0}
    return client


@pytest.fixture
def mock_graph_db_client():
    """Mock graph database client for testing."""
    client = AsyncMock()
    return client


@pytest.fixture
def sample_search_query():
    """Sample search query for testing."""
    return {"query": "machine learning", "filters": {"year_min": 2020, "year_max": 2026}, "limit": 10}


@pytest.fixture
def sample_author_result():
    """Sample author search result."""
    return {
        "id": "A123456",
        "display_name": "John Doe",
        "affiliation": "Carnegie Mellon University",
        "works_count": 42,
        "cited_by_count": 1234,
        "relevance_score": 0.95,
    }


@pytest.fixture
def sample_work_result():
    """Sample work search result."""
    return {
        "id": "W987654",
        "title": "Advances in Machine Learning Systems",
        "authors": ["John Doe", "Jane Smith"],
        "year": 2025,
        "cited_by_count": 56,
        "relevance_score": 0.89,
    }
