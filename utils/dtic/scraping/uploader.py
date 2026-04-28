"""
Azure Blob Storage Uploader for DTIC Publications.

Watches the dtic_publications folder and uploads new JSON files to Azure Blob Storage.
Maintains state of which files have been uploaded.
"""

import json
import logging
import time
import argparse
import os
from pathlib import Path
from typing import Dict
from datetime import datetime
from azure.storage.blob import BlobServiceClient

# Generate timestamped log filename
_log_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
_logs_dir = Path("logs")
_logs_dir.mkdir(exist_ok=True)
_log_filename = _logs_dir / f"{_log_timestamp}_uploader.log"

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


class UploadStateManager:
    """Manages state of uploaded files."""

    def __init__(self, state_file: str = "upload_state.json"):
        self.state_file = Path(state_file)
        self.state = self._load_state()

    def _load_state(self) -> Dict:
        """Load state from file or create new state."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                    logger.info(
                        f"Loaded state: {len(state.get('uploaded_files', []))} files uploaded"
                    )
                    return state
            except json.JSONDecodeError:
                logger.warning("Corrupted state file, starting fresh")

        return {"uploaded_files": [], "failed_files": [], "last_updated": None}

    def save_state(self):
        """Save current state to file."""
        self.state["last_updated"] = datetime.now().isoformat()
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)
        logger.debug("Upload state saved")

    def mark_uploaded(self, filename: str):
        """Mark a file as successfully uploaded."""
        if filename not in self.state["uploaded_files"]:
            self.state["uploaded_files"].append(filename)
            # Remove from failed if it was there
            if filename in self.state["failed_files"]:
                self.state["failed_files"].remove(filename)
            self.save_state()

    def mark_failed(self, filename: str):
        """Mark a file as failed to upload."""
        if filename not in self.state["failed_files"]:
            self.state["failed_files"].append(filename)
            self.save_state()

    def is_uploaded(self, filename: str) -> bool:
        """Check if file has been uploaded."""
        return filename in self.state["uploaded_files"]

    def get_uploaded_count(self) -> int:
        """Get count of uploaded files."""
        return len(self.state["uploaded_files"])

    def get_failed_count(self) -> int:
        """Get count of failed files."""
        return len(self.state["failed_files"])


class AzureBlobUploader:
    """Uploads DTIC publications to Azure Blob Storage."""

    def __init__(
        self,
        connection_string: str,
        container_name: str,
        publications_dir: str = "dtic_publications",
        state_file: str = "upload_state.json",
        blob_prefix: str = "dtic/works/",
    ):
        """
        Initialize the uploader.

        Args:
            connection_string: Azure Storage connection string
            container_name: Name of the blob container
            publications_dir: Directory containing publication JSON files
            state_file: State file path
            blob_prefix: Prefix for blob names in container
        """
        self.publications_dir = Path(publications_dir)
        self.state_manager = UploadStateManager(state_file)
        self.blob_prefix = blob_prefix

        # Initialize Azure Blob Storage client
        try:
            self.blob_service_client = BlobServiceClient.from_connection_string(
                connection_string
            )
            self.container_client = self.blob_service_client.get_container_client(
                container_name
            )

            # Create container if it doesn't exist
            try:
                self.container_client.create_container()
                logger.info(f"Created new container: {container_name}")
            except Exception:
                # Container already exists
                pass

            logger.info(f"Connected to Azure Blob Storage container: {container_name}")
        except Exception as e:
            logger.error(f"Failed to connect to Azure Blob Storage: {e}")
            raise

    def upload_file(self, file_path: Path) -> bool:
        """
        Upload a single file to Azure Blob Storage.

        Args:
            file_path: Path to the file to upload

        Returns:
            True if successful, False otherwise
        """
        try:
            filename = file_path.name
            blob_name = f"{self.blob_prefix}{filename}"

            # Read file content
            with open(file_path, "rb") as data:
                blob_client = self.container_client.get_blob_client(blob_name)
                blob_client.upload_blob(data, overwrite=True)

            logger.info(f"[OK] Uploaded: {filename} -> {blob_name}")
            return True

        except Exception as e:
            logger.error(f"[FAIL] Failed to upload {file_path.name}: {e}")
            return False

    def scan_and_upload(self) -> tuple[int, int]:
        """
        Scan publications directory and upload new files.

        Returns:
            Tuple of (uploaded_count, failed_count)
        """
        if not self.publications_dir.exists():
            logger.error(
                f"Publications directory does not exist: {self.publications_dir}"
            )
            return 0, 0

        json_files = list(self.publications_dir.glob("*.json"))
        logger.info(f"Found {len(json_files)} JSON files in {self.publications_dir}")

        uploaded = 0
        failed = 0

        for json_file in json_files:
            filename = json_file.name

            # Skip if already uploaded
            if self.state_manager.is_uploaded(filename):
                logger.debug(f"Skipping already uploaded: {filename}")
                continue

            # Try to upload
            if self.upload_file(json_file):
                self.state_manager.mark_uploaded(filename)
                uploaded += 1
            else:
                self.state_manager.mark_failed(filename)
                failed += 1

        return uploaded, failed

    def watch_and_upload(self, interval: int = 10):
        """
        Continuously watch directory and upload new files.

        Args:
            interval: Seconds between scans
        """
        logger.info(f"Starting watch mode (checking every {interval} seconds)")
        logger.info(f"Watching directory: {self.publications_dir.absolute()}")
        logger.info("Press Ctrl+C to stop")

        try:
            while True:
                uploaded, failed = self.scan_and_upload()

                if uploaded > 0 or failed > 0:
                    logger.info(f"Batch complete: {uploaded} uploaded, {failed} failed")

                total_uploaded = self.state_manager.get_uploaded_count()
                total_failed = self.state_manager.get_failed_count()
                logger.info(f"Total: {total_uploaded} uploaded, {total_failed} failed")

                time.sleep(interval)

        except KeyboardInterrupt:
            logger.info("Watch mode stopped by user")

    def upload_all(self):
        """Upload all files once and exit."""
        logger.info("Uploading all files...")
        uploaded, failed = self.scan_and_upload()

        total_uploaded = self.state_manager.get_uploaded_count()
        total_failed = self.state_manager.get_failed_count()

        logger.info("=" * 60)
        logger.info("Upload Summary")
        logger.info("=" * 60)
        logger.info(f"This run: {uploaded} uploaded, {failed} failed")
        logger.info(f"Total: {total_uploaded} uploaded, {total_failed} failed")
        logger.info("=" * 60)


def main():
    """Main entry point for the uploader."""
    parser = argparse.ArgumentParser(
        description="Azure Blob Storage Uploader for DTIC Publications"
    )
    parser.add_argument(
        "--connection-string",
        "-c",
        help="Azure Storage connection string (or set AZURE_STORAGE_CONNECTION_STRING env var)",
    )
    parser.add_argument(
        "--container", "-n", default="raw", help="Container name (default: raw)"
    )
    parser.add_argument(
        "--publications-dir",
        "-d",
        default="dtic_publications",
        help="Publications directory (default: dtic_publications)",
    )
    parser.add_argument(
        "--state",
        "-s",
        default="upload_state.json",
        help="State file path (default: upload_state.json)",
    )
    parser.add_argument(
        "--blob-prefix",
        "-p",
        default="dtic/works/",
        help="Blob prefix in container (default: dtic/works/)",
    )
    parser.add_argument(
        "--watch",
        "-w",
        action="store_true",
        help="Watch mode: continuously monitor and upload",
    )
    parser.add_argument(
        "--interval",
        "-i",
        type=int,
        default=10,
        help="Watch interval in seconds (default: 10)",
    )

    args = parser.parse_args()

    # Get connection string from args or environment variable
    connection_string = args.connection_string or os.environ.get(
        "AZURE_STORAGE_CONNECTION_STRING"
    )

    if not connection_string:
        parser.error(
            "Connection string is required. Provide via --connection-string or set AZURE_STORAGE_CONNECTION_STRING environment variable."
        )

    uploader = AzureBlobUploader(
        connection_string=connection_string,
        container_name=args.container,
        publications_dir=args.publications_dir,
        state_file=args.state,
        blob_prefix=args.blob_prefix,
    )

    if args.watch:
        uploader.watch_and_upload(interval=args.interval)
    else:
        uploader.upload_all()


if __name__ == "__main__":
    main()
