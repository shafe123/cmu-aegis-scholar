"""
DTIC Topic Extractor.

This script extracts topics/keywords from raw DTIC works in Azure Blob Storage
(raw/dtic/works/ prefix) and saves them as individual JSON files in the
clean/dtic/ prefix, following the AEGIS Scholar database schema.

Features:
- Reads raw DTIC work JSON files from Azure Blob Storage
- Extracts topic/keyword information from DTIC API
- Transforms data to match the Topic schema in database_schemas.json
- Generates consistent GUIDs for topics
- Implements upsert functionality (updates existing topic files)
- State management for tracking processed files
"""

import json
import logging
import argparse
import os
import time
import requests
import uuid
import re
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
from azure.storage.blob import BlobServiceClient
from urllib.parse import urljoin

# Generate timestamped log filename
_log_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
_logs_dir = Path("logs")
_logs_dir.mkdir(exist_ok=True)
_log_filename = _logs_dir / f"{_log_timestamp}_extract_topics.log"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(_log_filename, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Quiet Azure SDK loggers
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
    logging.WARNING
)


class ExtractionStateManager:
    """Manages state of processed files and discovered topics."""

    def __init__(self, state_file: str = "extraction_state_topics.json"):
        self.state_file = Path(state_file)
        self.state = self._load_state()

    def _load_state(self) -> Dict:
        """Load state from file or create new state."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                    logger.info(
                        f"Loaded state: {len(state.get('processed_files', []))} files processed"
                    )
                    return state
            except json.JSONDecodeError:
                logger.warning("Corrupted state file, starting fresh")

        return {
            "processed_files": [],
            "failed_files": [],
            "topics": {},  # topic_name -> topic_id mapping
            "last_updated": None,
            "total_processed": 0,
            "total_topics_found": 0,
        }

    def save_state(self):
        """Save current state to file with retry logic for Windows file locking."""
        self.state["last_updated"] = datetime.now().isoformat()

        # Retry logic for occasional Windows file locking issues
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Write to temp file first, then rename (atomic operation)
                temp_file = self.state_file.with_suffix(".tmp")
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(self.state, f, indent=2)

                # Atomic rename
                temp_file.replace(self.state_file)
                logger.debug("Extraction state saved")
                return

            except (OSError, IOError) as e:
                if attempt < max_retries - 1:
                    logger.debug(
                        f"Save state attempt {attempt + 1} failed, retrying: {e}"
                    )
                    time.sleep(0.1)  # Brief delay before retry
                else:
                    logger.warning(
                        f"Failed to save state after {max_retries} attempts: {e}"
                    )
                    # Don't raise - continue processing without saving state

    def mark_processed(self, blob_name: str):
        """Mark a blob as successfully processed."""
        if blob_name not in self.state["processed_files"]:
            self.state["processed_files"].append(blob_name)
            self.state["total_processed"] += 1
            # Remove from failed if it was there
            if blob_name in self.state["failed_files"]:
                self.state["failed_files"].remove(blob_name)
            self.save_state()

    def mark_failed(self, blob_name: str):
        """Mark a blob as failed to process."""
        if blob_name not in self.state["failed_files"]:
            self.state["failed_files"].append(blob_name)
            self.save_state()

    def is_processed(self, blob_name: str) -> bool:
        """Check if blob has been processed."""
        return blob_name in self.state["processed_files"]

    def get_or_create_topic_id(self, topic_name: str) -> str:
        """Get existing topic_id or create a new one."""
        # Normalize topic name for consistent ID generation
        normalized_name = topic_name.strip().lower()

        if normalized_name not in self.state["topics"]:
            # Generate deterministic GUID based on topic name
            namespace = uuid.UUID(
                "00000000-0000-0000-0000-000000000003"
            )  # Different namespace for topics
            topic_uuid = uuid.uuid5(namespace, normalized_name)
            self.state["topics"][normalized_name] = f"topic_{topic_uuid}"
            self.state["total_topics_found"] += 1
            self.save_state()

        return self.state["topics"][normalized_name]

    def get_processed_count(self) -> int:
        """Get count of processed files."""
        return len(self.state["processed_files"])

    def get_failed_count(self) -> int:
        """Get count of failed files."""
        return len(self.state["failed_files"])

    def get_topic_count(self) -> int:
        """Get count of unique topics."""
        return len(self.state["topics"])


class DTICTopicExtractor:
    """Extracts topics from DTIC works and transforms to schema format."""

    DTIC_BASE_URL = "https://dtic.dimensions.ai"

    def __init__(
        self,
        connection_string: str,
        source_container: str,
        dest_container: str,
        source_prefix: str = "dtic/works/",
        dest_prefix: str = "dtic/topics/",
        state_file: str = "extraction_state_topics.json",
        request_delay: float = 0.5,
        enable_amplification: bool = True,
    ):
        """
        Initialize the topic extractor.

        Args:
            connection_string: Azure Storage connection string
            source_container: Name of source blob container (e.g., 'raw')
            dest_container: Name of destination blob container (e.g., 'clean')
            source_prefix: Prefix for source blobs (raw works)
            dest_prefix: Prefix for topic files
            state_file: State file path
            request_delay: Delay between API requests in seconds
            enable_amplification: Whether to fetch data from DTIC API
        """
        self.connection_string = connection_string
        self.source_container = source_container
        self.dest_container = dest_container
        self.source_prefix = source_prefix
        self.dest_prefix = dest_prefix
        self.request_delay = request_delay
        self.enable_amplification = enable_amplification

        # Initialize blob service client
        self.blob_service_client = BlobServiceClient.from_connection_string(
            connection_string
        )
        self.source_container_client = self.blob_service_client.get_container_client(
            source_container
        )
        self.dest_container_client = self.blob_service_client.get_container_client(
            dest_container
        )

        # Initialize state manager
        self.state_manager = ExtractionStateManager(state_file)

        # Initialize HTTP session for API requests
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "AEGIS-Scholar-Extractor/1.0"})

        logger.info("Initialized DTICTopicExtractor")
        logger.info(f"  Source: {source_container}/{source_prefix}")
        logger.info(f"  Destination: {dest_container}/{dest_prefix}")
        logger.info(
            f"  Amplification: {'enabled' if enable_amplification else 'disabled'}"
        )

    def fetch_topic_info(self, keyword_url: str) -> Optional[Dict]:
        """
        Fetch topic/keyword information from DTIC API.

        Args:
            keyword_url: The keyword URL from the work data

        Returns:
            Dict with topic information or None if failed
        """
        if not self.enable_amplification:
            return None

        try:
            # Build full URL
            full_url = urljoin(self.DTIC_BASE_URL, keyword_url)
            logger.debug(f"Fetching topic info from: {full_url}")

            response = self.session.get(full_url, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Rate limiting
            time.sleep(self.request_delay)

            return data

        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to fetch topic info from {keyword_url}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse topic info JSON for {keyword_url}: {e}")
            return None

    def sanitize_filename(self, topic_name: str) -> str:
        """
        Create a safe filename from topic name.

        Args:
            topic_name: The topic name

        Returns:
            Sanitized filename
        """
        # Remove special characters, replace spaces with underscores
        safe_name = re.sub(r"[^\w\s-]", "", topic_name)
        safe_name = re.sub(r"[-\s]+", "_", safe_name)
        # Limit length
        safe_name = safe_name[:100].strip("_")
        return safe_name.lower()

    def extract_and_clean_topic(
        self, topic_name: str, topic_data: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Extract and clean a single topic.

        Args:
            topic_name: The topic/keyword name
            topic_data: Optional additional data from API (must include 'id' for filename)

        Returns:
            Cleaned topic dict or None if invalid
        """
        if not topic_name:
            return None

        topic_id = self.state_manager.get_or_create_topic_id(topic_name)

        # Build topic entity following schema
        topic_entity = {
            "id": topic_id,
            "name": topic_name,
            "sources": [
                {
                    "source": "dtic",
                    "id": topic_data.get(
                        "id", f"dtic:{self.sanitize_filename(topic_name)}"
                    )
                    if topic_data
                    else f"dtic:{self.sanitize_filename(topic_name)}",
                }
            ],
            "last_updated": datetime.now().isoformat(),
        }

        # Add optional fields from API data if available
        if topic_data and isinstance(topic_data, dict):
            # Extract field, subfield, domain if present
            if topic_data.get("field"):
                topic_entity["field"] = topic_data["field"]
            if topic_data.get("subfield"):
                topic_entity["subfield"] = topic_data["subfield"]
            if topic_data.get("domain"):
                topic_entity["domain"] = topic_data["domain"]

        return topic_entity

    def process_blob(self, blob_name: str) -> int:
        """
        Process a single blob: read raw work and extract topics.

        Args:
            blob_name: Name of the blob to process

        Returns:
            Number of topics extracted, or -1 if failed
        """
        try:
            # Download raw work data
            blob_client = self.source_container_client.get_blob_client(blob_name)
            raw_data = blob_client.download_blob().readall()
            raw_work = json.loads(raw_data)

            logger.debug(f"Processing: {raw_work.get('publication_id', 'unknown')}")

            # Extract topics from the work
            topics_found = 0
            keywords = raw_work.get("keywords", [])

            # Process keywords - they might be strings, URLs, or amplified structures
            for keyword in keywords:
                topics_to_process = []  # List of (topic_name, topic_data) tuples

                # Check if keyword is a URL or a plain string
                if isinstance(keyword, str):
                    if keyword.startswith("/") or keyword.startswith("http"):
                        # It's a URL, fetch data if amplification is enabled
                        if self.enable_amplification:
                            topic_data = self.fetch_topic_info(keyword)
                            # Try to extract topic name from data
                            if topic_data and isinstance(topic_data, dict):
                                topic_name = topic_data.get("name") or topic_data.get(
                                    "title"
                                )
                                if topic_name:
                                    topics_to_process.append((topic_name, topic_data))
                    else:
                        # It's a plain topic name
                        topics_to_process.append((keyword, None))

                elif isinstance(keyword, dict):
                    # Check if it's amplified data with 'entities' array
                    if "entities" in keyword:
                        # Amplified structure: group topics by field/subfield hierarchy
                        # Parse all entities first
                        parsed_entities = []
                        for entity in keyword.get("entities", []):
                            if isinstance(entity, dict) and "details" in entity:
                                details = entity["details"]
                                name = details.get("name", "")
                                entity_id = details.get("uber_cat_id") or entity.get(
                                    "id"
                                )

                                # Extract numeric code from name (e.g., "49" from "49 Mathematical Sciences")
                                code_match = re.match(r"^(\d+)", name)
                                if code_match and entity_id:
                                    code = code_match.group(1)
                                    parsed_entities.append(
                                        {
                                            "code": code,
                                            "name": name,
                                            "id": entity_id,
                                            "code_length": len(code),
                                        }
                                    )

                        # Group by field (2-digit) and subfield (4-digit)
                        # Build a map of field_code -> {field_data, subfields: []}
                        field_groups = {}
                        for entity in parsed_entities:
                            if entity["code_length"] == 2:
                                # This is a field
                                field_groups[entity["code"]] = {
                                    "field_name": entity["name"],
                                    "field_id": entity["id"],
                                    "subfields": [],
                                }

                        # Add subfields to their parent fields
                        for entity in parsed_entities:
                            if entity["code_length"] == 4:
                                # This is a subfield - find parent field (first 2 digits)
                                parent_code = entity["code"][:2]
                                if parent_code in field_groups:
                                    field_groups[parent_code]["subfields"].append(
                                        entity
                                    )
                                else:
                                    # Subfield without parent field - create standalone
                                    field_groups[entity["code"]] = {
                                        "field_name": None,
                                        "field_id": None,
                                        "subfields": [entity],
                                    }

                        # Create topic entities from grouped data
                        for field_code, group_data in field_groups.items():
                            if group_data["subfields"]:
                                # Create topic for each subfield with field info
                                for subfield in group_data["subfields"]:
                                    entity_data = {
                                        "name": subfield["name"],
                                        "id": subfield["id"],
                                        "field": group_data["field_name"],
                                        "subfield": subfield["name"],
                                    }
                                    topics_to_process.append(
                                        (subfield["name"], entity_data)
                                    )
                            elif group_data["field_name"]:
                                # Field with no subfields - create topic for field only
                                entity_data = {
                                    "name": group_data["field_name"],
                                    "id": group_data["field_id"],
                                    "field": group_data["field_name"],
                                }
                                topics_to_process.append(
                                    (group_data["field_name"], entity_data)
                                )
                    else:
                        # Simple structured data with direct name/title
                        topic_name = keyword.get("name") or keyword.get("title")
                        if topic_name:
                            topics_to_process.append((topic_name, keyword))

                # Process all extracted topics
                for topic_name, topic_data in topics_to_process:
                    # Clean the topic
                    cleaned_topic = self.extract_and_clean_topic(topic_name, topic_data)
                    if not cleaned_topic:
                        continue

                    # Use entity ID as filename if available, otherwise use sanitized name
                    if (
                        topic_data
                        and isinstance(topic_data, dict)
                        and topic_data.get("id")
                    ):
                        filename = topic_data["id"]
                    else:
                        filename = self.sanitize_filename(topic_name)

                    topic_blob_name = f"{self.dest_prefix}{filename}.json"

                    # Check if topic file already exists (for upsert)
                    try:
                        existing_blob = self.dest_container_client.get_blob_client(
                            topic_blob_name
                        )
                        existing_data = existing_blob.download_blob().readall()
                        existing_topic = json.loads(existing_data)

                        # Merge/update existing topic data
                        # Keep the earliest created date, update last_updated
                        if "created_at" in existing_topic:
                            cleaned_topic["created_at"] = existing_topic["created_at"]
                        else:
                            cleaned_topic["created_at"] = cleaned_topic["last_updated"]

                        logger.debug(f"Updating existing topic: {topic_name}")
                    except Exception:
                        # Topic file doesn't exist, this is a new topic
                        cleaned_topic["created_at"] = cleaned_topic["last_updated"]
                        logger.debug(f"Creating new topic: {topic_name}")

                    # Upload the topic file
                    topic_blob_client = self.dest_container_client.get_blob_client(
                        topic_blob_name
                    )
                    topic_json = json.dumps(cleaned_topic, indent=2, ensure_ascii=False)
                    topic_blob_client.upload_blob(topic_json, overwrite=True)

                    topics_found += 1

            logger.info(f"[OK] Processed {blob_name}: extracted {topics_found} topics")
            return topics_found

        except Exception as e:
            logger.error(f"[FAIL] Failed to process {blob_name}: {e}")
            return -1

    def process_all(self, max_files: Optional[int] = None) -> Dict[str, int]:
        """
        Process all blobs in the source prefix and extract topics.

        Args:
            max_files: Maximum number of files to process (None for all)

        Returns:
            Dict with processing statistics
        """
        logger.info(
            f"Starting to extract topics from {self.source_container}/{self.source_prefix}"
        )

        # List all blobs with source prefix
        blob_list = self.source_container_client.list_blobs(
            name_starts_with=self.source_prefix
        )

        processed = 0
        failed = 0
        total_topics_extracted = 0

        for blob in blob_list:
            blob_name = blob.name

            # Skip directories
            if blob_name.endswith("/"):
                continue

            # Skip if already processed
            if self.state_manager.is_processed(blob_name):
                logger.debug(f"Skipping already processed: {blob_name}")
                continue

            # Process the blob
            result = self.process_blob(blob_name)
            if result >= 0:
                self.state_manager.mark_processed(blob_name)
                processed += 1
                total_topics_extracted += result
            else:
                self.state_manager.mark_failed(blob_name)
                failed += 1

            # Check if we've hit the max files limit
            if max_files and (processed + failed) >= max_files:
                logger.info(f"Reached max files limit: {max_files}")
                break

            # Progress logging
            if (processed + failed) % 10 == 0:
                logger.info(
                    f"Progress: {processed + failed} files ({processed} processed, {failed} failed)"
                )

        logger.info(
            f"Processing complete: {processed} processed, {failed} failed, {total_topics_extracted} topics extracted"
        )

        return {
            "processed": processed,
            "failed": failed,
            "total_topics_extracted": total_topics_extracted,
        }

    def get_stats(self) -> Dict[str, int]:
        """Get extraction statistics."""
        return {
            "total_processed": self.state_manager.get_processed_count(),
            "total_failed": self.state_manager.get_failed_count(),
            "unique_topics": self.state_manager.get_topic_count(),
        }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Extract topics from DTIC works in Azure Blob Storage"
    )
    parser.add_argument(
        "--connection-string",
        default=os.environ.get("AZURE_STORAGE_CONNECTION_STRING"),
        help="Azure Storage connection string (or set AZURE_STORAGE_CONNECTION_STRING env var)",
    )
    parser.add_argument(
        "--source-container",
        default="raw",
        help="Source blob container name (default: raw)",
    )
    parser.add_argument(
        "--dest-container",
        default="clean",
        help="Destination blob container name (default: clean)",
    )
    parser.add_argument(
        "--source-prefix",
        default="dtic/works/",
        help="Source blob prefix for raw works (default: dtic/works/)",
    )
    parser.add_argument(
        "--dest-prefix",
        default="dtic/topics/",
        help="Destination blob prefix for topics (default: dtic/topics/)",
    )
    parser.add_argument(
        "--state-file",
        default="extraction_state_topics.json",
        help="State file path (default: extraction_state_topics.json)",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        help="Maximum number of files to process (default: all)",
    )
    parser.add_argument(
        "--request-delay",
        type=float,
        default=0.5,
        help="Delay between API requests in seconds (default: 0.5)",
    )
    parser.add_argument(
        "--no-amplification",
        action="store_true",
        help="Disable fetching amplifying data from DTIC API",
    )
    parser.add_argument("--stats", action="store_true", help="Show statistics and exit")

    args = parser.parse_args()

    # Check for connection string
    if not args.connection_string:
        logger.error("Azure Storage connection string is required")
        logger.error(
            "Set AZURE_STORAGE_CONNECTION_STRING environment variable or use --connection-string"
        )
        return 1

    try:
        # Initialize extractor
        extractor = DTICTopicExtractor(
            connection_string=args.connection_string,
            source_container=args.source_container,
            dest_container=args.dest_container,
            source_prefix=args.source_prefix,
            dest_prefix=args.dest_prefix,
            state_file=args.state_file,
            request_delay=args.request_delay,
            enable_amplification=not args.no_amplification,
        )

        # Show stats if requested
        if args.stats:
            stats = extractor.get_stats()
            logger.info("=== Extraction Statistics ===")
            for key, value in stats.items():
                logger.info(f"{key}: {value}")
            return 0

        # Process all works and extract topics
        results = extractor.process_all(max_files=args.max_files)

        # Show final stats
        stats = extractor.get_stats()
        logger.info("\n=== Final Statistics ===")
        logger.info(
            f"This run: {results['processed']} processed, {results['failed']} failed"
        )
        logger.info(
            f"This run: {results['total_topics_extracted']} topic instances extracted"
        )
        logger.info(f"Total files processed: {stats['total_processed']}")
        logger.info(f"Total files failed: {stats['total_failed']}")
        logger.info(f"Unique topics: {stats['unique_topics']}")

        return 0 if results["failed"] == 0 else 1

    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
