"""Test configuration and shared fixtures."""
import pytest
from unittest.mock import Mock


@pytest.fixture
def mock_neo4j_driver():
    """Mock Neo4j driver for testing."""
    driver = Mock()
    # Add mock methods as needed
    # driver.session.return_value = mock_session
    return driver


@pytest.fixture
def sample_author_node():
    """Sample author node data for testing."""
    return {
        "id": "author123",
        "label": "Author",
        "properties": {
            "name": "John Doe",
            "affiliation": "Carnegie Mellon University",
            "email": "jdoe@cmu.edu"
        }
    }


@pytest.fixture
def sample_work_node():
    """Sample work node data for testing."""
    return {
        "id": "work456",
        "label": "Work",
        "properties": {
            "title": "Research on AI Systems",
            "year": 2026,
            "doi": "10.1234/example"
        }
    }
