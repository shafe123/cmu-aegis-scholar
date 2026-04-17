import httpx


class GraphDBClient:
    def __init__(self):
        self.url = "http://graph-db:8003"  # Internal K8s/Docker URL

    async def get_collaborators(self, author_id: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.url}/authors/{author_id}/collaborators")
            return response.json()

    async def get_viz_data(self, author_id: str):
        async with httpx.AsyncClient() as client:
            # Calls the Graph API service
            response = await client.get(f"http://graph-db:8003/viz/author-network/{author_id}")
            return response.json()


graph_client = GraphDBClient()
