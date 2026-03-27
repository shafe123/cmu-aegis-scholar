import gzip
import json
import logging
import httpx
from pathlib import Path
from app.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GraphDBClient:
    """Client for the Graph API service."""
    def __init__(self):
        self.base_url = settings.graph_api_url.rstrip('/')
        self.client = httpx.Client(timeout=settings.graph_api_timeout)

    def get_stats(self):
        """Check the current population of the graph."""
        try:
            r = self.client.get(f"{self.base_url}/stats")
            if r.status_code == 200:
                return r.json()
            # If API is up but returns error, log it
            logger.warning(f"Graph API returned status {r.status_code}")
            return None
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return None

    def upsert_node(self, entity_type: str, data: dict):
        try:
            r = self.client.post(f"{self.base_url}/{entity_type}", json=data)
            r.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to upsert {entity_type} {data.get('id')}: {e}")
            return False

    def create_relationship(self, rel_type: str, payload: dict):
        try:
            r = self.client.post(f"{self.base_url}/relationships/{rel_type}", json=payload)
            r.raise_for_status()
            return True
        except Exception as e:
            logger.debug(f"Rel error {rel_type}: {e}")
            return False

class GraphLoader:
    def __init__(self, client=None, data_dir=None):
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
                logger.info(f"Graph already contains {count} authors. Skipping load.")
                return True
        return False

    def get_files(self, entity_type: str):
        return sorted(self.data_dir.glob(f"dtic_{entity_type}_*.jsonl.gz"))

    def load_nodes(self, entity_type: str):
        logger.info(f"--- Loading {entity_type} nodes ---")
        files = self.get_files(entity_type)
        count = 0
        for file_path in files:
            with gzip.open(file_path, 'rb') as f:
                for line in f:
                    if not line.strip(): continue
                    node_data = json.loads(line)
                    if self.api.upsert_node(entity_type, node_data):
                        count += 1
            logger.info(f"Processed {file_path.name}")
        logger.info(f"Total {entity_type} nodes upserted: {count}")

    def load_works_and_rels(self):
        logger.info("--- Loading Work nodes and Relationships ---")
        files = self.get_files("works")
        for file_path in files:
            with gzip.open(file_path, 'rb') as f:
                for line in f:
                    if not line.strip(): continue
                    work = json.loads(line)
                    work_id = work.get("id")
                    self.api.upsert_node("works", work)
                    for auth in work.get("authors", []):
                        self.api.create_relationship("authored", {"author_id": auth["author_id"], "work_id": work_id})
                        if auth.get("org_id"):
                            self.api.create_relationship("affiliated", {"author_id": auth["author_id"], "org_id": auth["org_id"], "role": "Researcher"})
                    for topic in work.get("topics", []):
                        self.api.create_relationship("covers", {"work_id": work_id, "topic_id": topic["topic_id"], "score": topic.get("score", 1.0)})
            logger.info(f"Processed relationships in {file_path.name}")

    def run(self):
        logger.info("Starting Graph Loader...")
        if self.should_skip_loading():
            return
        self.load_nodes("authors")
        self.load_nodes("orgs")
        self.load_nodes("topics")
        self.load_works_and_rels()
        logger.info("Graph Load Completed Successfully.")

if __name__ == "__main__":
    loader = GraphLoader()
    loader.run()