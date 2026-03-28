from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_neo4j_session():
    """
    Mock a Neo4j session and its run method.
    Provides a mock result object that can be used for single() or iteration.
    """
    session = MagicMock()
    
    # Mock the return value of session.run() to be a Mock Result
    mock_result = MagicMock()
    
    # Ensure it returns an empty list by default if iterated
    mock_result.__iter__.return_value = []
    
    session.run.return_value = mock_result
    return session
def mock_neo4j_session():
    """
    Mock a Neo4j session and its run method.
    Provides a mock result object that can be used for single() or iteration.
    """
    session = MagicMock()
    
    # Mock the return value of session.run() to be a Mock Result
    mock_result = MagicMock()
    
    # Ensure it returns an empty list by default if iterated
    mock_result.__iter__.return_value = []
    
    session.run.return_value = mock_result
    return session

@pytest.fixture
def mock_neo4j_driver(mock_neo4j_session):
    """
    Mock the Neo4j driver.
    1. Handles the 'with driver.session() as session:' context manager.
    2. Mocks the .close() method to prevent DeprecationWarnings in tests.
    """
    driver = MagicMock()
    
    # Mocking close() prevents the 'Driver destructor' warning during pytest teardown
    driver.close.return_value = None 
    
    # This specifically mocks the context manager pattern used in app/main.py
    # driver.session() -> returns a mock -> __enter__ returns the session mock
    driver.session.return_value.__enter__.return_value = mock_neo4j_session
    
    return driver
def mock_neo4j_driver(mock_neo4j_session):
    """
    Mock the Neo4j driver.
    1. Handles the 'with driver.session() as session:' context manager.
    2. Mocks the .close() method to prevent DeprecationWarnings in tests.
    """
    driver = MagicMock()
    
    # Mocking close() prevents the 'Driver destructor' warning during pytest teardown
    driver.close.return_value = None 
    
    # This specifically mocks the context manager pattern used in app/main.py
    # driver.session() -> returns a mock -> __enter__ returns the session mock
    driver.session.return_value.__enter__.return_value = mock_neo4j_session
    
    return driver

@pytest.fixture
def client(mock_neo4j_driver):
    """
    Create a FastAPI TestClient with the global database driver patched.
    
    We use 'patch' to swap the real Neo4j driver in app.main with our 
    mock_neo4j_driver before the app starts.
    """
    # We target 'app.main.driver' because that is where the 
    # GraphDatabase.driver instance lives in your code.
    with patch("app.main.driver", mock_neo4j_driver):
        from app.main import app
        # yield allows the test to run, then performs cleanup after
        yield TestClient(app)
def client(mock_neo4j_driver):
    """
    Create a FastAPI TestClient with the global database driver patched.
    
    We use 'patch' to swap the real Neo4j driver in app.main with our 
    mock_neo4j_driver before the app starts.
    """
    # We target 'app.main.driver' because that is where the 
    # GraphDatabase.driver instance lives in your code.
    with patch("app.main.driver", mock_neo4j_driver):
        from app.main import app
        # yield allows the test to run, then performs cleanup after
        yield TestClient(app)