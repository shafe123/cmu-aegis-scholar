"""
Script to download all DTIC objects from Azure Blob Storage clean container.

Downloads all blobs with the 'dtic/' prefix from the 'clean' container to the 
local 'data/dtic/' folder, maintaining the same directory structure.

Usage:
    # Using environment variable for connection string:
    python download_dtic_from_blob.py
    
    # Using SAS token:
    python download_dtic_from_blob.py --sas-token "?sv=2024..."
    
    # Using connection string directly:
    python download_dtic_from_blob.py --connection-string "DefaultEndpointsProtocol=https;..."
    
    # Dry run to see what would be downloaded:
    python download_dtic_from_blob.py --dry-run
    
    # Download to a different local directory:
    python download_dtic_from_blob.py --output-dir "path/to/directory"
    
    # Limit number of files:
    python download_dtic_from_blob.py --max-files 100
"""

import os
import argparse
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime
from azure.storage.blob import BlobServiceClient
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Quiet Azure SDK loggers
logging.getLogger('azure').setLevel(logging.WARNING)
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)

# --- CONFIGURATION ---
ACCOUNT_URL = "https://aegisscholardata.blob.core.windows.net"
SOURCE_CONTAINER = "clean"
SOURCE_PREFIX = "dtic/"


class BlobDownloader:
    """Handles downloading blobs from Azure Storage to local filesystem."""
    
    def __init__(self, 
                 connection_string: Optional[str] = None,
                 sas_token: Optional[str] = None,
                 container_name: str = SOURCE_CONTAINER,
                 prefix: str = SOURCE_PREFIX):
        """
        Initialize the blob downloader.
        
        Args:
            connection_string: Azure Storage connection string
            sas_token: Azure Storage SAS token
            container_name: Name of the blob container
            prefix: Prefix of blobs to download
        """
        self.container_name = container_name
        self.prefix = prefix
        
        # Initialize blob service client
        if connection_string:
            self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
            logger.info("Connected using connection string")
        elif sas_token:
            account_url_with_sas = f"{ACCOUNT_URL}{sas_token}"
            self.blob_service_client = BlobServiceClient(account_url=account_url_with_sas)
            logger.info("Connected using SAS token")
        else:
            raise ValueError("Either connection_string or sas_token must be provided")
        
        self.container_client = self.blob_service_client.get_container_client(container_name)
        logger.info(f"Connected to container: {container_name}")
    
    def list_blobs(self, max_files: Optional[int] = None):
        """
        List all blobs with the specified prefix.
        
        Args:
            max_files: Maximum number of files to list (None for all)
            
        Returns:
            List of blob names
        """
        logger.info(f"Listing blobs with prefix: {self.prefix}")
        blobs = []
        
        try:
            blob_list = self.container_client.list_blobs(name_starts_with=self.prefix)
            for i, blob in enumerate(blob_list):
                if max_files and i >= max_files:
                    break
                blobs.append(blob.name)
            
            logger.info(f"Found {len(blobs)} blobs to download")
            return blobs
        except Exception as e:
            logger.error(f"Error listing blobs: {e}")
            raise
    
    def download_blob(self, blob_name: str, output_dir: Path, dry_run: bool = False) -> tuple[str, bool]:
        """
        Download a single blob to local filesystem.
        
        Args:
            blob_name: Name of the blob to download
            output_dir: Local directory to save the file
            dry_run: If True, only simulate the download
            
        Returns:
            Tuple of (blob_name, success)
        """
        try:
            # Calculate local file path
            # Remove the prefix from blob name to get relative path
            relative_path = blob_name[len(self.prefix):] if blob_name.startswith(self.prefix) else blob_name
            local_file = output_dir / relative_path
            
            if dry_run:
                logger.info(f"[DRY RUN] Would download: {blob_name} -> {local_file}")
                return blob_name, True
            
            # Create parent directories if they don't exist
            local_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Skip if file already exists (optional - can add --force flag later)
            if local_file.exists():
                logger.debug(f"Skipping existing file: {local_file}")
                return blob_name, True
            
            # Download the blob
            blob_client = self.container_client.get_blob_client(blob_name)
            
            with open(local_file, 'wb') as f:
                download_stream = blob_client.download_blob()
                f.write(download_stream.readall())
            
            logger.info(f"Downloaded: {blob_name} -> {local_file}")
            return blob_name, True
            
        except Exception as e:
            logger.error(f"Error downloading {blob_name}: {e}")
            return blob_name, False
    
    def download_all(self, 
                     output_dir: Path, 
                     dry_run: bool = False, 
                     max_files: Optional[int] = None,
                     max_workers: int = 5) -> dict:
        """
        Download all blobs with the specified prefix.
        
        Args:
            output_dir: Local directory to save files
            dry_run: If True, only simulate downloads
            max_files: Maximum number of files to download
            max_workers: Number of parallel download threads
            
        Returns:
            Dictionary with download statistics
        """
        start_time = datetime.now()
        
        # List all blobs to download
        blob_names = self.list_blobs(max_files=max_files)
        
        if not blob_names:
            logger.warning("No blobs found to download")
            return {
                'total': 0,
                'success': 0,
                'failed': 0,
                'duration': 0
            }
        
        # Download blobs in parallel
        success_count = 0
        failed_count = 0
        failed_blobs = []
        
        if dry_run:
            logger.info(f"[DRY RUN] Would download {len(blob_names)} blobs to {output_dir}")
            for blob_name in blob_names:
                self.download_blob(blob_name, output_dir, dry_run=True)
            success_count = len(blob_names)
        else:
            logger.info(f"Starting download of {len(blob_names)} blobs using {max_workers} workers")
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all download tasks
                future_to_blob = {
                    executor.submit(self.download_blob, blob_name, output_dir): blob_name
                    for blob_name in blob_names
                }
                
                # Process completed downloads
                for future in as_completed(future_to_blob):
                    blob_name, success = future.result()
                    if success:
                        success_count += 1
                    else:
                        failed_count += 1
                        failed_blobs.append(blob_name)
                    
                    # Print progress
                    total_processed = success_count + failed_count
                    if total_processed % 10 == 0 or total_processed == len(blob_names):
                        logger.info(f"Progress: {total_processed}/{len(blob_names)} "
                                  f"(Success: {success_count}, Failed: {failed_count})")
        
        duration = (datetime.now() - start_time).total_seconds()
        
        # Print summary
        logger.info("=" * 60)
        logger.info("DOWNLOAD SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total blobs: {len(blob_names)}")
        logger.info(f"Successfully downloaded: {success_count}")
        logger.info(f"Failed: {failed_count}")
        logger.info(f"Duration: {duration:.2f} seconds")
        
        if failed_blobs:
            logger.warning(f"Failed to download {len(failed_blobs)} blobs:")
            for blob in failed_blobs:
                logger.warning(f"  - {blob}")
        
        return {
            'total': len(blob_names),
            'success': success_count,
            'failed': failed_count,
            'failed_blobs': failed_blobs,
            'duration': duration
        }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Download DTIC data from Azure Blob Storage clean container',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Authentication options
    auth_group = parser.add_mutually_exclusive_group()
    auth_group.add_argument(
        '--connection-string',
        help='Azure Storage connection string (or set AZURE_STORAGE_CONNECTION_STRING env var)'
    )
    auth_group.add_argument(
        '--sas-token',
        help='Azure Storage SAS token (including the ? prefix)'
    )
    
    # Download options
    parser.add_argument(
        '--output-dir',
        type=str,
        default='data/dtic',
        help='Local directory to save downloaded files (default: data/dtic)'
    )
    parser.add_argument(
        '--container',
        default=SOURCE_CONTAINER,
        help=f'Blob container name (default: {SOURCE_CONTAINER})'
    )
    parser.add_argument(
        '--prefix',
        default=SOURCE_PREFIX,
        help=f'Blob prefix to download (default: {SOURCE_PREFIX})'
    )
    parser.add_argument(
        '--max-files',
        type=int,
        help='Maximum number of files to download (default: all)'
    )
    parser.add_argument(
        '--max-workers',
        type=int,
        default=5,
        help='Number of parallel download threads (default: 5)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview what would be downloaded without actually downloading'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Get connection credentials
    connection_string = args.connection_string or os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
    sas_token = args.sas_token
    
    if not connection_string and not sas_token:
        logger.error("No authentication provided!")
        logger.error("Either set AZURE_STORAGE_CONNECTION_STRING environment variable,")
        logger.error("or provide --connection-string or --sas-token argument")
        return 1
    
    # Create output directory
    output_dir = Path(args.output_dir)
    
    try:
        # Initialize downloader
        downloader = BlobDownloader(
            connection_string=connection_string,
            sas_token=sas_token,
            container_name=args.container,
            prefix=args.prefix
        )
        
        # Download all blobs
        results = downloader.download_all(
            output_dir=output_dir,
            dry_run=args.dry_run,
            max_files=args.max_files,
            max_workers=args.max_workers
        )
        
        # Return success/failure based on results
        if results['failed'] > 0:
            return 1
        return 0
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    exit(main())
