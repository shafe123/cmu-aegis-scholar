"""Test configuration and shared fixtures for graph-loader."""
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# 1. Configuration Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_settings():
    """Provide mock settings for graph-loader tests."""
    from app.config import Settings
    return Settings(
        graph_api_url="http://test-graph:8003",
        data_dir="/tmp/graph_test_data",
        skip_if_loaded=True,
        min_entities_threshold=100,
        log_level="INFO"
    )

# ---------------------------------------------------------------------------
# 2. HTTP & API Client Mocks (Synchronous for Loader)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_http_client():
    """
    Mock synchronous HTTP client for API calls.
    Note: Your loader uses httpx.Client (Sync), so we use MagicMock, not AsyncMock.
    """
    client = MagicMock()
    # Mock return values for standard calls
    client.get.return_value = MagicMock(status_code=200, json=lambda: {"author_count": 0})
    client.post.return_value = MagicMock(status_code=200)
    return client

# ---------------------------------------------------------------------------
# 3. Data Fixtures (Updated for DTIC Prefixed Schema)
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_dtic_author():
    """Sample DTIC author data matching your graph node properties."""
    return {
        "id": "author_cbaacc8e-3d91-5bb6-9c19-f82e83a39150",
        "name": "Dr. Jane Smith",
        "h_index": 25,
        "works_count": 42,
        "sources": [{"source": "openalex", "id": "A12345"}]
    }

@pytest.fixture
def sample_dtic_work():
    """Sample DTIC work data with internal relationship keys."""
    return {
        "id": "work_w789012",
        "title": "Advanced Defense Systems Research",
        "authors": [
            {"author_id": "author_1", "org_id": "org_1"},
            {"author_id": "author_2", "org_id": None}
        ],
        "topics": [
            {"topic_id": "topic_cyber", "score": 0.95},
            {"topic_id": "topic_ml", "score": 0.8}
        ],
        "year": 2025,
        "citation_count": 10
    }

@pytest.fixture
def sample_dtic_organization():
    """Sample DTIC organization data."""
    return {
        "id": "org_o555555",
        "name": "Carnegie Mellon University",
        "type": "institution",
        "country": "US"
    }

# ---------------------------------------------------------------------------
# 4. File System Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_data_dir(tmp_path):
    """Provides a temporary path for creating mock .jsonl.gz files."""
    d = tmp_path / "data"
    d.mkdir()
    return d