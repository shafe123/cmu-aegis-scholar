"""HTTP client for communicating with the Graph DB microservice."""

import logging

import httpx

logger = logging.getLogger(__name__)


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
            response = await client.get(f"{self.url}/viz/author-network/{author_id}")
            return response.json()

    async def get_most_recent_work_year(self, author_id: str) -> int | None:
        """Return the most recent publication year for an author from the graph DB.

        Calls /viz/author-network/{author_id} and extracts the maximum ``year``
        value from all work nodes in the response.  Returns ``None`` if the
        graph DB is unreachable or no work years are available.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.url}/viz/author-network/{author_id}")
                response.raise_for_status()
                data = response.json()
            years = [
                node["year"]
                for node in data.get("nodes", [])
                if node.get("group") == "work" and node.get("year") is not None
            ]
            return max(years) if years else None
        except (httpx.HTTPError, httpx.RequestError) as exc:
            logger.warning("Graph DB unavailable when fetching work year for %s: %s", author_id, exc)
            return None
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.debug("Unexpected error fetching work year for %s from graph DB: %s", author_id, exc)
            return None


graph_client = GraphDBClient()
