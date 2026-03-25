"""Test configuration and shared fixtures for graph-loader."""
import pytest
from unittest.mock import Mock, AsyncMock


@pytest.fixture
def mock_http_client():
    """Mock HTTP client for API calls."""
    client = AsyncMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    return client


@pytest.fixture
def mock_neo4j_client():
    """Mock Neo4j client for graph operations."""
    client = Mock()
    client.execute_query = AsyncMock()
    return client


@pytest.fixture
def sample_dtic_author():
    """Sample DTIC author data."""
    return {
        "id": "A123456",
        "display_name": "Dr. Jane Smith",
        "affiliation": "Defense Research Lab",
        "works_count": 25
    }


@pytest.fixture
def sample_dtic_work():
    """Sample DTIC work data."""
    return {
        "id": "W789012",
        "title": "Advanced Defense Systems Research",
        "authors": ["A123456", "A234567"],
        "topics": ["T111", "T222"],
        "year": 2025
    }


@pytest.fixture
def sample_dtic_organization():
    """Sample DTIC organization data."""
    return {
        "id": "O555555",
        "display_name": "Carnegie Mellon University",
        "type": "education",
        "country": "US"
    }


@pytest.fixture
def sample_batch_data():
    """Sample batch of records for testing."""
    return [
        {"id": "1", "name": "Record 1"},
        {"id": "2", "name": "Record 2"},
        {"id": "3", "name": "Record 3"},
    ]
