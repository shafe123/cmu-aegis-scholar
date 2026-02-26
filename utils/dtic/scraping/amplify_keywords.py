"""
Amplify DTIC publications with actual keywords fetched from URLs.

This script reads DTIC JSON files from Azure Blob Storage, fetches the actual
keywords from the URLs in the 'keywords' field, and saves the amplified data
back to blob storage with a different prefix.
"""

import json
import logging
import argparse
import os
import time
import requests
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from azure.storage.blob import BlobServiceClient
from urllib.parse import urljoin

# Generate timestamped log filename
_log_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
_logs_dir = Path("logs")
_logs_dir.mkdir(exist_ok=True)
_log_filename = _logs_dir / f"{_log_timestamp}_amplify_keywords.log"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(_log_filename, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Quiet Azure SDK loggers
logging.getLogger('azure').setLevel(logging.WARNING)
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)


class AmplifyStateManager:
    """Manages state of amplified files."""
    
    def __init__(self, state_file: str = "amplify_state.json"):
        self.state_file = Path(state_file)
        self.state = self._load_state()
    
    def _load_state(self) -> Dict:
        """Load state from file or create new state."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    logger.info(f"Loaded state: {len(state.get('amplified_files', []))} files amplified")
                    return state
            except json.JSONDecodeError:
                logger.warning("Corrupted state file, starting fresh")
        
        return {
            'amplified_files': [],
            'failed_files': [],
            'skipped_files': [],  # Files with no keywords to fetch
            'last_updated': None,
            'total_amplified': 0
        }
    
    def save_state(self):
        """Save current state to file."""
        self.state['last_updated'] = datetime.now().isoformat()
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, indent=2)
        logger.debug("Amplify state saved")
    
    def mark_amplified(self, blob_name: str):
        """Mark a blob as successfully amplified."""
        if blob_name not in self.state['amplified_files']:
            self.state['amplified_files'].append(blob_name)
            self.state['total_amplified'] += 1
            # Remove from failed/skipped if it was there
            if blob_name in self.state['failed_files']:
                self.state['failed_files'].remove(blob_name)
            if blob_name in self.state['skipped_files']:
                self.state['skipped_files'].remove(blob_name)
            self.save_state()
    
    def mark_failed(self, blob_name: str):
        """Mark a blob as failed to amplify."""
        if blob_name not in self.state['failed_files']:
            self.state['failed_files'].append(blob_name)
            self.save_state()
    
    def mark_skipped(self, blob_name: str):
        """Mark a blob as skipped (no keywords to fetch)."""
        if blob_name not in self.state['skipped_files']:
            self.state['skipped_files'].append(blob_name)
            self.save_state()
    
    def is_amplified(self, blob_name: str) -> bool:
        """Check if blob has been amplified."""
        return blob_name in self.state['amplified_files']
    
    def get_amplified_count(self) -> int:
        """Get count of amplified files."""
        return len(self.state['amplified_files'])
    
    def get_failed_count(self) -> int:
        """Get count of failed files."""
        return len(self.state['failed_files'])
    
    def get_skipped_count(self) -> int:
        """Get count of skipped files."""
        return len(self.state['skipped_files'])


class KeywordAmplifier:
    """Amplifies DTIC publications with actual keywords from URLs."""
    
    BASE_URL = "https://dtic.dimensions.ai"
    
    def __init__(self,
                 connection_string: str,
                 container_name: str,
                 source_prefix: str = "dtic/works/",
                 dest_prefix: str = "dtic/works_amplified/",
                 state_file: str = "amplify_state.json",
                 request_delay: float = 0.5):
        """
        Initialize the keyword amplifier.
        
        Args:
            connection_string: Azure Storage connection string
            container_name: Name of the blob container
            source_prefix: Prefix for source blobs
            dest_prefix: Prefix for amplified blobs
            state_file: State file path
            request_delay: Delay between HTTP requests in seconds
        """
        self.source_prefix = source_prefix
        self.dest_prefix = dest_prefix
        self.state_manager = AmplifyStateManager(state_file)
        self.request_delay = request_delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Initialize Azure Blob Storage client
        try:
            self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
            self.container_client = self.blob_service_client.get_container_client(container_name)
            logger.info(f"Connected to Azure Blob Storage container: {container_name}")
        except Exception as e:
            logger.error(f"Failed to connect to Azure Blob Storage: {e}")
            raise
    
    def fetch_keywords(self, keyword_url_path: str) -> Optional[List[str]]:
        """
        Fetch keywords from the DTIC dimensions.ai URL.
        
        Args:
            keyword_url_path: Path to append to base URL (e.g., '/details/sources/...')
            
        Returns:
            List of keyword strings or None if failed
        """
        try:
            full_url = urljoin(self.BASE_URL, keyword_url_path)
            logger.debug(f"Fetching keywords from: {full_url}")
            
            response = self.session.get(full_url, timeout=30)
            response.raise_for_status()
            
            # Parse JSON response
            keywords_data = response.json()
            
            # Extract keywords - the structure may vary, handle different cases
            if isinstance(keywords_data, list):
                return keywords_data
            elif isinstance(keywords_data, dict):
                # Try common field names
                for field in ['keywords', 'fields', 'subjects', 'for', 'data']:
                    if field in keywords_data:
                        return keywords_data[field] if isinstance(keywords_data[field], list) else [keywords_data[field]]
                # If no known field, return the whole dict as a single item
                return [keywords_data]
            else:
                return [str(keywords_data)]
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to fetch keywords from {keyword_url_path}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse keywords JSON from {keyword_url_path}: {e}")
            return None
    
    def amplify_publication(self, pub_data: Dict) -> Dict:
        """
        Amplify a single publication document with actual keywords.
        
        Args:
            pub_data: Publication JSON data
            
        Returns:
            Amplified publication data
        """
        if 'keywords' not in pub_data or not pub_data['keywords']:
            logger.debug("No keywords field or empty keywords")
            return pub_data
        
        keywords = pub_data['keywords']
        if not isinstance(keywords, list):
            logger.warning("Keywords field is not a list")
            return pub_data
        
        # Check if keywords are URL paths (strings starting with / or http)
        amplified_keywords = []
        original_urls = []
        fetch_count = 0
        
        for keyword in keywords:
            if isinstance(keyword, str) and (keyword.startswith('/') or keyword.startswith('http')):
                # This is a URL, save it and fetch the actual keywords
                original_urls.append(keyword)
                logger.info(f"Fetching keywords from: {keyword}")
                fetched = self.fetch_keywords(keyword)
                if fetched:
                    amplified_keywords.extend(fetched)
                    fetch_count += 1
                    # Rate limiting
                    time.sleep(self.request_delay)
                else:
                    # Keep the original URL if fetch failed
                    amplified_keywords.append(keyword)
            else:
                # Already a keyword, keep it
                amplified_keywords.append(keyword)
        
        if fetch_count > 0:
            pub_data['keywords'] = amplified_keywords
            pub_data['keywords_urls'] = original_urls  # Preserve original URLs
            pub_data['keywords_amplified'] = True
            pub_data['keywords_amplified_at'] = datetime.now().isoformat()
            logger.info(f"Amplified {fetch_count} keyword URL(s)")
        
        return pub_data
    
    def process_blob(self, blob_name: str) -> bool:
        """
        Process a single blob: download, amplify, and upload.
        
        Args:
            blob_name: Name of the blob to process
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Download blob
            logger.info(f"Processing: {blob_name}")
            blob_client = self.container_client.get_blob_client(blob_name)
            blob_data = blob_client.download_blob()
            content = blob_data.readall()
            
            # Parse JSON
            pub_data = json.loads(content.decode('utf-8'))
            
            # Amplify with keywords
            amplified_data = self.amplify_publication(pub_data)
            
            # Upload amplified version
            dest_blob_name = blob_name.replace(self.source_prefix, self.dest_prefix, 1)
            dest_blob_client = self.container_client.get_blob_client(dest_blob_name)
            
            amplified_json = json.dumps(amplified_data, indent=2, ensure_ascii=False)
            dest_blob_client.upload_blob(amplified_json.encode('utf-8'), overwrite=True)
            
            logger.info(f"[OK] Uploaded amplified version: {dest_blob_name}")
            return True
            
        except Exception as e:
            logger.error(f"[FAIL] Failed to process {blob_name}: {e}")
            return False
    
    def list_source_blobs(self) -> List[str]:
        """
        List all JSON blobs with the source prefix.
        
        Returns:
            List of blob names
        """
        try:
            blob_list = []
            for blob in self.container_client.list_blobs(name_starts_with=self.source_prefix):
                if blob.name.endswith('.json'):
                    blob_list.append(blob.name)
            
            logger.info(f"Found {len(blob_list)} JSON blobs with prefix '{self.source_prefix}'")
            return blob_list
        
        except Exception as e:
            logger.error(f"Failed to list blobs: {e}")
            return []
    
    def amplify_all(self, max_files: Optional[int] = None) -> tuple[int, int, int]:
        """
        Amplify all publications in the source prefix.
        
        Args:
            max_files: Maximum number of files to process (None for all)
            
        Returns:
            Tuple of (amplified_count, failed_count, skipped_count)
        """
        blob_list = self.list_source_blobs()
        
        if not blob_list:
            logger.warning("No blobs found to process")
            return 0, 0, 0
        
        amplified = 0
        failed = 0
        skipped = 0
        
        for i, blob_name in enumerate(blob_list):
            if max_files and i >= max_files:
                logger.info(f"Reached max_files limit ({max_files})")
                break
            
            # Skip if already amplified
            if self.state_manager.is_amplified(blob_name):
                logger.debug(f"Skipping already amplified: {blob_name}")
                skipped += 1
                continue
            
            # Process the blob
            if self.process_blob(blob_name):
                self.state_manager.mark_amplified(blob_name)
                amplified += 1
            else:
                self.state_manager.mark_failed(blob_name)
                failed += 1
            
            # Progress update
            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i + 1}/{len(blob_list)} processed")
        
        return amplified, failed, skipped


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Amplify DTIC publications with actual keywords from URLs'
    )
    parser.add_argument(
        '--connection-string',
        help='Azure Storage connection string (or set AZURE_STORAGE_CONNECTION_STRING env var)'
    )
    parser.add_argument(
        '--container',
        default='raw',
        help='Blob container name (default: raw)'
    )
    parser.add_argument(
        '--source-prefix',
        default='dtic/works/',
        help='Source blob prefix (default: dtic/works/)'
    )
    parser.add_argument(
        '--dest-prefix',
        default='dtic/works/',
        help='Destination blob prefix (default: dtic/works/)'
    )
    parser.add_argument(
        '--state-file',
        default='amplify_state.json',
        help='State file path (default: amplify_state.json)'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=0.5,
        help='Delay between HTTP requests in seconds (default: 0.5)'
    )
    parser.add_argument(
        '--max-files',
        type=int,
        help='Maximum number of files to process (default: all)'
    )
    
    args = parser.parse_args()
    
    # Get connection string
    connection_string = args.connection_string or os.getenv('AZURE_STORAGE_CONNECTION_STRING')
    if not connection_string:
        logger.error("Azure Storage connection string not provided")
        logger.error("Use --connection-string or set AZURE_STORAGE_CONNECTION_STRING environment variable")
        return 1
    
    try:
        # Create amplifier
        amplifier = KeywordAmplifier(
            connection_string=connection_string,
            container_name=args.container,
            source_prefix=args.source_prefix,
            dest_prefix=args.dest_prefix,
            state_file=args.state_file,
            request_delay=args.delay
        )
        
        logger.info("=" * 80)
        logger.info("Starting keyword amplification")
        logger.info(f"Container: {args.container}")
        logger.info(f"Source prefix: {args.source_prefix}")
        logger.info(f"Destination prefix: {args.dest_prefix}")
        logger.info(f"Request delay: {args.delay}s")
        if args.max_files:
            logger.info(f"Max files: {args.max_files}")
        logger.info("=" * 80)
        
        # Amplify all publications
        amplified, failed, skipped = amplifier.amplify_all(max_files=args.max_files)
        
        logger.info("=" * 80)
        logger.info("Amplification complete!")
        logger.info(f"Amplified: {amplified}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Skipped: {skipped}")
        logger.info(f"State file: {args.state_file}")
        logger.info(f"Log file: {_log_filename}")
        logger.info("=" * 80)
        
        return 0
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    exit(main())
