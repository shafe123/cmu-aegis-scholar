"""
Vector Loader for DTIC Vector Database

Loads compressed JSONL data into the vector database.
Runs once and inspects vector database to avoid duplicate loading.
"""
import gzip
import json
import logging
import time
from pathlib import Path
from typing import Optional
from collections import defaultdict

try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False

import httpx

from app.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class VectorDBClient:
    """Client for interacting with the Vector DB API."""
    
    def __init__(self, base_url: str, timeout: int = 300):
        """Initialize the client."""
        self.base_url = base_url.rstrip('/')
        self.client = httpx.Client(timeout=timeout)
        logger.info(f"Initialized VectorDBClient with base_url: {self.base_url}")
    
    def check_health(self) -> bool:
        """Check if the vector DB service is healthy."""
        try:
            response = self.client.get(f"{self.base_url}/health")
            response.raise_for_status()
            data = response.json()
            logger.info(f"Vector DB health check: {data}")
            return data.get("status") == "healthy"
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def get_collection_info(self, collection_name: str) -> Optional[dict]:
        """Get information about a collection."""
        try:
            response = self.client.get(f"{self.base_url}/collections/{collection_name}")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return None
    
    def create_author_embedding(
        self,
        author_id: str,
        author_name: str,
        abstracts: list[str],
        collection_name: str,
        model_name: str
    ) -> bool:
        """Create an author embedding from abstracts."""
        try:
            payload = {
                "author_id": author_id,
                "author_name": author_name,
                "abstracts": abstracts,
                "collection_name": collection_name,
                "model_name": model_name
            }
            
            response = self.client.post(
                f"{self.base_url}/authors/embeddings",
                json=payload
            )
            response.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to create author embedding for {author_id}: {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Failed to create author embedding for {author_id}: {e}")
            return False
    
    def close(self):
        """Close the HTTP client."""
        self.client.close()


class VectorLoader:
    """Loads DTIC data into the vector database."""
    
    def __init__(self):
        """Initialize the data loader."""
        self.data_dir = Path(settings.data_dir)
        self.client = VectorDBClient(settings.vector_db_url, settings.vector_db_timeout)
        self.stats = defaultdict(int)
    
    def _parse_json(self, line: bytes) -> dict:
        """Parse a JSON line using orjson if available, otherwise standard json."""
        if HAS_ORJSON:
            return orjson.loads(line)
        else:
            return json.loads(line.decode('utf-8'))
    
    def should_skip_loading(self) -> bool:
        """Check if loading should be skipped by inspecting the vector database."""
        if not settings.skip_if_loaded:
            logger.info("skip_if_loaded is False, proceeding with load")
            return False
        
        # Check if collection exists and has data
        collection_info = self.client.get_collection_info(settings.collection_name)
        if collection_info:
            num_entities = collection_info.get("num_entities", 0)
            if num_entities >= settings.min_entities_threshold:
                logger.info(f"Collection '{settings.collection_name}' already has "
                           f"{num_entities} entities (threshold: {settings.min_entities_threshold}). "
                           f"Skipping load.")
                return True
            else:
                logger.info(f"Collection has {num_entities} entities, below threshold. "
                           f"Proceeding with load.")
        else:
            logger.info(f"Collection '{settings.collection_name}' does not exist. "
                       f"Proceeding with load.")
        
        return False
    
    def get_compressed_files(self, entity_type: str) -> list[Path]:
        """Get all compressed JSONL files for an entity type."""
        pattern = f"dtic_{entity_type}_*.jsonl.gz"
        files = sorted(self.data_dir.glob(pattern))
        logger.info(f"Found {len(files)} compressed files for {entity_type}")
        return files
    
    def process_works_file(self, file_path: Path) -> int:
        """
        Process a works file and extract author abstracts.
        
        Returns:
            Number of records processed
        """
        logger.info(f"Processing works file: {file_path.name}")
        
        # Accumulate abstracts per author
        author_data = defaultdict(lambda: {"name": None, "abstracts": []})
        records_read = 0
        
        try:
            with gzip.open(file_path, 'rb') as f:
                for line in f:
                    if not line.strip():
                        continue
                    
                    try:
                        work = self._parse_json(line)
                        records_read += 1
                        
                        # Extract abstract
                        abstract = work.get("abstract", "").strip()
                        if not abstract:
                            continue
                        
                        # Extract authors
                        authors = work.get("authors", [])
                        for author in authors:
                            author_id = author.get("author_id")
                            if not author_id:
                                continue
                            
                            # Store author name if we don't have it yet
                            if author_data[author_id]["name"] is None:
                                # Try to get name from author object or use ID
                                author_data[author_id]["name"] = author.get("name", author_id)
                            
                            # Add abstract to this author's collection
                            author_data[author_id]["abstracts"].append(abstract)
                        
                        # Check max records limit
                        if settings.max_records and records_read >= settings.max_records:
                            logger.info(f"Reached max_records limit: {settings.max_records}")
                            break
                    
                    except Exception as e:
                        logger.error(f"Error parsing work record: {e}")
                        continue
            
            logger.info(f"Read {records_read} works, extracted abstracts for {len(author_data)} authors")
            
            # Upload author embeddings in batches
            authors_uploaded = 0
            authors_failed = 0
            
            for author_id, data in author_data.items():
                try:
                    if not data["abstracts"]:
                        continue
                    
                    success = self.client.create_author_embedding(
                        author_id=author_id,
                        author_name=data["name"] or author_id,
                        abstracts=data["abstracts"],
                        collection_name=settings.collection_name,
                        model_name=settings.embedding_model
                    )
                    
                    if success:
                        authors_uploaded += 1
                    else:
                        authors_failed += 1
                    
                    # Progress logging
                    if (authors_uploaded + authors_failed) % 10 == 0:
                        logger.info(f"  Progress: {authors_uploaded + authors_failed}/{len(author_data)} authors processed")
                
                except Exception as e:
                    logger.error(f"Failed to upload author {author_id}: {e}")
                    authors_failed += 1
            
            logger.info(f"Completed file: {authors_uploaded} authors uploaded, {authors_failed} failed")
            
            self.stats["works_files_processed"] += 1
            self.stats["works_records_read"] += records_read
            self.stats["authors_uploaded"] += authors_uploaded
            self.stats["authors_failed"] += authors_failed
            
            return records_read
        
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            return 0
    
    def process_entity_type(self, entity_type: str):
        """Process all files for a specific entity type."""
        logger.info(f"Processing entity type: {entity_type}")
        
        files = self.get_compressed_files(entity_type)
        if not files:
            logger.warning(f"No files found for {entity_type}")
            return
        
        for file_path in files:
            # Process based on entity type
            if entity_type == "works":
                self.process_works_file(file_path)
            else:
                logger.warning(f"Entity type '{entity_type}' not yet supported for loading")
                continue
    
    def run(self):
        """Run the vector loader."""
        logger.info("=" * 70)
        logger.info("DTIC VECTOR LOADER STARTED")
        logger.info("=" * 70)
        logger.info(f"Data directory: {self.data_dir}")
        logger.info(f"Vector DB URL: {settings.vector_db_url}")
        logger.info(f"Collection: {settings.collection_name}")
        logger.info(f"Model: {settings.embedding_model}")
        logger.info("")
        
        try:
            # Wait for vector DB to be ready
            logger.info("Checking vector DB health...")
            max_retries = 10
            for i in range(max_retries):
                if self.client.check_health():
                    logger.info("Vector DB is healthy!")
                    break
                logger.warning(f"Vector DB not ready, retrying ({i+1}/{max_retries})...")
                time.sleep(5)
            else:
                raise RuntimeError("Vector DB failed health check after max retries")
            
            # Check if loading should be skipped
            if self.should_skip_loading():
                logger.info("Skipping data load (data already present)")
                return
            
            # Process entity types (currently only works are supported)
            # Note: We only process works files because they contain the abstracts
            # needed to generate author embeddings
            entity_types_to_process = ["works"]
            
            for entity_type in entity_types_to_process:
                self.process_entity_type(entity_type)
            
            # Print summary
            logger.info("=" * 70)
            logger.info("VECTOR LOADING COMPLETED")
            logger.info("=" * 70)
            logger.info(f"Works files processed: {self.stats['works_files_processed']}")
            logger.info(f"Works records read: {self.stats['works_records_read']}")
            logger.info(f"Authors uploaded: {self.stats['authors_uploaded']}")
            logger.info(f"Authors failed: {self.stats['authors_failed']}")
            logger.info("=" * 70)
        
        except Exception as e:
            logger.error(f"Vector loading failed: {e}", exc_info=True)
            raise
        
        finally:
            self.client.close()


def main():
    """Main entry point."""
    loader = VectorLoader()
    loader.run()


if __name__ == "__main__":
    main()
