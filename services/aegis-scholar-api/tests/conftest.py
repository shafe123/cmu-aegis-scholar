"""Test configuration and shared fixtures for aegis-scholar-api."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def mock_graph_db_year():
    """Auto-mock graph DB year lookup for all tests to avoid live network calls.

    Tests that need specific years can override with their own patch.object block.
    """
    from app.services.graph_db import graph_client

    with patch.object(graph_client, "get_most_recent_work_year", new=AsyncMock(return_value=None)):
        yield


@pytest.fixture
def mock_vector_db_search():
    """Standard successful vector DB search response."""
    return {
        "results": [
            {
                "author_id": "author_1a2b3c4d-1234-5678-abcd-1234567890ab",
                "author_name": "Dr. Jane Smith",
                "num_abstracts": 42,
                "citation_count": 1500,
                "distance": 0.25,
            },
            {
                "author_id": "author_2b3c4d5e-2345-6789-bcde-2345678901bc",
                "author_name": "Dr. John Doe",
                "num_abstracts": 18,
                "citation_count": 300,
                "distance": 0.55,
            },
        ],
        "pagination": {"returned": 2},
    }


@pytest.fixture
def mock_vector_db_empty():
    """Empty vector DB search response."""
    return {"results": [], "pagination": {"returned": 0}}


@pytest.fixture
async def async_client():
    """Async HTTP client for testing FastAPI app with mocked lifespan."""
    with (
        patch("app.services.vector_db.init_client", new_callable=AsyncMock),
        patch("app.services.vector_db.close_client", new_callable=AsyncMock),
    ):
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
