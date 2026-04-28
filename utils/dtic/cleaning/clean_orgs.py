"""
DTIC Organization Extractor.

This script extracts organizations from raw DTIC works in Azure Blob Storage
(raw/dtic/works/ prefix) and saves them as individual JSON files in the
clean/dtic/orgs/ prefix, following the AEGIS Scholar database schema.

Features:
- Reads raw DTIC work JSON files from Azure Blob Storage
- Extracts organization information
- Transforms data to match the Organization schema in database_schemas.json
- Fetches amplifying information from DTIC API endpoints
- Generates consistent GUIDs for organizations
- Implements upsert functionality (updates existing org files)
- State management for tracking processed files
"""

import json
import logging
import argparse
import os
import time
import requests
import uuid
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
from azure.storage.blob import BlobServiceClient
from urllib.parse import urljoin

# Generate timestamped log filename
_log_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
_logs_dir = Path("logs")
_logs_dir.mkdir(exist_ok=True)
_log_filename = _logs_dir / f"{_log_timestamp}_extract_orgs.log"

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
    """Manages state of processed files and discovered organizations."""

    def __init__(self, state_file: str = "extraction_state.json"):
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
            "organizations": {},  # grid_id -> org_id mapping
            "last_updated": None,
            "total_processed": 0,
            "total_orgs_found": 0,
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

    def get_or_create_org_id(self, grid_id: str) -> str:
        """Get existing org_id or create a new one."""
        if grid_id not in self.state["organizations"]:
            # Generate deterministic GUID based on grid_id.
            # Keep this aligned with clean_works.py and clean_authors.py.
            namespace = uuid.UUID("00000000-0000-0000-0000-000000000001")
            org_uuid = uuid.uuid5(namespace, grid_id)
            self.state["organizations"][grid_id] = f"org_{org_uuid}"
            self.state["total_orgs_found"] += 1
            self.save_state()

        return self.state["organizations"][grid_id]

    def get_processed_count(self) -> int:
        """Get count of processed files."""
        return len(self.state["processed_files"])

    def get_failed_count(self) -> int:
        """Get count of failed files."""
        return len(self.state["failed_files"])

    def get_org_count(self) -> int:
        """Get count of unique organizations."""
        return len(self.state["organizations"])


