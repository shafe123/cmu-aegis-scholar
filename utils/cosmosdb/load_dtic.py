"""
Load JSON data from Azure Blob Storage into Cosmos DB.

This script downloads JSON files (regular, compressed, or JSONL format) from Azure Blob Storage 
and inserts them into Cosmos DB. Supports multiple data sources (DTIC, OpenAlex, etc.).
Maintains state of which files have been loaded to avoid duplicates.
"""

import json
import logging
import argparse
import os
import gzip
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from azure.storage.blob import BlobServiceClient
from azure.cosmos import CosmosClient, PartitionKey, exceptions

# Generate timestamped log filename
_log_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
_logs_dir = Path("logs")
_logs_dir.mkdir(exist_ok=True)
_log_filename = _logs_dir / f"{_log_timestamp}_cosmos_loader.log"

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


class LoadStateManager:
    """Manages state of loaded files."""
    
    def __init__(self, state_file: str = "load_state.json"):
        self.state_file = Path(state_file)
        self.state = self._load_state()
    
    def _load_state(self) -> Dict:
        """Load state from file or create new state."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    logger.info(f"Loaded state: {len(state.get('loaded_files', []))} files loaded")
                    return state
            except json.JSONDecodeError:
                logger.warning("Corrupted state file, starting fresh")
        
        return {
            'loaded_files': [],
            'failed_files': [],
            'last_updated': None,
            'total_documents': 0
        }
    
    def save_state(self):
        """Save current state to file."""
        self.state['last_updated'] = datetime.now().isoformat()
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, indent=2)
        logger.debug("Load state saved")
    
    def mark_loaded(self, blob_name: str):
        """Mark a blob as successfully loaded."""
        if blob_name not in self.state['loaded_files']:
            self.state['loaded_files'].append(blob_name)
            self.state['total_documents'] += 1
            # Remove from failed if it was there
            if blob_name in self.state['failed_files']:
                self.state['failed_files'].remove(blob_name)
            self.save_state()
    
    def mark_failed(self, blob_name: str):
        """Mark a blob as failed to load."""
        if blob_name not in self.state['failed_files']:
            self.state['failed_files'].append(blob_name)
            self.save_state()
    
    def is_loaded(self, blob_name: str) -> bool:
        """Check if blob has been loaded."""
        return blob_name in self.state['loaded_files']
    
    def get_loaded_count(self) -> int:
        """Get count of loaded files."""
        return len(self.state['loaded_files'])
    
    def get_failed_count(self) -> int:
        """Get count of failed files."""
        return len(self.state['failed_files'])


class CosmosDBLoader:
    """Loads JSON data from Azure Blob Storage into Cosmos DB."""
    
    def __init__(self,
                 blob_connection_string: str,
                 blob_container_name: str,
                 cosmos_endpoint: str,
                 cosmos_key: str,
                 cosmos_database: str,
                 cosmos_container: str,
                 blob_prefix: str = "",
                 partition_key: str = "id",
                 state_file: str = "load_state.json",
                 batch_size: int = 100):
        """
        Initialize the loader.
        
        Args:
            blob_connection_string: Azure Blob Storage connection string
            blob_container_name: Name of the blob container
            cosmos_endpoint: Cosmos DB endpoint URL
            cosmos_key: Cosmos DB master key
            cosmos_database: Cosmos DB database name
            cosmos_container: Cosmos DB container name
            blob_prefix: Prefix for blob names in container (e.g., 'dtic/works/', 'openalex/works/')
            partition_key: Partition key path for Cosmos DB (default: 'id')
            state_file: State file path
            batch_size: Number of documents to process in one batch
        """
        self.blob_prefix = blob_prefix
        self.partition_key = partition_key
        self.batch_size = batch_size
        self.state_manager = LoadStateManager(state_file)
        
        # Initialize Azure Blob Storage client
        try:
            self.blob_service_client = BlobServiceClient.from_connection_string(blob_connection_string)
            self.container_client = self.blob_service_client.get_container_client(blob_container_name)
            logger.info(f"Connected to Azure Blob Storage container: {blob_container_name}")
        except Exception as e:
            logger.error(f"Failed to connect to Azure Blob Storage: {e}")
            raise
        
        # Initialize Cosmos DB client
        try:
            self.cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key)
            self.database = self.cosmos_client.get_database_client(cosmos_database)
            
            # Create database if it doesn't exist
            try:
                self.cosmos_client.create_database(cosmos_database)
                logger.info(f"Created database: {cosmos_database}")
            except exceptions.CosmosResourceExistsError:
                logger.info(f"Using existing database: {cosmos_database}")
            
            # Create container if it doesn't exist
            try:
                # Try creating without throughput first (works for serverless accounts)
                partition_key_path = f"/{partition_key}" if not partition_key.startswith('/') else partition_key
                self.database.create_container(
                    id=cosmos_container,
                    partition_key=PartitionKey(path=partition_key_path)
                )
                logger.info(f"Created container: {cosmos_container} with partition key: {partition_key_path}")
            except exceptions.CosmosResourceExistsError:
                logger.info(f"Using existing container: {cosmos_container}")
            except exceptions.CosmosHttpResponseError as e:
                # If container doesn't exist and we need throughput, handle it
                if "BadRequest" in str(e) and "serverless" in str(e).lower():
                    logger.error("Cannot set throughput on serverless account")
                    raise
                else:
                    raise
            
            self.container = self.database.get_container_client(cosmos_container)
            logger.info(f"Connected to Cosmos DB container: {cosmos_container}")
            
        except Exception as e:
            logger.error(f"Failed to connect to Cosmos DB: {e}")
            raise
    
    def list_blobs(self) -> List[str]:
        """
        List all JSON/compressed blobs with the specified prefix.
        
        Returns:
            List of blob names
        """
        try:
            blob_list = []
            list_kwargs = {'name_starts_with': self.blob_prefix} if self.blob_prefix else {}
            
            for blob in self.container_client.list_blobs(**list_kwargs):
                # Accept .json, .json.gz, .jsonl, .jsonl.gz, .gz files
                if any(blob.name.endswith(ext) for ext in ['.json', '.json.gz', '.jsonl', '.jsonl.gz', '.gz']):
                    blob_list.append(blob.name)
            
            logger.info(f"Found {len(blob_list)} JSON/compressed blobs in Azure Blob Storage")
            return blob_list
        
        except Exception as e:
            logger.error(f"Failed to list blobs: {e}")
            return []
    
    @staticmethod
    def clean_id(id_value: any) -> str:
        """
        Clean ID value by removing URL prefixes.
        
        Examples:
            "https://openalex.org/W2741809807" -> "W2741809807"
            "https://doi.org/10.7717/peerj.4375" -> "10.7717/peerj.4375"
            "pub.1000004508" -> "pub.1000004508"
        
        Args:
            id_value: The ID value (can be string or any type)
            
        Returns:
            Cleaned ID string
        """
        if not id_value:
            return ""
        
        id_str = str(id_value)
        
        # If it looks like a URL, extract the last part
        if id_str.startswith(('http://', 'https://')):
            # Remove trailing slashes
            id_str = id_str.rstrip('/')
            # Get everything after the last slash
            return id_str.split('/')[-1]
        
        return id_str
    
    def download_blob(self, blob_name: str) -> Optional[List[Dict]]:
        """
        Download and parse a JSON blob (supports regular JSON, JSONL, and compressed formats).
        
        Args:
            blob_name: Name of the blob to download
            
        Returns:
            List of parsed JSON documents or None if failed
        """
        try:
            blob_client = self.container_client.get_blob_client(blob_name)
            blob_data = blob_client.download_blob()
            raw_content = blob_data.readall()
            
            # Decompress if gzipped
            if blob_name.endswith('.gz'):
                raw_content = gzip.decompress(raw_content)
            
            # Decode to string
            text_content = raw_content.decode('utf-8')
            
            # Parse based on format
            documents = []
            
            # Check if it's JSONL format (multiple lines, each is a JSON object)
            if blob_name.endswith('.jsonl') or blob_name.endswith('.jsonl.gz'):
                for line_num, line in enumerate(text_content.strip().split('\n'), 1):
                    if line.strip():
                        try:
                            doc = json.loads(line)
                            documents.append(doc)
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse line {line_num} in {blob_name}: {e}")
                            continue
            else:
                # Try to parse as single JSON document first
                try:
                    document = json.loads(text_content)
                    # If it's a list, use it directly; otherwise wrap in list
                    documents = document if isinstance(document, list) else [document]
                except json.JSONDecodeError:
                    # If that fails, try line-by-line (JSONL without .jsonl extension)
                    for line_num, line in enumerate(text_content.strip().split('\n'), 1):
                        if line.strip():
                            try:
                                doc = json.loads(line)
                                documents.append(doc)
                            except json.JSONDecodeError:
                                logger.warning(f"Failed to parse line {line_num} in {blob_name}")
                                continue
            
            if not documents:
                logger.warning(f"No valid JSON documents found in {blob_name}")
                return None
            
            logger.debug(f"Parsed {len(documents)} document(s) from {blob_name}")
            return documents
        
        except Exception as e:
            logger.error(f"Failed to download blob {blob_name}: {e}")
            return None
    
    def insert_document(self, document: Dict) -> bool:
        """
        Insert a document into Cosmos DB.
        
        Args:
            document: Document to insert
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure the document has an id field (required by Cosmos DB)
            if 'id' not in document:
                # Try common ID fields from different data sources
                raw_id = document.get('publication_id') or \
                         document.get('work_id') or \
                         document.get('doi') or \
                         str(abs(hash(str(document))))
                document['id'] = self.clean_id(raw_id)
            else:
                # Clean existing ID (remove URL prefix if present)
                document['id'] = self.clean_id(document['id'])
            
            # Upsert the document (insert or update if exists)
            self.container.upsert_item(document)
            return True
        
        except exceptions.CosmosHttpResponseError as e:
            logger.error(f"Failed to insert document {document.get('id', 'unknown')}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error inserting document: {e}")
            return False
    
    def load_blob_to_cosmos(self, blob_name: str) -> tuple[bool, int]:
        """
        Download a blob and insert all documents into Cosmos DB.
        
        Args:
            blob_name: Name of the blob to load
            
        Returns:
            Tuple of (success, document_count)
        """
        # Download blob
        documents = self.download_blob(blob_name)
        if documents is None:
            return False, 0
        
        # Insert all documents into Cosmos DB
        success_count = 0
        for doc in documents:
            if self.insert_document(doc):
                success_count += 1
        
        if success_count == len(documents):
            logger.info(f"[OK] Loaded: {blob_name} ({success_count} document(s))")
            return True, success_count
        elif success_count > 0:
            logger.warning(f"[PARTIAL] Loaded {success_count}/{len(documents)} documents from: {blob_name}")
            return True, success_count
        else:
            logger.error(f"[FAIL] Failed to insert any documents from: {blob_name}")
            return False, 0
    
    def load_all_blobs(self, force_reload: bool = False) -> tuple[int, int, int]:
        """
        Load all blobs from Azure Blob Storage into Cosmos DB.
        
        Args:
            force_reload: If True, reload even already loaded blobs
            
        Returns:
            Tuple of (files_loaded, files_failed, total_documents)
        """
        blob_names = self.list_blobs()
        
        if not blob_names:
            logger.warning("No blobs found to load")
            return 0, 0, 0
        
        files_loaded = 0
        files_failed = 0
        total_documents = 0
        total = len(blob_names)
        
        for idx, blob_name in enumerate(blob_names, 1):
            # Skip if already loaded (unless force_reload is True)
            if not force_reload and self.state_manager.is_loaded(blob_name):
                logger.debug(f"[{idx}/{total}] Skipping already loaded: {blob_name}")
                continue
            
            logger.info(f"[{idx}/{total}] Processing: {blob_name}")
            
            # Try to load
            success, doc_count = self.load_blob_to_cosmos(blob_name)
            if success:
                self.state_manager.mark_loaded(blob_name)
                files_loaded += 1
                total_documents += doc_count
            else:
                self.state_manager.mark_failed(blob_name)
                files_failed += 1
        
        return files_loaded, files_failed, total_documents
    
    def get_stats(self) -> Dict:
        """Get statistics about loaded documents."""
        return {
            'total_loaded': self.state_manager.get_loaded_count(),
            'total_failed': self.state_manager.get_failed_count(),
            'last_updated': self.state_manager.state.get('last_updated', 'Never')
        }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Load JSON data from Azure Blob Storage into Cosmos DB (supports regular, compressed, and JSONL formats)'
    )
    
    # Azure Blob Storage arguments
    parser.add_argument(
        '--blob-connection-string',
        help='Azure Blob Storage connection string',
        default=os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
    )
    parser.add_argument(
        '--blob-container',
        help='Azure Blob Storage container name',
        default='dtic-publications'
    )
    parser.add_argument(
        '--blob-prefix',
        help='Blob prefix to filter files (e.g., "dtic/works/", "openalex/works/")',
        default=''
    )
    
    # Cosmos DB arguments
    parser.add_argument(
        '--cosmos-endpoint',
        help='Cosmos DB endpoint URL',
        default=os.environ.get('COSMOS_ENDPOINT')
    )
    parser.add_argument(
        '--cosmos-key',
        help='Cosmos DB master key',
        default=os.environ.get('COSMOS_KEY')
    )
    parser.add_argument(
        '--cosmos-database',
        help='Cosmos DB database name',
        default='aegis-scholar'
    )
    parser.add_argument(
        '--cosmos-container',
        help='Cosmos DB container name',
        default='publications'
    )
    parser.add_argument(
        '--partition-key',
        help='Partition key path for Cosmos DB (default: "id")',
        default='id'
    )
    
    # Processing arguments
    parser.add_argument(
        '--state-file',
        help='State file to track loaded files',
        default='load_state.json'
    )
    parser.add_argument(
        '--batch-size',
        help='Number of documents to process in one batch',
        type=int,
        default=100
    )
    parser.add_argument(
        '--force-reload',
        help='Reload even already loaded blobs',
        action='store_true'
    )
    
    args = parser.parse_args()
    
    # Validate required arguments
    if not args.blob_connection_string:
        logger.error("Azure Blob Storage connection string is required. "
                    "Set AZURE_STORAGE_CONNECTION_STRING or use --blob-connection-string")
        return 1
    
    if not args.cosmos_endpoint:
        logger.error("Cosmos DB endpoint is required. "
                    "Set COSMOS_ENDPOINT or use --cosmos-endpoint")
        return 1
    
    if not args.cosmos_key:
        logger.error("Cosmos DB key is required. "
                    "Set COSMOS_KEY or use --cosmos-key")
        return 1
    
    try:
        # Initialize loader
        loader = CosmosDBLoader(
            blob_connection_string=args.blob_connection_string,
            blob_container_name=args.blob_container,
            cosmos_endpoint=args.cosmos_endpoint,
            cosmos_key=args.cosmos_key,
            cosmos_database=args.cosmos_database,
            cosmos_container=args.cosmos_container,
            blob_prefix=args.blob_prefix,
            partition_key=args.partition_key,
            state_file=args.state_file,
            batch_size=args.batch_size
        )
        
        logger.info("="*70)
        logger.info("Starting Cosmos DB load process")
        logger.info("="*70)
        
        # Load all blobs
        files_loaded, files_failed, total_docs = loader.load_all_blobs(force_reload=args.force_reload)
        
        # Print summary
        stats = loader.get_stats()
        logger.info("="*70)
        logger.info("Load Summary:")
        logger.info(f"  New files loaded: {files_loaded}")
        logger.info(f"  Total documents inserted: {total_docs}")
        logger.info(f"  Files failed: {files_failed}")
        logger.info(f"  Total files loaded (all time): {stats['total_loaded']}")
        logger.info(f"  Total files failed (all time): {stats['total_failed']}")
        logger.info(f"  Last updated: {stats['last_updated']}")
        logger.info("="*70)
        
        return 0 if files_failed == 0 else 1
        
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    exit(main())
