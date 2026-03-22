import httpx
from app.config import settings

class GraphDBClient:
    def __init__(self):
        self.url = "http://graph-db:8003" # Internal K8s/Docker URL

    async def get_collaborators(self, author_id: str):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.url}/authors/{author_id}/collaborators")
            return response.json()

graph_client = GraphDBClient()