class DTICOrgExtractor:
    """Extracts organizations from DTIC works and transforms to schema format."""

    DTIC_BASE_URL = "https://dtic.dimensions.ai"

    def __init__(
        self,
        connection_string: str,
        source_container: str,
        dest_container: str,
        source_prefix: str = "dtic/works/",
        dest_prefix: str = "dtic/orgs/",
        state_file: str = "extraction_state.json",
        request_delay: float = 0.5,
        enable_amplification: bool = True,
    ):
        """
        Initialize the organization extractor.

        Args:
            connection_string: Azure Storage connection string
            source_container: Name of source blob container (e.g., 'raw')
            dest_container: Name of destination blob container (e.g., 'clean')
            source_prefix: Prefix for source blobs (raw works)
            dest_prefix: Prefix for organization files
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

        logger.info("Initialized DTICOrgExtractor")
        logger.info(f"  Source: {source_container}/{source_prefix}")
        logger.info(f"  Destination: {dest_container}/{dest_prefix}")
        logger.info(
            f"  Amplification: {'enabled' if enable_amplification else 'disabled'}"
        )

    def fetch_org_info(self, grid_id: str) -> Optional[Dict]:
        """
        Fetch organization/funder information from DTIC API.

        Args:
            grid_id: The GRID organization ID

        Returns:
            Dict with organization information or None if failed
        """
        if not self.enable_amplification:
            return None

        try:
            # Try both endpoints mentioned in the requirements
            endpoints = [
                f"/details/facets/publication/funder/{grid_id}/box.json",
                f"/discover/publication/results.json?and_facet_funder={grid_id}",
            ]

            for endpoint in endpoints:
                full_url = urljoin(self.DTIC_BASE_URL, endpoint)
                logger.debug(f"Fetching org info from: {full_url}")

                response = self.session.get(full_url, timeout=30)
                response.raise_for_status()

                data = response.json()
                if data:
                    return data

                # Rate limiting
                time.sleep(self.request_delay)

            return None

        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to fetch org info for {grid_id}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse org info JSON for {grid_id}: {e}")
            return None

    def extract_and_clean_org(self, grid_id: str, org_data: Dict) -> Optional[Dict]:
        """
        Extract and clean a single organization.

        Args:
            grid_id: The GRID organization ID
            org_data: Raw organization data from work

        Returns:
            Cleaned organization dict or None if invalid
        """
        if not grid_id:
            return None

        org_id = self.state_manager.get_or_create_org_id(grid_id)

        # Build organization entity following schema
        org_entity = {
            "id": org_id,
            "name": org_data.get("name", ""),
            "sources": [{"source": "dtic", "id": grid_id}],
            "last_updated": datetime.now().isoformat(),
        }

        # Add optional fields
        if org_data.get("country"):
            org_entity["country"] = org_data["country"]

        if org_data.get("type"):
            # Validate type enum
            org_type = org_data["type"]
            if org_type in ["institution", "funder", "publisher", "other"]:
                org_entity["type"] = org_type
            else:
                org_entity["type"] = "other"

        # Try to fetch amplifying information from DTIC API
        if self.enable_amplification:
            api_data = self.fetch_org_info(grid_id)
            if api_data:
                # Merge any additional information from API
                # This depends on what the API returns
                logger.debug(f"Fetched amplifying data for {grid_id}")

        return org_entity

    def process_blob(self, blob_name: str) -> int:
        """
        Process a single blob: read raw work and extract organizations.

        Args:
            blob_name: Name of the blob to process

        Returns:
            Number of organizations extracted, or -1 if failed
        """
        try:
            # Download raw work data
            blob_client = self.source_container_client.get_blob_client(blob_name)
            raw_data = blob_client.download_blob().readall()
            raw_work = json.loads(raw_data)

            logger.debug(f"Processing: {raw_work.get('publication_id', 'unknown')}")

            # Extract organizations from the work
            orgs_found = 0
            for org_data in raw_work.get("organizations", []):
                grid_id = org_data.get("org_id")
                if not grid_id:
                    logger.debug(
                        f"Skipping org without grid_id: {org_data.get('name', 'unknown')}"
                    )
                    continue

                # Clean the organization
                cleaned_org = self.extract_and_clean_org(grid_id, org_data)
                if not cleaned_org:
                    continue

                # Check if org file already exists (for upsert)
                org_blob_name = f"{self.dest_prefix}{grid_id}.json"
                try:
                    # Try to download existing org file
                    existing_blob = self.dest_container_client.get_blob_client(
                        org_blob_name
                    )
                    existing_data = existing_blob.download_blob().readall()
                    existing_org = json.loads(existing_data)

                    # Merge/update existing org data
                    # Keep the earliest created date, update last_updated
                    if "created_at" in existing_org:
                        cleaned_org["created_at"] = existing_org["created_at"]
                    else:
                        cleaned_org["created_at"] = cleaned_org["last_updated"]

                    logger.debug(f"Updating existing org: {grid_id}")
                except Exception:
                    # Org file doesn't exist, this is a new org
                    cleaned_org["created_at"] = cleaned_org["last_updated"]
                    logger.debug(f"Creating new org: {grid_id}")

                # Upload the org file
                org_blob_client = self.dest_container_client.get_blob_client(
                    org_blob_name
                )
                org_json = json.dumps(cleaned_org, indent=2, ensure_ascii=False)
                org_blob_client.upload_blob(org_json, overwrite=True)

                orgs_found += 1

            logger.info(
                f"[OK] Processed {blob_name}: extracted {orgs_found} organizations"
            )
            return orgs_found

        except Exception as e:
            logger.error(f"[FAIL] Failed to process {blob_name}: {e}")
            return -1

    def process_all(self, max_files: Optional[int] = None) -> Dict[str, int]:
        """
        Process all blobs in the source prefix and extract organizations.

        Args:
            max_files: Maximum number of files to process (None for all)

        Returns:
            Dict with processing statistics
        """
        logger.info(
            f"Starting to extract organizations from {self.source_container}/{self.source_prefix}"
        )

        # List all blobs with source prefix
        blob_list = self.source_container_client.list_blobs(
            name_starts_with=self.source_prefix
        )

        processed = 0
        failed = 0
        total_orgs_extracted = 0

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
                total_orgs_extracted += result
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
            f"Processing complete: {processed} processed, {failed} failed, {total_orgs_extracted} orgs extracted"
        )

        return {
            "processed": processed,
            "failed": failed,
            "total_orgs_extracted": total_orgs_extracted,
        }

    def get_stats(self) -> Dict[str, int]:
        """Get extraction statistics."""
        return {
            "total_processed": self.state_manager.get_processed_count(),
            "total_failed": self.state_manager.get_failed_count(),
            "unique_organizations": self.state_manager.get_org_count(),
        }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Extract organizations from DTIC works in Azure Blob Storage"
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
        default="dtic/orgs/",
        help="Destination blob prefix for organizations (default: dtic/orgs/)",
    )
    parser.add_argument(
        "--state-file",
        default="extraction_state.json",
        help="State file path (default: extraction_state.json)",
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
        extractor = DTICOrgExtractor(
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

        # Process all works and extract organizations
        results = extractor.process_all(max_files=args.max_files)

        # Show final stats
        stats = extractor.get_stats()
        logger.info("\n=== Final Statistics ===")
        logger.info(
            f"This run: {results['processed']} processed, {results['failed']} failed"
        )
        logger.info(
            f"This run: {results['total_orgs_extracted']} org instances extracted"
        )
        logger.info(f"Total files processed: {stats['total_processed']}")
        logger.info(f"Total files failed: {stats['total_failed']}")
        logger.info(f"Unique organizations: {stats['unique_organizations']}")

        return 0 if results["failed"] == 0 else 1

    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
