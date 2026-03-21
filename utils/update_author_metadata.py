"""
Utility script to update author names and citation counts in the vector database.

This script:
1. Reads all author data from compressed JSONL files to build a lookup table
2. Connects directly to Milvus and queries all entries
3. Updates entries that have incorrect author names or missing citation counts
4. Preserves existing embeddings - only updates metadata fields
"""
import gzip
import json
import logging
import argparse
from pathlib import Path
from collections import defaultdict

try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False

from pymilvus import connections, Collection, utility, CollectionSchema, FieldSchema, DataType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AuthorMetadataUpdater:
    """Updates author metadata in the vector database."""
    
    def __init__(
        self,
        data_dir: str,
        milvus_host: str,
        milvus_port: int,
        collection_name: str,
        dry_run: bool = False,
        batch_size: int = 100
    ):
        """
        Initialize the updater.
        
        Args:
            data_dir: Directory containing compressed author files
            milvus_host: Milvus server hostname
            milvus_port: Milvus server port
            collection_name: Name of the collection to update
            dry_run: If True, only log what would be updated without making changes
            batch_size: Number of entries to process in each batch
        """
        self.data_dir = Path(data_dir)
        self.milvus_host = milvus_host
        self.milvus_port = milvus_port
        self.collection_name = collection_name
        self.dry_run = dry_run
        self.batch_size = batch_size
        self.stats = defaultdict(int)
        self.collection = None
    
    def _parse_json(self, line: bytes) -> dict:
        """Parse a JSON line using orjson if available, otherwise standard json."""
        if HAS_ORJSON:
            return orjson.loads(line)
        else:
            return json.loads(line.decode('utf-8'))
    
    def build_author_lookup(self) -> dict[str, dict]:
        """
        Build a lookup table of author_id -> {name, citation_count}.
        
        Returns:
            Dictionary mapping author_id to author metadata
        """
        logger.info("Building author lookup table from compressed files...")
        lookup = {}
        
        # Find all author files
        pattern = "dtic_authors_*.jsonl.gz"
        author_files = sorted(self.data_dir.glob(pattern))
        
        if not author_files:
            logger.error(f"No author files found matching pattern '{pattern}' in {self.data_dir}")
            return lookup
        
        logger.info(f"Found {len(author_files)} author files")
        
        total_authors = 0
        for file_path in author_files:
            logger.info(f"Reading {file_path.name}...")
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
                            logger.debug(f"Error parsing author record: {e}")
                            continue
            except Exception as e:
                logger.error(f"Error reading file {file_path}: {e}")
                continue
        
        logger.info(f"Built lookup table with {total_authors} authors ({len(lookup)} unique)")
        return lookup
    
    def connect_to_milvus(self):
        """Connect to Milvus and load the collection."""
        logger.info(f"Connecting to Milvus at {self.milvus_host}:{self.milvus_port}...")
        
        try:
            connections.connect(
                alias="default",
                host=self.milvus_host,
                port=self.milvus_port
            )
            logger.info("Connected to Milvus successfully")
            
            # Check if collection exists
            if not utility.has_collection(self.collection_name):
                raise ValueError(f"Collection '{self.collection_name}' does not exist")
            
            # Load the collection
            self.collection = Collection(self.collection_name)
            self.collection.load()
            
            num_entities = self.collection.num_entities
            logger.info(f"Loaded collection '{self.collection_name}' with {num_entities} entities")
            
            # Check if schema needs migration
            self._ensure_schema_updated()
            
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            raise
    
    def _ensure_schema_updated(self):
        """Ensure the collection schema has the citation_count field."""
        try:
            schema = self.collection.schema
            field_names = [field.name for field in schema.fields]
            
            logger.info(f"Current schema fields: {field_names}")
            
            if "citation_count" not in field_names:
                logger.warning("citation_count field not found in schema - migration required")
                
                if self.dry_run:
                    logger.warning("[DRY RUN] Migration skipped - will simulate updates without citation_count field")
                    logger.warning("[DRY RUN] Run without --dry-run to perform actual schema migration")
                    return
                
                logger.info("Migrating collection schema to add citation_count field...")
                self._migrate_schema()
                logger.info("Migration completed - reloading collection...")
                
                # Reload collection to ensure we have the updated schema
                self.collection = Collection(self.collection_name)
                self.collection.load()
                
                # Verify the field was added
                new_schema = self.collection.schema
                new_field_names = [field.name for field in new_schema.fields]
                if "citation_count" in new_field_names:
                    logger.info("✓ Schema migration successful - citation_count field added")
                else:
                    raise RuntimeError("Schema migration failed - citation_count field still missing")
            else:
                logger.info("✓ Schema is up to date (citation_count field exists)")
        except Exception as e:
            logger.error(f"Error during schema validation: {e}", exc_info=True)
            raise
    
    def _migrate_schema(self):
        """
        Migrate the collection schema to add citation_count field.
        This creates a new collection, copies data, and swaps them.
        """
        temp_collection_name = f"{self.collection_name}_temp"
        
        try:
            # Clean up any existing temp collection from failed migrations
            if utility.has_collection(temp_collection_name):
                logger.warning(f"Found existing temp collection '{temp_collection_name}' - cleaning up...")
                utility.drop_collection(temp_collection_name)
            
            # Step 1: Create new collection with updated schema
            logger.info(f"Creating temporary collection '{temp_collection_name}' with updated schema...")
            
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=512),
                FieldSchema(name="author_id", dtype=DataType.VARCHAR, max_length=512),
                FieldSchema(name="author_name", dtype=DataType.VARCHAR, max_length=1024),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=384),
                FieldSchema(name="num_abstracts", dtype=DataType.INT64),
                FieldSchema(name="citation_count", dtype=DataType.INT64, default_value=0),
            ]
            
            schema = CollectionSchema(
                fields=fields,
                description="AEGIS Scholar author embeddings with citation counts"
            )
            
            temp_collection = Collection(name=temp_collection_name, schema=schema)
            logger.info(f"✓ Created temp collection with schema: {[f.name for f in fields]}")
            
            # Step 2: Create same index on embedding field
            logger.info("Creating index on new collection...")
            index_params = {
                "metric_type": "L2",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 1024}
            }
            temp_collection.create_index(field_name="embedding", index_params=index_params)
            logger.info("✓ Index created")
            
            # Step 3: Query all data from old collection
            logger.info("Querying data from old collection...")
            old_data = self.collection.query(
                expr="id != ''",
                output_fields=["id", "author_id", "author_name", "embedding", "num_abstracts"],
                limit=16384
            )
            
            logger.info(f"Found {len(old_data)} entries to migrate")
            
            if old_data:
                # Prepare data with citation_count = 0 as default
                logger.info("Inserting data into new collection...")
                entity_data = [
                    [entry['id'] for entry in old_data],
                    [entry['author_id'] for entry in old_data],
                    [entry['author_name'] for entry in old_data],
                    [entry['embedding'] for entry in old_data],
                    [entry['num_abstracts'] for entry in old_data],
                    [0] * len(old_data),  # citation_count defaults to 0
                ]
                
                temp_collection.insert(entity_data)
                temp_collection.flush()
                logger.info(f"✓ Copied {len(old_data)} entries to new collection")
            else:
                logger.warning("No data to migrate - old collection is empty")
            
            # Step 4: Load new collection
            logger.info("Loading new collection...")
            temp_collection.load()
            logger.info(f"✓ New collection loaded with {temp_collection.num_entities} entities")
            
            # Step 5: Drop old collection and rename new one
            logger.info(f"Dropping old collection '{self.collection_name}'...")
            self.collection.release()
            utility.drop_collection(self.collection_name)
            logger.info("✓ Old collection dropped")
            
            logger.info(f"Renaming '{temp_collection_name}' to '{self.collection_name}'...")
            utility.rename_collection(temp_collection_name, self.collection_name)
            logger.info("✓ Collection renamed")
            
            logger.info("Schema migration completed successfully!")
            
        except Exception as e:
            logger.error(f"Schema migration failed: {e}", exc_info=True)
            # Clean up temp collection if it exists
            if utility.has_collection(temp_collection_name):
                logger.info("Cleaning up temporary collection...")
                try:
                    utility.drop_collection(temp_collection_name)
                except Exception:
                    pass
            raise
    
    def get_all_vector_entries(self) -> list[dict]:
        """
        Fetch all entries from the vector database.
        
        Returns:
            List of all vector database entries with metadata
        """
        logger.info(f"Querying all entries from collection '{self.collection_name}'...")
        
        try:
            # Check if citation_count field exists in current schema
            schema = self.collection.schema
            field_names = [field.name for field in schema.fields]
            has_citation_count = "citation_count" in field_names
            
            # Build output fields list based on what exists
            output_fields = ["id", "author_id", "author_name", "embedding", "num_abstracts"]
            if has_citation_count:
                output_fields.append("citation_count")
            
            logger.info(f"Querying fields: {output_fields}")
            
            # Query all entities
            results = self.collection.query(
                expr="id != ''",  # Match all non-empty IDs
                output_fields=output_fields,
                limit=16384  # Milvus default max, we'll handle pagination if needed
            )
            
            # Add citation_count as 0 if it doesn't exist in schema
            if not has_citation_count:
                logger.info("Adding citation_count=0 to all entries (field not in schema)")
                for result in results:
                    result["citation_count"] = 0
            
            logger.info(f"Retrieved {len(results)} entries")
            return results
            
        except Exception as e:
            logger.error(f"Error querying vector entries: {e}")
            raise
    
    def update_entries_batch(self, entries_to_update: list[dict]) -> int:
        """
        Update a batch of entries with correct metadata.
        
        Args:
            entries_to_update: List of entry dicts with updated metadata
            
        Returns:
            Number of successfully updated entries
        """
        if not entries_to_update:
            return 0
        
        if self.dry_run:
            for entry in entries_to_update:
                logger.info(
                    f"[DRY RUN] Would update {entry['author_id']}: "
                    f"name='{entry['author_name']}', citations={entry['citation_count']}"
                )
            return len(entries_to_update)
        
        try:
            # Check if citation_count field exists in schema
            schema = self.collection.schema
            field_names = [field.name for field in schema.fields]
            has_citation_count = "citation_count" in field_names
            
            if not has_citation_count:
                logger.warning(
                    "citation_count field not in schema - will only update author_name. "
                    "Run the script again to perform migration first."
                )
            
            # Prepare data in the format Milvus expects for upsert
            if has_citation_count:
                entity_data = [
                    [entry['id'] for entry in entries_to_update],              # id
                    [entry['author_id'] for entry in entries_to_update],       # author_id
                    [entry['author_name'] for entry in entries_to_update],     # author_name
                    [entry['embedding'] for entry in entries_to_update],       # embedding (preserved)
                    [entry['num_abstracts'] for entry in entries_to_update],   # num_abstracts
                    [entry['citation_count'] for entry in entries_to_update],  # citation_count
                ]
            else:
                entity_data = [
                    [entry['id'] for entry in entries_to_update],              # id
                    [entry['author_id'] for entry in entries_to_update],       # author_id
                    [entry['author_name'] for entry in entries_to_update],     # author_name
                    [entry['embedding'] for entry in entries_to_update],       # embedding (preserved)
                    [entry['num_abstracts'] for entry in entries_to_update],   # num_abstracts
                ]
            
            # Upsert the data (updates existing entries)
            self.collection.upsert(entity_data)
            logger.info(f"Successfully updated batch of {len(entries_to_update)} entries")
            return len(entries_to_update)
            
        except Exception as e:
            logger.error(f"Failed to update batch: {e}")
            return 0
    
    def run(self):
        """Run the metadata update process."""
        logger.info("=" * 70)
        logger.info("AUTHOR METADATA UPDATER")
        logger.info("=" * 70)
        logger.info(f"Data directory: {self.data_dir}")
        logger.info(f"Milvus: {self.milvus_host}:{self.milvus_port}")
        logger.info(f"Collection: {self.collection_name}")
        logger.info(f"Batch size: {self.batch_size}")
        logger.info(f"Dry run: {self.dry_run}")
        logger.info("")
        
        try:
            # Step 1: Build author lookup table
            author_lookup = self.build_author_lookup()
            if not author_lookup:
                logger.error("Failed to build author lookup table")
                return
            self.stats["lookup_entries"] = len(author_lookup)
            
            # Step 2: Connect to Milvus
            logger.info("")
            self.connect_to_milvus()
            
            # Step 3: Get all vector entries
            logger.info("")
            all_entries = self.get_all_vector_entries()
            self.stats["total_entries"] = len(all_entries)
            
            # Step 4: Identify entries that need updating
            logger.info("")
            logger.info("Identifying entries that need updates...")
            entries_to_update = []
            
            for entry in all_entries:
                author_id = entry.get("author_id")
                current_name = entry.get("author_name")
                current_citations = entry.get("citation_count", 0)
                
                # Check if this entry needs updating
                needs_update = False
                updated_entry = entry.copy()
                
                # Check if name is wrong (author_id used as name)
                if current_name == author_id and author_id in author_lookup:
                    correct_name = author_lookup[author_id]["name"]
                    if correct_name != author_id:
                        updated_entry["author_name"] = correct_name
                        needs_update = True
                        self.stats["name_updates"] += 1
                
                # Check if citation count is missing or zero and we have data
                if author_id in author_lookup:
                    correct_citations = author_lookup[author_id]["citation_count"]
                    if current_citations == 0 and correct_citations > 0:
                        updated_entry["citation_count"] = correct_citations
                        needs_update = True
                        self.stats["citation_updates"] += 1
                
                if needs_update:
                    entries_to_update.append(updated_entry)
                    if len(entries_to_update) % 100 == 0:
                        logger.info(f"  Found {len(entries_to_update)} entries to update so far...")
            
            logger.info(f"Found {len(entries_to_update)} entries that need updates")
            logger.info(f"  - {self.stats['name_updates']} need name corrections")
            logger.info(f"  - {self.stats['citation_updates']} need citation counts")
            
            # Step 5: Update entries in batches
            if entries_to_update:
                logger.info("")
                logger.info(f"Updating entries in batches of {self.batch_size}...")
                
                for i in range(0, len(entries_to_update), self.batch_size):
                    batch = entries_to_update[i:i + self.batch_size]
                    updated = self.update_entries_batch(batch)
                    self.stats["updated"] += updated
                    
                    logger.info(f"  Progress: {min(i + self.batch_size, len(entries_to_update))}/{len(entries_to_update)}")
                
                logger.info(f"Successfully updated {self.stats['updated']} entries")
            else:
                logger.info("No entries need updating - all metadata is already correct!")
            
        except Exception as e:
            logger.error(f"Update process failed: {e}", exc_info=True)
            raise
        
        finally:
            # Disconnect from Milvus
            if connections.has_connection("default"):
                connections.disconnect("default")
                logger.info("Disconnected from Milvus")
            
            # Print summary
            logger.info("")
            logger.info("=" * 70)
            logger.info("UPDATE SUMMARY")
            logger.info("=" * 70)
            logger.info(f"Authors in lookup table: {self.stats['lookup_entries']}")
            logger.info(f"Total entries in database: {self.stats['total_entries']}")
            logger.info(f"Entries needing name updates: {self.stats['name_updates']}")
            logger.info(f"Entries needing citation updates: {self.stats['citation_updates']}")
            logger.info(f"Entries successfully updated: {self.stats['updated']}")
            logger.info("=" * 70)


