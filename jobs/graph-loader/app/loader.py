import gzip
import json
import logging
from pathlib import Path
from typing import Any

import httpx

from app.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class GraphDBClient:
    """Client for the Graph API service."""

    def __init__(self) -> None:
        self.base_url = settings.graph_api_url.rstrip("/")
        self.client = httpx.Client(timeout=settings.graph_api_timeout)

    def get_stats(self) -> dict[str, Any] | None:
        """Check the current population of the graph."""
        try:
            r = self.client.get(f"{self.base_url}/stats")
            if r.status_code == 200:
                return r.json()
            # If API is up but returns error, log it
            logger.warning("Graph API returned status %s", r.status_code)
            return None
        except Exception as e:
            logger.error("Failed to get stats: %s", e)
            return None

    def upsert_node(self, entity_type: str, data: dict[str, Any]) -> bool:
        """Send a POST request to upsert a node."""
        try:
            r = self.client.post(f"{self.base_url}/{entity_type}", json=data)
            r.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            response_text = e.response.text if e.response is not None else ""
            logger.error(
                "Failed to upsert %s %s: %s | response=%s",
                entity_type,
                data.get("id"),
                e,
                response_text,
            )
            return False
        except Exception as e:
            logger.error("Failed to upsert %s %s: %s", entity_type, data.get("id"), e)
            return False

    def create_relationship(self, rel_type: str, payload: dict[str, Any]) -> bool:
        """Send a POST request to create a relationship."""
        try:
            r = self.client.post(f"{self.base_url}/relationships/{rel_type}", json=payload)
            r.raise_for_status()
            return True
        except Exception as e:
            logger.debug("Rel error %s: %s", rel_type, e)
            return False


class GraphLoader:
    """Orchestrates loading data from local files into the Graph API."""

    def __init__(self, client: GraphDBClient | None = None, data_dir: Path | None = None) -> None:
        self.data_dir = Path(data_dir or settings.data_dir)
        self.api = client or GraphDBClient()

    def should_skip_loading(self) -> bool:
        """Query the Graph API to see if the database is already populated."""
        if not settings.skip_if_loaded:
            return False

        stats = self.api.get_stats()
        if stats:
            count = stats.get("author_count", 0)
            if count >= settings.min_entities_threshold:
                logger.info("Graph already contains %s authors. Skipping load.", count)
                return True
        return False

    def get_files(self, entity_type: str) -> list[Path]:
        """Retrieve list of compressed JSONL files for a type."""
        return sorted(self.data_dir.glob(f"dtic_{entity_type}_*.jsonl.gz"))

    def load_nodes(self, entity_type: str) -> None:
        """Standard node loader for Authors, Orgs, and Topics."""
        files = self.get_files(entity_type)
        total_files = len(files)
        count = 0

        logger.info("--- Loading %s nodes from %s file(s) ---", entity_type, total_files)

        for file_index, file_path in enumerate(files, start=1):
            file_count = 0
            with gzip.open(file_path, "rb") as f:
                for line in f:
                    if not line.strip():
                        continue
                    node_data = json.loads(line)
                    # Ensure Org data has a default 'type' if missing to satisfy Schema
                    if entity_type == "orgs" and not node_data.get("type"):
                        node_data["type"] = "institution"
                    if self.api.upsert_node(entity_type, node_data):
                        count += 1
                        file_count += 1

            logger.info(
                "Progress [%s]: file %s/%s complete (%s) - file_nodes=%s total_nodes=%s",
                entity_type,
                file_index,
                total_files,
                file_path.name,
                file_count,
                count,
            )

        logger.info("Total %s nodes upserted: %s", entity_type, count)

    @staticmethod
    def normalize_work_payload(work: dict[str, Any]) -> dict[str, Any]:
        """Fill in optional graph fields for sparse DTIC work records."""
        normalized = dict(work)
        title = normalized.get("title") or normalized.get("name") or normalized.get("id") or "Untitled Work"

        normalized.setdefault("title", title)
        normalized.setdefault("name", title)
        normalized.setdefault("type", "report")

        if normalized.get("citation_count") is None:
            normalized["citation_count"] = 0
        if normalized.get("sources") is None:
            normalized["sources"] = []

        if normalized.get("year") is None:
            publication_date = normalized.get("publication_date")
            if isinstance(publication_date, str):
                try:
                    normalized["year"] = int(publication_date[:4])
                except (TypeError, ValueError):
                    pass

        return normalized

    def load_works_and_rels(self) -> None:
        """Processes Work nodes and establishes all graph relationships."""
        files = self.get_files("works")
        total_files = len(files)
        total_works = 0
        total_relationships = 0

        logger.info("--- Loading Work nodes and Relationships from %s file(s) ---", total_files)

        for file_index, file_path in enumerate(files, start=1):
            file_work_count = 0
            file_relationship_count = 0
            with gzip.open(file_path, "rb") as f:
                for line in f:
                    if not line.strip():
                        continue
                    work = self.normalize_work_payload(json.loads(line))
                    work_id = work.get("id")

                    # 1. Upsert the Work node itself
                    if self.api.upsert_node("works", work):
                        total_works += 1
                        file_work_count += 1

                    for auth in work.get("authors", []):
                        # Link Author to Work
                        if self.api.create_relationship(
                            "authored", {"author_id": auth["author_id"], "work_id": work_id}
                        ):
                            total_relationships += 1
                            file_relationship_count += 1
                        # Link Author to Org (Affiliation)
                        if auth.get("org_id") and self.api.create_relationship(
                            "affiliated",
                            {
                                "author_id": auth["author_id"],
                                "org_id": auth["org_id"],
                                "role": "Researcher",
                            },
                        ):
                            total_relationships += 1
                            file_relationship_count += 1

                    for topic in work.get("topics", []):
                        # Link Work to Topic
                        if self.api.create_relationship(
                            "covers",
                            {
                                "work_id": work_id,
                                "topic_id": topic["topic_id"],
                                "score": topic.get("score", 1.0),
                            },
                        ):
                            total_relationships += 1
                            file_relationship_count += 1

            logger.info(
                "Progress [works]: file %s/%s complete (%s) - file_works=%s file_relationships=%s total_works=%s total_relationships=%s",
                file_index,
                total_files,
                file_path.name,
                file_work_count,
                file_relationship_count,
                total_works,
                total_relationships,
            )

    def run(self) -> None:
        """Execute the full loading pipeline."""
        logger.info("Starting Graph Loader...")
        if self.should_skip_loading():
            return
        self.load_nodes("authors")
        self.load_nodes("orgs")
        self.load_nodes("topics")
        self.load_works_and_rels()
        logger.info("Graph Load Completed Successfully.")


def main() -> None:
    """Main entry point for the job."""
    loader = GraphLoader()
    loader.run()


if __name__ == "__main__":
    main()
