"""Integration tests between Scholar API and Graph DB."""

import pytest
from httpx import AsyncClient, ASGITransport

@pytest.mark.asyncio
async def test_author_lookup_integration(app_client, graph_db_url):
    """
    Tests the real connection between the API and the Graph service.
    Note: Requires the graph-db service to be running at graph_db_url.
    """
    transport = ASGITransport(app=app_client)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Use a real ID that exists in your local/docker Neo4j
        author_id = "author_550e8400-e29b-41d4-a716-446655440000"
        response = await ac.get(f"/search/authors/{author_id}")

    assert response.status_code == 200
    # No mocking here! We are asserting against real data.
