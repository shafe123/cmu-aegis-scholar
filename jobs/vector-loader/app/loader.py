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
        logger.info("Initialized VectorDBClient with base_url: %s", self.base_url)

    def check_health(self) -> bool:
        """Check if the vector DB service is healthy."""
        try:
            response = self.client.get(f"{self.base_url}/health")
            response.raise_for_status()
            data = response.json()
            logger.info("Vector DB health check: %s", data)
            return data.get("status") == "healthy"
        except Exception as e:
            logger.error("Health check failed: %s", e)
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
            logger.error("Failed to get collection info: %s", e)
            return None

    def create_author_embedding(
        self,
        author_id: str,
        author_name: str,
        abstracts: list[str],
        collection_name: str,
        model_name: str,
        citation_count: int = None
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
            if citation_count is not None:
                payload["citation_count"] = citation_count

            response = self.client.post(
                f"{self.base_url}/authors/embeddings",
                json=payload
            )
            response.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to create author embedding for %s: %s",
                author_id, e.response.text
            )
            return False
        except Exception as e:
            logger.error("Failed to create author embedding for %s: %s", author_id, e)
            return False

    def close(self):
        """Close the HTTP client."""
        self.client.close()


class VectorLoader:
    """Loads DTIC data into the vector database."""

    def __init__(self, client: 'VectorDBClient' = None, data_dir: Path = None):
        """Initialize the data loader."""
        self.data_dir = data_dir if data_dir is not None else Path(settings.data_dir)
        self.client = client if client is not None else VectorDBClient(
            settings.vector_db_url, settings.vector_db_timeout
        )
        self.stats = defaultdict(int)

    def _parse_json(self, line: bytes) -> dict:
        """Parse a JSON line using orjson if available, otherwise standard json."""
        if HAS_ORJSON:
            return orjson.loads(line)
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
                logger.info(
                    "Collection '%s' already has %d entities (threshold: %d). "
                    "Skipping load.",
                    settings.collection_name, num_entities,
                    settings.min_entities_threshold
                )
                return True
            logger.info(
                "Collection has %d entities, below threshold. Proceeding with load.",
                num_entities
            )
        else:
            logger.info(
                "Collection '%s' does not exist. Proceeding with load.",
                settings.collection_name
            )

        return False

    def get_compressed_files(self, entity_type: str) -> list[Path]:
        """Get all compressed JSONL files for an entity type."""
        pattern = f"dtic_{entity_type}_*.jsonl.gz"
        files = sorted(self.data_dir.glob(pattern))
        logger.info("Found %d compressed files for %s", len(files), entity_type)
        return files

    def build_author_lookup(self) -> dict[str, dict]:
        """
        Build a lookup table of author_id -> {name, citation_count} by scanning author files.
        This is done once at startup to avoid repeated file scanning.

        Returns:
            Dictionary mapping author_id to author metadata
        """
        logger.info("Building author lookup table from author files...")
        lookup = {}

        author_files = self.get_compressed_files("authors")
        if not author_files:
            logger.warning("No author files found - author names will default to IDs")
            return lookup

        total_authors = 0
        for file_path in author_files:
            try:
                with gzip.open(file_path, 'rb') as f:
                    for line in f:
                        if not line.strip():
                            continue

                        try:
                            author = self._parse_json(line)
                            author_id = author.get("id")
                            author_name = author.get("name")
                            citation_count = author.get("citation_count", 0)

                            if author_id:
                                lookup[author_id] = {
                                    "name": author_name or author_id,
                                    "citation_count": citation_count
                                }
                                total_authors += 1
                        except Exception as e:
                            logger.debug("Error parsing author record: %s", e)
                            continue
            except Exception as e:
                logger.error("Error reading author file %s: %s", file_path, e)
                continue

        logger.info(
            "Built lookup table with %d authors (%d unique)",
            total_authors, len(lookup)
        )
        return lookup

    def process_works_file(self, file_path: Path, author_lookup: dict[str, dict]) -> int:
        """
        Process a works file and extract author abstracts.

        Args:
            file_path: Path to the works file
            author_lookup: Pre-built lookup table of author_id -> {name, citation_count}

        Returns:
            Number of records processed
        """
        logger.info("Processing works file: %s", file_path.name)

        # Accumulate abstracts per author
        author_data = defaultdict(lambda: {"name": None, "citation_count": 0, "abstracts": []})
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

                            # Get author metadata from lookup table (if available)
                            if author_data[author_id]["name"] is None:
                                author_info = author_lookup.get(author_id, {})
                                author_data[author_id]["name"] = author_info.get("name", author_id)
                            author_data[author_id]["citation_count"] = (
                                author_info.get("citation_count", 0)
                            )
                            # Add abstract to this author's collection
                            author_data[author_id]["abstracts"].append(abstract)

                        # Check max records limit
                        if settings.max_records and records_read >= settings.max_records:
                            logger.info("Reached max_records limit: %d", settings.max_records)
                            break

                    except Exception as e:
                        logger.error("Error parsing work record: %s", e)
                        continue

            logger.info(
                "Read %d works, extracted abstracts for %d authors",
                records_read, len(author_data)
            )

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
                        model_name=settings.embedding_model,
                        citation_count=data.get("citation_count")
                    )

                    if success:
                        authors_uploaded += 1
                    else:
                        authors_failed += 1

                    # Progress logging
                    if (authors_uploaded + authors_failed) % 10 == 0:
                        logger.info(
                            "  Progress: %d/%d authors processed",
                            authors_uploaded + authors_failed, len(author_data)
                        )

                except Exception as e:
                    logger.error("Failed to upload author %s: %s", author_id, e)
                    authors_failed += 1

            logger.info(
                "Completed file: %d authors uploaded, %d failed",
                authors_uploaded, authors_failed
            )

            self.stats["works_files_processed"] += 1
            self.stats["works_records_read"] += records_read
            self.stats["authors_uploaded"] += authors_uploaded
            self.stats["authors_failed"] += authors_failed

            return records_read

        except Exception as e:
            logger.error("Error processing file %s: %s", file_path, e)
            return 0

    def process_entity_type(self, entity_type: str, author_lookup: dict[str, dict]):
        """Process all files for a specific entity type."""
        logger.info("Processing entity type: %s", entity_type)

        files = self.get_compressed_files(entity_type)
        if not files:
            logger.warning("No files found for %s", entity_type)
            return

        for file_path in files:
            # Process based on entity type
            if entity_type == "works":
                self.process_works_file(file_path, author_lookup)
            else:
                logger.warning(
                    "Entity type '%s' not yet supported for loading", entity_type
                )
                continue

    def run(self):
        """Run the vector loader."""
        logger.info("=" * 70)
        logger.info("DTIC VECTOR LOADER STARTED")
        logger.info("=" * 70)
        logger.info("Data directory: %s", self.data_dir)
        logger.info("Vector DB URL: %s", settings.vector_db_url)
        logger.info("Collection: %s", settings.collection_name)
        logger.info("Model: %s", settings.embedding_model)
        logger.info("")

        try:
            # Wait for vector DB to be ready
            logger.info("Checking vector DB health...")
            max_retries = 10
            for i in range(max_retries):
                if self.client.check_health():
                    logger.info("Vector DB is healthy!")
                    break
                logger.warning(
                    "Vector DB not ready, retrying (%d/%d)...", i+1, max_retries
                )
                time.sleep(5)
            else:
                raise RuntimeError("Vector DB failed health check after max retries")

            # Check if loading should be skipped
            if self.should_skip_loading():
                logger.info("Skipping data load (data already present)")
                return

            # Build author lookup table first (for author names and metadata)
            author_lookup = self.build_author_lookup()

            # Process entity types (currently only works are supported)
            # Note: We only process works files because they contain the abstracts
            # needed to generate author embeddings
            entity_types_to_process = ["works"]

            for entity_type in entity_types_to_process:
                self.process_entity_type(entity_type, author_lookup)

            # Print summary
            logger.info("=" * 70)
            logger.info("VECTOR LOADING COMPLETED")
            logger.info("=" * 70)
            logger.info("Works files processed: %d", self.stats['works_files_processed'])
            logger.info("Works records read: %d", self.stats['works_records_read'])
            logger.info("Authors uploaded: %d", self.stats['authors_uploaded'])
            logger.info("Authors failed: %d", self.stats['authors_failed'])
            logger.info("=" * 70)

        except Exception as e:
            logger.error("Vector loading failed: %s", e, exc_info=True)
            raise

        finally:
            self.client.close()


def main():
    """Main entry point."""
    loader = VectorLoader()
    loader.run()


if __name__ == "__main__":
    main()