def main():
    """
    Update author names and citation counts in the vector database.
    
    This utility:
    - Reads author metadata from compressed JSONL files
    - Connects directly to Milvus to query existing entries
    - Updates entries with incorrect names or missing citation counts
    - Preserves existing embeddings (no recomputation needed)
    - Uses efficient batched upserts
    """
    parser = argparse.ArgumentParser(
        description='Update author names and citation counts in the vector database.'
    )
    
    parser.add_argument(
        '--data-dir',
        default='data/dtic_compressed',
        help='Directory containing compressed author files (default: data/dtic_compressed)'
    )
    
    parser.add_argument(
        '--milvus-host',
        default='localhost',
        help='Milvus server hostname (default: localhost)'
    )
    
    parser.add_argument(
        '--milvus-port',
        type=int,
        default=19530,
        help='Milvus server port (default: 19530)'
    )
    
    parser.add_argument(
        '--collection',
        default='aegis_vectors',
        help='Name of the collection to update (default: aegis_vectors)'
    )
    
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Number of entries to update in each batch (default: 100)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Only show what would be updated without making changes'
    )
    
    args = parser.parse_args()
    
    updater = AuthorMetadataUpdater(
        data_dir=args.data_dir,
        milvus_host=args.milvus_host,
        milvus_port=args.milvus_port,
        collection_name=args.collection,
        dry_run=args.dry_run,
        batch_size=args.batch_size
    )
    updater.run()


if __name__ == "__main__":
    main()
