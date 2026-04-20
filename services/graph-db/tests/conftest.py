from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_neo4j_session():
    """Mock a Neo4j session and its run method."""
    session = MagicMock()
    mock_result = MagicMock()
    mock_result.__iter__.return_value = []
    session.run.return_value = mock_result
    return session


@pytest.fixture
def mock_neo4j_driver(mock_neo4j_session):
    """Mock the Neo4j driver and its session() method."""
    driver = MagicMock()
    driver.close.return_value = None
    driver.session.return_value.__enter__.return_value = mock_neo4j_session
    return driver


@pytest.fixture
def client(mock_neo4j_driver):
    """Create a TestClient with the Neo4j driver patched and lifespan handled."""
    with patch("app.main.get_driver", return_value=mock_neo4j_driver):
        from app.main import app

        with TestClient(app) as test_client:
            yield test_client
