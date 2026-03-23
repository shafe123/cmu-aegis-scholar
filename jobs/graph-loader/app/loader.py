import gzip
import json
import logging
import httpx
from pathlib import Path
from collections import defaultdict
from app.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GraphDBClient:
    """Client for the Graph API service."""
    def __init__(self):
        self.base_url = settings.graph_api_url.rstrip('/')
        self.client = httpx.Client(timeout=settings.graph_api_timeout)

    def upsert_node(self, entity_type: str, data: dict):
        # entity_type: authors, works, orgs, topics
        try:
            r = self.client.post(f"{self.base_url}/{entity_type}", json=data)
            r.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to upsert {entity_type} {data.get('id')}: {e}")
            return False

    def create_relationship(self, rel_type: str, payload: dict):
        # rel_type: authored, affiliated, covers, cites, funded
        try:
            r = self.client.post(f"{self.base_url}/relationships/{rel_type}", json=payload)
            r.raise_for_status()
            return True
        except Exception as e:
            logger.debug(f"Rel error {rel_type}: {e}") # Debug because nodes might be missing in small test samples
            return False

class GraphLoader:
    def __init__(self):
        self.data_dir = Path(settings.data_dir)
        self.api = GraphDBClient()

    def get_files(self, entity_type: str):
        return sorted(self.data_dir.glob(f"dtic_{entity_type}_*.jsonl.gz"))

    def load_nodes(self, entity_type: str):
        """Standard node loader for Authors, Orgs, and Topics."""
        logger.info(f"--- Loading {entity_type} nodes ---")
        files = self.get_files(entity_type)
        count = 0
        for file_path in files:
            with gzip.open(file_path, 'rb') as f:
                for line in f:
                    node_data = json.loads(line)
                    if self.api.upsert_node(entity_type, node_data):
                        count += 1
            logger.info(f"Processed {file_path.name}")
        logger.info(f"Total {entity_type} nodes upserted: {count}")

    def load_works_and_rels(self):
        """
        The Works file is the 'glue'. It contains the Work node data 
        AND the links to Authors, Topics, and Orgs.
        """
        logger.info("--- Loading Work nodes and Relationships ---")
        files = self.get_files("works")
        
        for file_path in files:
            with gzip.open(file_path, 'rb') as f:
                for line in f:
                    work = json.loads(line)
                    work_id = work.get("id")

                    # 1. Upsert the Work node itself
                    self.api.upsert_node("works", work)

                    # 2. Extract and create relationships
                    # Link Authors
                    for author_entry in work.get("authors", []):
                        self.api.create_relationship("authored", {
                            "author_id": author_entry["author_id"],
                            "work_id": work_id
                        })
                        # If affiliation is present in the work record, link author to org
                        if author_entry.get("org_id"):
                            self.api.create_relationship("affiliated", {
                                "author_id": author_entry["author_id"],
                                "org_id": author_entry["org_id"],
                                "role": "Researcher"
                            })

                    # Link Topics
                    for topic_entry in work.get("topics", []):
                        self.api.create_relationship("covers", {
                            "work_id": work_id,
                            "topic_id": topic_entry["topic_id"],
                            "score": topic_entry.get("score", 1.0)
                        })

            logger.info(f"Processed relationships in {file_path.name}")

    def run(self):
        logger.info("Starting Graph Load...")
        # Order matters! Nodes must exist before they can be linked.
        self.load_nodes("authors")
        self.load_nodes("orgs")
        self.load_nodes("topics")
        self.load_works_and_rels()
        logger.info("Graph Load Completed Successfully.")

if __name__ == "__main__":
    loader = GraphLoader()
    loader.run()