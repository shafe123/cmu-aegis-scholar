"""HTTP client for communicating with the Graph DB microservice."""

import httpx


class GraphDBClient:
    """Async HTTP client for the Graph DB service."""

    def __init__(self):
        self.url = "http://graph-db:8003"  # Internal K8s/Docker URL

    async def get_collaborators(self, author_id: str):
        """Fetch co-authors for a given author ID from the Graph DB."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.url}/authors/{author_id}/collaborators")
            return response.json()

    async def get_viz_data(self, author_id: str):
        """Fetch graph visualization data for a given author ID."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://graph-db:8003/viz/author-network/{author_id}"
            )
            return response.json()


graph_client = GraphDBClient()
