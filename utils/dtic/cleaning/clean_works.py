"""
DTIC Work Extractor

This script processes raw DTIC works from Azure Blob Storage and transforms them
to match the Work schema defined in database_schemas.json. Each work is saved as
an individual JSON file named by publication_id.

Features:
- Transforms raw DTIC works to clean Work schema format
- Links to author_ids, org_ids, and topic_ids using deterministic GUIDs
- Saves individual files named by publication_id (e.g., pub.1000004508.json)
- Upsert functionality: updates existing work files
- State management for resumable operations
- Builds relationships between works, authors, orgs, and topics

Usage:
    poetry run python clean_works.py [--max-files N] [--stats]

Example:
    poetry run python clean_works.py --max-files 100
"""

import os
import sys
import json
import logging
import argparse
import uuid
import time
from typing import Dict, List, Optional, Set
from pathlib import Path
from datetime import datetime
from azure.storage.blob import BlobServiceClient, ContainerClient
from azure.core.exceptions import ResourceNotFoundError
import requests

# Generate timestamped log filename
_log_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
_logs_dir = Path("logs")
_logs_dir.mkdir(exist_ok=True)
_log_filename = _logs_dir / f"{_log_timestamp}_extract_works.log"

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


class StateManager:
    """Manages extraction state for works."""
    
    def __init__(self, state_file: str = 'extraction_state_works.json'):
        self.state_file = state_file
        self.state = self.load_state()
    
    def load_state(self) -> Dict:
        """Load state from file or create new state."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                logger.info(f"Loaded state: {state['total_processed']} files processed")
                return state
            except Exception as e:
                logger.warning(f"Could not load state file: {e}")
        
        return {
            'processed_files': [],
            'failed_files': [],
            'works': {},  # publication_id -> work_id mapping
            'total_processed': 0,
            'last_updated': None
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
    
    def get_or_create_work_id(self, publication_id: str) -> str:
        """Get existing work_id or create a new one."""
        if publication_id not in self.state['works']:
            # Generate deterministic GUID based on publication_id
            namespace = uuid.UUID('00000000-0000-0000-0000-000000000003')
            work_uuid = uuid.uuid5(namespace, publication_id)
            work_id = f"work_{work_uuid}"
            self.state['works'][publication_id] = work_id
            self.save_state()
        return self.state['works'][publication_id]


class DTICWorkExtractor:
    """Extracts and cleans works from DTIC raw data."""
    
    def __init__(self,
                 source_container: str = 'raw',
                 source_prefix: str = 'dtic/works/',
                 dest_container: str = 'clean',
                 dest_prefix: str = 'dtic/works/'):
        """
        Initialize the work extractor.
        
        Args:
            source_container: Source container name
            source_prefix: Prefix for source blobs
            dest_container: Destination container name
            dest_prefix: Prefix for destination blobs
        """
        self.source_container = source_container
        self.source_prefix = source_prefix
        self.dest_container = dest_container
        self.dest_prefix = dest_prefix
        
        # Initialize Azure Blob Storage client
        connection_string = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
        if not connection_string:
            raise ValueError("AZURE_STORAGE_CONNECTION_STRING environment variable not set")
        
        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        self.source_container_client = self.blob_service_client.get_container_client(source_container)
        self.dest_container_client = self.blob_service_client.get_container_client(dest_container)
        
        # Initialize state manager
        self.state_manager = StateManager()
        
        logger.info(f"Initialized DTIC Work Extractor")
        logger.info(f"Source: {source_container}/{source_prefix}")
        logger.info(f"Destination: {dest_container}/{dest_prefix}")
    
    def get_author_guid_from_researcher_id(self, researcher_id: str) -> str:
        """
        Generate author GUID from researcher ID (same logic as author extractor).
        
        Args:
            researcher_id: Researcher ID like ur.015241325677.49
            
        Returns:
            Author GUID with author_ prefix
        """
        namespace = uuid.UUID('00000000-0000-0000-0000-000000000002')
        author_uuid = uuid.uuid5(namespace, researcher_id)
        return f"author_{author_uuid}"
    
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
    
    def get_topic_guid_from_uber_cat_id(self, uber_cat_id: str) -> str:
        """
        Generate topic GUID from uber_cat_id (same logic as topic extractor).
        
        Args:
            uber_cat_id: Topic ID like 80020 or 80208
            
        Returns:
            Topic GUID with topic_ prefix
        """
        namespace = uuid.UUID('00000000-0000-0000-0000-000000000004')
        topic_uuid = uuid.uuid5(namespace, uber_cat_id)
        return f"topic_{topic_uuid}"
    
    def extract_and_clean_work(self, raw_work: Dict) -> Optional[Dict]:
        """
        Extract and clean a single work.
        
        Args:
            raw_work: Raw work data from DTIC
            
        Returns:
            Cleaned work dict or None if invalid
        """
        publication_id = raw_work.get('publication_id')
        title = raw_work.get('title')
        
        if not publication_id or not title:
            logger.warning(f"Skipping work without publication_id or title")
            return None
        
        work_id = self.state_manager.get_or_create_work_id(publication_id)
        
        # Build work entity following schema
        work_entity = {
            'id': work_id,
            'title': title,
            'sources': [{
                'source': 'dtic',
                'id': publication_id
            }],
            'last_updated': datetime.now().isoformat()
        }
        
        # Add optional fields
        if raw_work.get('abstract'):
            work_entity['abstract'] = raw_work['abstract']
        
        if raw_work.get('publication_date'):
            # DTIC dates are in format YYYY-MM or YYYY-MM-DD
            pub_date = raw_work['publication_date']
            # Ensure it's in ISO format (pad to YYYY-MM-DD if needed)
            if len(pub_date) == 7:  # YYYY-MM
                pub_date = f"{pub_date}-01"
            work_entity['publication_date'] = pub_date
        
        if raw_work.get('doi'):
            work_entity['doi'] = raw_work['doi']
        
        if raw_work.get('url'):
            work_entity['url'] = raw_work['url']
        
        if raw_work.get('citations_count') is not None:
            work_entity['citation_count'] = int(raw_work['citations_count'])
        
        # Note: venue not typically in DTIC data, but add if present
        if raw_work.get('venue'):
            work_entity['venue'] = raw_work['venue']
        
        # Build org name to org_id mapping
        org_name_to_id = {}
        for org in raw_work.get('organizations', []):
            if org.get('name') and org.get('org_id'):
                org_guid = self.get_org_guid_from_grid(org['org_id'])
                org_name_to_id[org['name']] = org_guid
        
        # Process authors with affiliations
        authors_list = []
        for author in raw_work.get('authors', []):
            researcher_id = author.get('researcher_id')
            if not researcher_id:
                continue
            
            author_guid = self.get_author_guid_from_researcher_id(researcher_id)
            author_entry = {'author_id': author_guid}
            
            # Try to get org_id from first affiliation
            affiliations = author.get('affiliations', [])
            if affiliations and len(affiliations) > 0:
                first_affiliation = affiliations[0]
                if first_affiliation in org_name_to_id:
                    author_entry['org_id'] = org_name_to_id[first_affiliation]
            
            authors_list.append(author_entry)
        
        if authors_list:
            work_entity['authors'] = authors_list
        
        # Process organizations
        orgs_list = []
        for org in raw_work.get('organizations', []):
            if org.get('org_id'):
                org_guid = self.get_org_guid_from_grid(org['org_id'])
                # Determine role - DTIC orgs are typically affiliations
                org_entry = {
                    'org_id': org_guid,
                    'role': 'affiliation'  # Default for DTIC data
                }
                orgs_list.append(org_entry)
        
        if orgs_list:
            work_entity['orgs'] = orgs_list
        
        # Process topics from keywords
        topics_list = []
        keywords = raw_work.get('keywords', [])
        if isinstance(keywords, list):
            for keyword_group in keywords:
                if isinstance(keyword_group, dict):
                    entities = keyword_group.get('entities', [])
                    for entity in entities:
                        uber_cat_id = entity.get('details', {}).get('uber_cat_id')
                        if uber_cat_id:
                            topic_guid = self.get_topic_guid_from_uber_cat_id(uber_cat_id)
                            # DTIC doesn't provide scores, use 1.0 as default
                            topic_entry = {
                                'topic_id': topic_guid,
                                'score': 1.0
                            }
                            topics_list.append(topic_entry)
        
        if topics_list:
            work_entity['topics'] = topics_list
        
        return work_entity
    
    def process_blob(self, blob_name: str) -> int:
        """
        Process a single blob: read raw work and save cleaned version.
        
        Args:
            blob_name: Name of the blob to process
            
        Returns:
            1 if successful, -1 if failed
        """
        try:
            # Download raw work data
            blob_client = self.source_container_client.get_blob_client(blob_name)
            raw_data = blob_client.download_blob().readall()
            raw_work = json.loads(raw_data)
            
            publication_id = raw_work.get('publication_id', 'unknown')
            logger.debug(f"Processing: {publication_id}")
            
            # Clean the work
            cleaned_work = self.extract_and_clean_work(raw_work)
            if not cleaned_work:
                logger.warning(f"Failed to clean work: {publication_id}")
                return -1
            
            # Use publication_id as filename
            work_blob_name = f"{self.dest_prefix}{publication_id}.json"
            
            # Check if work file already exists (for upsert)
            try:
                existing_blob = self.dest_container_client.get_blob_client(work_blob_name)
                existing_data = existing_blob.download_blob().readall()
                existing_work = json.loads(existing_data)
                
                # Merge/update existing work data
                # Keep the earliest created date, update last_updated
                if 'created_at' in existing_work:
                    cleaned_work['created_at'] = existing_work['created_at']
                else:
                    cleaned_work['created_at'] = cleaned_work['last_updated']
                
                logger.debug(f"Updating existing work: {publication_id}")
            except (ResourceNotFoundError, Exception):
                # New work (or error reading existing), set created_at
                cleaned_work['created_at'] = cleaned_work['last_updated']
                logger.debug(f"Creating new work: {publication_id}")
            
            # Upload cleaned work
            dest_blob_client = self.dest_container_client.get_blob_client(work_blob_name)
            cleaned_json = json.dumps(cleaned_work, indent=2, ensure_ascii=False)
            dest_blob_client.upload_blob(cleaned_json, overwrite=True)
            
            logger.info(f"Saved work: {publication_id}")
            return 1
            
        except Exception as e:
            logger.error(f"Error processing blob {blob_name}: {e}")
            return -1
    
    def process_all(self, max_files: Optional[int] = None) -> Dict[str, int]:
        """
        Process all blobs in the source prefix and extract works.
        
        Args:
            max_files: Maximum number of files to process (None for all)
            
        Returns:
            Dict with processing statistics
        """
        logger.info(f"Starting to extract works from {self.source_container}/{self.source_prefix}")
        
        # List all blobs with source prefix
        blob_list = self.source_container_client.list_blobs(name_starts_with=self.source_prefix)
        
        processed = 0
        failed = 0
        skipped = 0
        
        for blob in blob_list:
            if max_files and processed >= max_files:
                logger.info(f"Reached maximum file limit: {max_files}")
                break
            
            # Skip if already processed
            if self.state_manager.is_processed(blob.name):
                skipped += 1
                continue
            
            result = self.process_blob(blob.name)
            
            if result > 0:
                self.state_manager.mark_processed(blob.name)
                processed += 1
                
                # Log progress every 10 files
                if processed % 10 == 0:
                    logger.info(f"Progress: {processed} works processed")
            else:
                self.state_manager.mark_failed(blob.name)
                failed += 1
        
        stats = {
            'processed': processed,
            'failed': failed,
            'skipped': skipped,
            'total': processed + failed + skipped
        }
        
        logger.info("=" * 60)
        logger.info("Extraction complete!")
        logger.info(f"Processed: {processed}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Skipped: {skipped}")
        logger.info(f"Total: {stats['total']}")
        logger.info("=" * 60)
        
        return stats


def main():
    parser = argparse.ArgumentParser(description='Extract and clean DTIC works')
    parser.add_argument('--max-files', type=int, help='Maximum number of files to process')
    parser.add_argument('--source-container', default='raw', help='Source container name')
    parser.add_argument('--source-prefix', default='dtic/works/', help='Source blob prefix')
    parser.add_argument('--dest-container', default='clean', help='Destination container name')
    parser.add_argument('--dest-prefix', default='dtic/works/', help='Destination blob prefix')
    parser.add_argument('--stats', action='store_true', help='Show statistics and exit')
    
    args = parser.parse_args()
    
    # Show stats only
    if args.stats:
        state_manager = StateManager()
        print("\n=== Extraction Statistics ===")
        print(f"Total files processed: {state_manager.state['total_processed']}")
        print(f"Total works extracted: {len(state_manager.state['works'])}")
        print(f"Failed files: {len(state_manager.state['failed_files'])}")
        print(f"Last updated: {state_manager.state.get('last_updated', 'Never')}")
        return
    
    # Run extraction
    try:
        extractor = DTICWorkExtractor(
            source_container=args.source_container,
            source_prefix=args.source_prefix,
            dest_container=args.dest_container,
            dest_prefix=args.dest_prefix
        )
        
        stats = extractor.process_all(max_files=args.max_files)
        
        # Exit with error code if any failures
        if stats['failed'] > 0:
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
