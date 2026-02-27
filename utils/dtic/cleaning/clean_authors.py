"""
DTIC Author Extractor.

This script extracts authors from raw DTIC works in Azure Blob Storage 
(raw/dtic/works/ prefix) and saves them as individual JSON files in the 
clean/dtic/authors/ prefix, following the AEGIS Scholar database schema.

Features:
- Reads raw DTIC work JSON files from Azure Blob Storage
- Extracts author information from DTIC works
- Transforms data to match the Author schema in database_schemas.json
- Generates consistent GUIDs for authors
- Implements upsert functionality (updates existing author files)
- State management for tracking processed files
- Optional API amplification for additional author metrics
"""

import json
import logging
import argparse
import os
import time
import requests
import uuid
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from azure.storage.blob import BlobServiceClient
from urllib.parse import urljoin

# Generate timestamped log filename
_log_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
_logs_dir = Path("logs")
_logs_dir.mkdir(exist_ok=True)
_log_filename = _logs_dir / f"{_log_timestamp}_extract_authors.log"

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


class ExtractionStateManager:
    """Manages state of processed files and discovered authors."""
    
    def __init__(self, state_file: str = "extraction_state_authors.json"):
        self.state_file = Path(state_file)
        self.state = self._load_state()
    
    def _load_state(self) -> Dict:
        """Load state from file or create new state."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    logger.info(f"Loaded state: {len(state.get('processed_files', []))} files processed")
                    return state
            except json.JSONDecodeError:
                logger.warning("Corrupted state file, starting fresh")
        
        return {
            'processed_files': [],
            'failed_files': [],
            'authors': {},  # researcher_id -> author_id mapping
            'last_updated': None,
            'total_processed': 0,
            'total_authors_found': 0
        }
    
    def save_state(self):
        """Save current state to file with retry logic for Windows file locking."""
        self.state['last_updated'] = datetime.now().isoformat()
        
        # Retry logic for occasional Windows file locking issues
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Write to temp file first, then rename (atomic operation)
                temp_file = self.state_file.with_suffix('.tmp')
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(self.state, f, indent=2)
                
                # Atomic rename
                temp_file.replace(self.state_file)
                logger.debug("Extraction state saved")
                return
                
            except (OSError, IOError) as e:
                if attempt < max_retries - 1:
                    logger.debug(f"Save state attempt {attempt + 1} failed, retrying: {e}")
                    time.sleep(0.1)  # Brief delay before retry
                else:
                    logger.warning(f"Failed to save state after {max_retries} attempts: {e}")
                    # Don't raise - continue processing without saving state
    
    def mark_processed(self, blob_name: str):
        """Mark a blob as successfully processed."""
        if blob_name not in self.state['processed_files']:
            self.state['processed_files'].append(blob_name)
            self.state['total_processed'] += 1
            # Remove from failed if it was there
            if blob_name in self.state['failed_files']:
                self.state['failed_files'].remove(blob_name)
            self.save_state()
    
    def mark_failed(self, blob_name: str):
        """Mark a blob as failed to process."""
        if blob_name not in self.state['failed_files']:
            self.state['failed_files'].append(blob_name)
            self.save_state()
    
    def is_processed(self, blob_name: str) -> bool:
        """Check if blob has been processed."""
        return blob_name in self.state['processed_files']
    
    def get_or_create_author_id(self, researcher_id: str) -> str:
        """Get existing author_id or create a new one."""
        if researcher_id not in self.state['authors']:
            # Generate deterministic GUID based on researcher_id
            namespace = uuid.UUID('00000000-0000-0000-0000-000000000002')  # Author namespace
            author_uuid = uuid.uuid5(namespace, researcher_id)
            self.state['authors'][researcher_id] = f"author_{author_uuid}"
            self.state['total_authors_found'] += 1
            self.save_state()
        
        return self.state['authors'][researcher_id]
    
    def get_processed_count(self) -> int:
        """Get count of processed files."""
        return len(self.state['processed_files'])
    
    def get_failed_count(self) -> int:
        """Get count of failed files."""
        return len(self.state['failed_files'])
    
    def get_author_count(self) -> int:
        """Get count of unique authors."""
        return len(self.state['authors'])


class DTICAuthorExtractor:
    """Extracts authors from DTIC works and transforms to schema format."""
    
    DTIC_BASE_URL = "https://dtic.dimensions.ai"
    
    def __init__(self,
                 connection_string: str,
                 source_container: str,
                 dest_container: str,
                 source_prefix: str = "dtic/works/",
                 dest_prefix: str = "dtic/authors/",
                 state_file: str = "extraction_state_authors.json",
                 request_delay: float = 0.5,
                 enable_amplification: bool = True):
        """
        Initialize the author extractor.
        
        Args:
            connection_string: Azure Storage connection string
            source_container: Name of source blob container (e.g., 'raw')
            dest_container: Name of destination blob container (e.g., 'clean')
            source_prefix: Prefix for source blobs (raw works)
            dest_prefix: Prefix for author files
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
        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        self.source_container_client = self.blob_service_client.get_container_client(source_container)
        self.dest_container_client = self.blob_service_client.get_container_client(dest_container)
        
        # Initialize state manager
        self.state_manager = ExtractionStateManager(state_file)
        
        # Initialize HTTP session for API requests
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'AEGIS-Scholar-Extractor/1.0'})
        
        logger.info("Initialized DTICAuthorExtractor")
        logger.info(f"  Source: {source_container}/{source_prefix}")
        logger.info(f"  Destination: {dest_container}/{dest_prefix}")
        logger.info(f"  Amplification: {'enabled' if enable_amplification else 'disabled'}")
    
    def fetch_author_info(self, researcher_id: str) -> Optional[Dict]:
        """
        Fetch author information from DTIC API.
        
        Args:
            researcher_id: The researcher ID (e.g., ur.015241325677.49)
            
        Returns:
            Dict with author information or None if failed.
            
            Response structure:
            {
                "id": "ur.XXXXX.XX",
                "first_name": "First",
                "last_name": "Last",
                "label": "Full Name",
                "orcid": ["0000-0000-0000-0000"],  // Added to sources if present
                "dim_current_research_org_id": "grid.xxxx.x",
                "sources": [
                    {
                        "id": "publication_plus",
                        "label": "DOD Publications",
                        "value": 123,  // works_count
                        "meta": [
                            {"id": "citations", "value": 456.0}  // citation_count
                        ]
                    }
                ]
            }
        """
        if not self.enable_amplification:
            return None
        
        try:
            # Build API URL
            url = f"{self.DTIC_BASE_URL}/details/facets/publication/researcher/{researcher_id}/box.json"
            logger.debug(f"Fetching author info from: {url}")
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Rate limiting
            time.sleep(self.request_delay)
            
            return data
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to fetch author info for {researcher_id}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse author info JSON for {researcher_id}: {e}")
            return None
    
    def extract_and_clean_author(self, 
                                  author_name: str, 
                                  researcher_id: str,
                                  affiliations: List[str] = None,
                                  org_id_mapping: Dict[str, str] = None,
                                  author_data: Optional[Dict] = None) -> Optional[Dict]:
        """
        Extract and clean a single author.
        
        Args:
            author_name: The author's name
            researcher_id: DTIC researcher ID
            affiliations: List of affiliation names
            org_id_mapping: Mapping of org names to org_ids (from organizations in work)
            author_data: Optional additional data from API
            
        Returns:
            Cleaned author dict or None if invalid
        """
        if not author_name or not researcher_id:
            return None
        
        author_id = self.state_manager.get_or_create_author_id(researcher_id)
        
        # Build author entity following schema
        author_entity = {
            'id': author_id,
            'name': author_name,
            'sources': [{
                'source': 'dtic',
                'id': researcher_id
            }],
            'last_updated': datetime.now().isoformat()
        }
        
        # Add org_ids from affiliations if we have org mapping
        if affiliations and org_id_mapping:
            org_ids = []
            for affiliation in affiliations:
                if affiliation in org_id_mapping:
                    org_ids.append(org_id_mapping[affiliation])
            if org_ids:
                author_entity['org_ids'] = org_ids
        
        # Add optional fields from API data if available
        if author_data and isinstance(author_data, dict):
            # Add ORCID to sources if available
            orcid_list = author_data.get('orcid', [])
            if orcid_list and len(orcid_list) > 0:
                # Add each ORCID as a separate source entry
                for orcid_id in orcid_list:
                    if orcid_id:  # Make sure it's not empty
                        author_entity['sources'].append({
                            'source': 'orcid',
                            'id': orcid_id
                        })
            
            # Parse DTIC API response structure:
            # sources[].id == "publication_plus" contains:
            #   - value: works_count
            #   - meta[].id == "citations" contains value: citation_count
            api_sources = author_data.get('sources', [])
            for source in api_sources:
                if source.get('id') == 'publication_plus':
                    # Extract works count
                    works_count = source.get('value')
                    if works_count is not None:
                        author_entity['works_count'] = int(works_count)
                    
                    # Extract citation count from meta
                    meta = source.get('meta', [])
                    for meta_item in meta:
                        if meta_item.get('id') == 'citations':
                            citation_count = meta_item.get('value')
                            if citation_count is not None:
                                author_entity['citation_count'] = int(citation_count)
                            break
                    break
            
            # Note: h_index is not available in DTIC API response
        
        return author_entity
    
    def process_blob(self, blob_name: str) -> int:
        """
        Process a single blob: read raw work and extract authors.
        
        Args:
            blob_name: Name of the blob to process
            
        Returns:
            Number of authors extracted, or -1 if failed
        """
        try:
            # Download raw work data
            blob_client = self.source_container_client.get_blob_client(blob_name)
            raw_data = blob_client.download_blob().readall()
            raw_work = json.loads(raw_data)
            
            logger.debug(f"Processing: {raw_work.get('publication_id', 'unknown')}")
            
            # Build org name to org_id mapping from organizations in this work
            org_id_mapping = {}
            for org in raw_work.get('organizations', []):
                if org.get('name') and org.get('org_id'):
                    org_id_mapping[org['name']] = self.get_org_guid_from_grid(org['org_id'])
            
            # Extract authors from the work
            authors_found = 0
            authors = raw_work.get('authors', [])
            
            for author in authors:
                author_name = author.get('name')
                researcher_id = author.get('researcher_id')
                affiliations = author.get('affiliations', [])
                
                if not author_name or not researcher_id:
                    logger.debug(f"Skipping author without name or ID: {author}")
                    continue
                
                # Fetch amplifying data if enabled
                author_data = None
                if self.enable_amplification:
                    author_data = self.fetch_author_info(researcher_id)
                
                # Clean the author
                cleaned_author = self.extract_and_clean_author(
                    author_name, 
                    researcher_id, 
                    affiliations,
                    org_id_mapping,
                    author_data
                )
                if not cleaned_author:
                    continue
                
                # Use researcher_id as filename
                author_blob_name = f"{self.dest_prefix}{researcher_id}.json"
                
                # Check if author file already exists (for upsert)
                try:
                    existing_blob = self.dest_container_client.get_blob_client(author_blob_name)
                    existing_data = existing_blob.download_blob().readall()
                    existing_author = json.loads(existing_data)
                    
                    # Merge/update existing author data
                    # Keep the earliest created date, update last_updated
                    if 'created_at' in existing_author:
                        cleaned_author['created_at'] = existing_author['created_at']
                    else:
                        cleaned_author['created_at'] = cleaned_author['last_updated']
                    
                    # Merge org_ids (keep unique)
                    if 'org_ids' in existing_author:
                        existing_org_ids = set(existing_author['org_ids'])
                        new_org_ids = set(cleaned_author.get('org_ids', []))
                        merged_org_ids = list(existing_org_ids | new_org_ids)
                        if merged_org_ids:
                            cleaned_author['org_ids'] = merged_org_ids
                    
                    logger.debug(f"Updating existing author: {author_name}")
                except Exception:
                    # Author file doesn't exist, this is a new author
                    cleaned_author['created_at'] = cleaned_author['last_updated']
                    logger.debug(f"Creating new author: {author_name}")
                
                # Upload the author file
                author_blob_client = self.dest_container_client.get_blob_client(author_blob_name)
                author_json = json.dumps(cleaned_author, indent=2, ensure_ascii=False)
                author_blob_client.upload_blob(author_json, overwrite=True)
                
                authors_found += 1
            
            logger.info(f"[OK] Processed {blob_name}: extracted {authors_found} authors")
            return authors_found
            
        except Exception as e:
            logger.error(f"[FAIL] Failed to process {blob_name}: {e}")
            return -1
    
    def get_org_guid_from_grid(self, grid_id: str) -> str:
        """
        Generate org GUID from GRID ID (same logic as org extractor).
        
        Args:
            grid_id: GRID ID like grid.213917.f
            
        Returns:
            Organization GUID with org_ prefix
        """
        namespace = uuid.UUID('00000000-0000-0000-0000-000000000001')
        org_uuid = uuid.uuid5(namespace, grid_id)
        return f"org_{org_uuid}"
    
    def process_all(self, max_files: Optional[int] = None) -> Dict[str, int]:
        """
        Process all blobs in the source prefix and extract authors.
        
        Args:
            max_files: Maximum number of files to process (None for all)
            
        Returns:
            Dict with processing statistics
        """
        logger.info(f"Starting to extract authors from {self.source_container}/{self.source_prefix}")
        
        # List all blobs with source prefix
        blob_list = self.source_container_client.list_blobs(name_starts_with=self.source_prefix)
        
        processed = 0
        failed = 0
        total_authors_extracted = 0
        
        for blob in blob_list:
            blob_name = blob.name
            
            # Skip directories
            if blob_name.endswith('/'):
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
                total_authors_extracted += result
            else:
                self.state_manager.mark_failed(blob_name)
                failed += 1
            
            # Check if we've hit the max files limit
            if max_files and (processed + failed) >= max_files:
                logger.info(f"Reached max files limit: {max_files}")
                break
            
            # Progress logging
            if (processed + failed) % 10 == 0:
                logger.info(f"Progress: {processed + failed} files ({processed} processed, {failed} failed)")
        
        logger.info(f"Processing complete: {processed} processed, {failed} failed, {total_authors_extracted} authors extracted")
        
        return {
            'processed': processed,
            'failed': failed,
            'total_authors_extracted': total_authors_extracted
        }
    
    def get_stats(self) -> Dict[str, int]:
        """Get extraction statistics."""
        return {
            'total_processed': self.state_manager.get_processed_count(),
            'total_failed': self.state_manager.get_failed_count(),
            'unique_authors': self.state_manager.get_author_count()
        }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Extract authors from DTIC works in Azure Blob Storage'
    )
    parser.add_argument(
        '--connection-string',
        default=os.environ.get('AZURE_STORAGE_CONNECTION_STRING'),
        help='Azure Storage connection string (or set AZURE_STORAGE_CONNECTION_STRING env var)'
    )
    parser.add_argument(
        '--source-container',
        default='raw',
        help='Source blob container name (default: raw)'
    )
    parser.add_argument(
        '--dest-container',
        default='clean',
        help='Destination blob container name (default: clean)'
    )
    parser.add_argument(
        '--source-prefix',
        default='dtic/works/',
        help='Source blob prefix for raw works (default: dtic/works/)'
    )
    parser.add_argument(
        '--dest-prefix',
        default='dtic/authors/',
        help='Destination blob prefix for authors (default: dtic/authors/)'
    )
    parser.add_argument(
        '--state-file',
        default='extraction_state_authors.json',
        help='State file path (default: extraction_state_authors.json)'
    )
    parser.add_argument(
        '--max-files',
        type=int,
        help='Maximum number of files to process (default: all)'
    )
    parser.add_argument(
        '--request-delay',
        type=float,
        default=0.5,
        help='Delay between API requests in seconds (default: 0.5)'
    )
    parser.add_argument(
        '--no-amplification',
        action='store_true',
        help='Disable fetching amplifying data from DTIC API'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics and exit'
    )
    
    args = parser.parse_args()
    
    # Check for connection string
    if not args.connection_string:
        logger.error("Azure Storage connection string is required")
        logger.error("Set AZURE_STORAGE_CONNECTION_STRING environment variable or use --connection-string")
        return 1
    
    try:
        # Initialize extractor
        extractor = DTICAuthorExtractor(
            connection_string=args.connection_string,
            source_container=args.source_container,
            dest_container=args.dest_container,
            source_prefix=args.source_prefix,
            dest_prefix=args.dest_prefix,
            state_file=args.state_file,
            request_delay=args.request_delay,
            enable_amplification=not args.no_amplification
        )
        
        # Show stats if requested
        if args.stats:
            stats = extractor.get_stats()
            logger.info("=== Extraction Statistics ===")
            for key, value in stats.items():
                logger.info(f"{key}: {value}")
            return 0
        
        # Process all works and extract authors
        results = extractor.process_all(max_files=args.max_files)
        
        # Show final stats
        stats = extractor.get_stats()
        logger.info("\n=== Final Statistics ===")
        logger.info(f"This run: {results['processed']} processed, {results['failed']} failed")
        logger.info(f"This run: {results['total_authors_extracted']} author instances extracted")
        logger.info(f"Total files processed: {stats['total_processed']}")
        logger.info(f"Total files failed: {stats['total_failed']}")
        logger.info(f"Unique authors: {stats['unique_authors']}")
        
        return 0 if results['failed'] == 0 else 1
        
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1


if __name__ == '__main__':
    exit(main())
