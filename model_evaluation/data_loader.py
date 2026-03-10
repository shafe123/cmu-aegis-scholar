"""
Data Loader for Model Evaluation

Fetches paper data from Azure Blob Storage for specified authors.
Handles DTIC works data stored in blob storage.
"""

import json
import gzip
import logging
from pathlib import Path
from typing import List, Dict, Set, Optional
from azure.storage.blob import BlobServiceClient, ContainerClient
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AuthorDataLoader:
    """
    Loads paper data for specified authors from Azure Blob Storage.
    """
    
    def __init__(
        self,
        connection_string: str,
        container_name: str = "dtic-publications",
        blob_prefix: str = "dtic/works/",
        cache_dir: str = "cache"
    ):
        """
        Initialize the data loader.
        
        Args:
            connection_string: Azure Storage connection string
            container_name: Name of the blob container
            blob_prefix: Prefix for blob names in container
            cache_dir: Local directory to cache downloaded data
        """
        self.connection_string = connection_string
        self.container_name = container_name
        self.blob_prefix = blob_prefix
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Initialize blob service client
        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        self.container_client = self.blob_service_client.get_container_client(container_name)
        
        logger.info(f"Initialized AuthorDataLoader with container: {container_name}")
    
    def fetch_papers_for_authors(
        self,
        author_ids: List[str],
        max_blobs: Optional[int] = None,
        use_cache: bool = True
    ) -> Dict[str, List[Dict]]:
        """
        Fetch papers for the specified authors from blob storage.
        
        Args:
            author_ids: List of DTIC author IDs (researcher_id format)
            max_blobs: Maximum number of blob files to process (None for all)
            use_cache: Whether to use locally cached blob data
            
        Returns:
            Dictionary mapping author_id to list of their papers
        """
        # Convert to set for faster lookup
        target_author_ids = set(author_ids)
        logger.info(f"Searching for papers by {len(target_author_ids)} authors")
        
        # Dictionary to store papers by author
        author_papers = defaultdict(list)
        
        # List blobs to process
        logger.info(f"Listing blobs with prefix: {self.blob_prefix}")
        blob_list = list(self.container_client.list_blobs(name_starts_with=self.blob_prefix))
        
        if max_blobs:
            blob_list = blob_list[:max_blobs]
        
        logger.info(f"Processing {len(blob_list)} blob files...")
        
        for idx, blob in enumerate(blob_list, 1):
            if idx % 100 == 0:
                logger.info(f"Processed {idx}/{len(blob_list)} blobs...")
            
            try:
                paper = self._process_blob(blob.name, use_cache)
                
                if paper:
                    # Extract author IDs from this paper
                    paper_author_ids = self._extract_author_ids(paper)
                    
                    # Check if any of our target authors wrote this paper
                    for author_id in target_author_ids:
                        if author_id in paper_author_ids:
                            author_papers[author_id].append(paper)
                
            except Exception as e:
                logger.error(f"Error processing blob {blob.name}: {e}")
                continue
        
        # Log results
        logger.info("="*70)
        logger.info("Paper collection complete:")
        for author_id, papers in author_papers.items():
            logger.info(f"  {author_id}: {len(papers)} papers")
        logger.info("="*70)
        
        return dict(author_papers)
    
    def _process_blob(self, blob_name: str, use_cache: bool = True) -> Optional[Dict]:
        """
        Download and parse a blob file.
        
        Args:
            blob_name: Name of the blob to process
            use_cache: Whether to use cached data
            
        Returns:
            Paper dictionary or None if invalid
        """
        # Check cache first
        cache_file = self.cache_dir / blob_name.replace('/', '_')
        
        if use_cache and cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load cache for {blob_name}: {e}")
        
        # Download from blob storage
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name,
            blob=blob_name
        )
        
        try:
            blob_data = blob_client.download_blob().readall()
        except Exception as e:
            logger.error(f"Failed to download {blob_name}: {e}")
            return None
        
        # Handle gzipped data
        if blob_name.endswith('.gz'):
            try:
                blob_data = gzip.decompress(blob_data)
            except Exception as e:
                logger.error(f"Failed to decompress {blob_name}: {e}")
                return None
        
        # Parse JSON (DTIC files are single JSON objects, not JSON lines)
        try:
            paper = json.loads(blob_data.decode('utf-8'))
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON for {blob_name}: {e}")
            return None
        
        # Cache the parsed data
        if use_cache:
            try:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(paper, f)
            except Exception as e:
                logger.warning(f"Failed to cache {blob_name}: {e}")
        
        return paper
    
    def _extract_author_ids(self, paper: Dict) -> Set[str]:
        """
        Extract all author IDs from a DTIC paper.
        
        Args:
            paper: Paper dictionary
            
        Returns:
            Set of DTIC author IDs (researcher_id format)
        """
        author_ids = set()
        
        # DTIC format: authors array with researcher_id field
        if "authors" in paper:
            for author in paper["authors"]:
                if isinstance(author, dict):
                    researcher_id = author.get("researcher_id")
                    if researcher_id:
                        author_ids.add(researcher_id)
        
        return author_ids
    
    def save_author_papers(self, author_papers: Dict[str, List[Dict]], output_file: str):
        """
        Save author papers to a JSON file.
        
        Args:
            author_papers: Dictionary mapping author_id to list of papers
            output_file: Path to output file
        """
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(author_papers, f, indent=2)
        
        logger.info(f"Saved author papers to {output_file}")
    
    def load_author_papers(self, input_file: str) -> Dict[str, List[Dict]]:
        """
        Load author papers from a JSON file.
        
        Args:
            input_file: Path to input file
            
        Returns:
            Dictionary mapping author_id to list of papers
        """
        with open(input_file, 'r', encoding='utf-8') as f:
            return json.load(f)
