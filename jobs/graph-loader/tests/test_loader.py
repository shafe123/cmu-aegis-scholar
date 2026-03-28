from unittest.mock import MagicMock, patch

from app.loader import GraphDBClient, GraphLoader


class TestGraphLoader:
    def test_should_skip_loading_true(self, tmp_data_dir):
        # We mock the API client so get_stats returns a real dict
        mock_api = MagicMock()
        mock_api.get_stats.return_value = {"author_count": 500}
        
        # Inject the mock client into the loader
        loader = GraphLoader(client=mock_api, data_dir=tmp_data_dir)
        
        # Patch settings to enable skipping
        with patch("app.loader.settings") as s:
            s.skip_if_loaded = True
            s.min_entities_threshold = 100
            
            # This should now return True because 500 >= 100
            assert loader.should_skip_loading() is True
            mock_api.get_stats.assert_called_once()

    def test_should_skip_loading_false(self, tmp_data_dir):
        mock_api = MagicMock()
        mock_api.get_stats.return_value = {"author_count": 10} # Below 100
        
        loader = GraphLoader(client=mock_api, data_dir=tmp_data_dir)
        
        with patch("app.loader.settings") as s:
            s.skip_if_loaded = True
            s.min_entities_threshold = 100
            assert loader.should_skip_loading() is False

class TestGraphDBClient:
    def test_get_stats_success(self):
        # Test the internal HTTP handling of the client
        with patch("httpx.Client") as mock_http_cls:
            mock_http = MagicMock()
            mock_http_cls.return_value = mock_http
            
            # Setup the mock response
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"author_count": 123}
            mock_http.get.return_value = mock_resp
            
            client = GraphDBClient()
            stats = client.get_stats()
            
            assert stats["author_count"] == 123
            assert mock_http.get.called