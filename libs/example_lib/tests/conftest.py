"""Test configuration and shared fixtures for example_lib."""
import pytest


@pytest.fixture
def sample_data():
    """Sample data for testing library functions."""
    return {
        "id": "123",
        "name": "Test Item",
        "value": 42
    }


@pytest.fixture
def sample_list():
    """Sample list for testing."""
    return [1, 2, 3, 4, 5]


@pytest.fixture
def sample_dict_list():
    """Sample list of dictionaries."""
    return [
        {"id": "1", "name": "Item 1"},
        {"id": "2", "name": "Item 2"},
        {"id": "3", "name": "Item 3"},
    ]
