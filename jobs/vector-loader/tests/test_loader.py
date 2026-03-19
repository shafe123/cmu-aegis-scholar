"""Tests for vector loader job."""
import pytest
from unittest.mock import Mock, patch, MagicMock

from app.loader import VectorDBClient, VectorLoader
from app.config import Settings


@patch('httpx.Client')
def test_vector_db_client_health_check(mock_client):
    """Test VectorDBClient health check."""
    mock_response = Mock()
    mock_response.json.return_value = {"status": "healthy"}
    mock_client.return_value.get.return_value = mock_response
    
    client = VectorDBClient("http://test:8002")
    result = client.check_health()
    
    assert result is True


@patch('httpx.Client')
def test_vector_db_client_get_collection_info(mock_client):
    """Test getting collection info."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"name": "test", "num_entities": 100}
    mock_client.return_value.get.return_value = mock_response
    
    client = VectorDBClient("http://test:8002")
    info = client.get_collection_info("test_collection")
    
    assert info is not None
    assert info["num_entities"] == 100


@patch('httpx.Client')
def test_should_skip_loading_with_data(mock_client):
    """Test should_skip_loading when collection has data."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"name": "test", "num_entities": 1000}
    mock_client.return_value.get.return_value = mock_response
    
    with patch('app.loader.settings') as mock_settings:
        mock_settings.vector_db_url = "http://test:8002"
        mock_settings.vector_db_timeout = 300
        mock_settings.data_dir = "/tmp/test"
        mock_settings.collection_name = "test"
        mock_settings.skip_if_loaded = True
        mock_settings.min_entities_threshold = 100
        
        loader = VectorLoader()
        assert loader.should_skip_loading() is True


@patch('httpx.Client')
def test_should_skip_loading_below_threshold(mock_client):
    """Test should_skip_loading when collection has data below threshold."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"name": "test", "num_entities": 50}
    mock_client.return_value.get.return_value = mock_response
    
    with patch('app.loader.settings') as mock_settings:
        mock_settings.vector_db_url = "http://test:8002"
        mock_settings.vector_db_timeout = 300
        mock_settings.data_dir = "/tmp/test"
        mock_settings.collection_name = "test"
        mock_settings.skip_if_loaded = True
        mock_settings.min_entities_threshold = 100
        
        loader = VectorLoader()
        assert loader.should_skip_loading() is False
