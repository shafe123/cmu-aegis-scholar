"""
Script to copy authors and works from clean container to subset container for evaluation.

Reads DTIC author IDs from Author Ratings CSV and:
1. Copies author files from dtic/authors/ to evaluation/authors/ in the subsets container
2. Copies their works from dtic/works/ to evaluation/works/ in the subsets container

Usage:
    python copy_evaluation_works.py                 # Copy both authors and works
    python copy_evaluation_works.py --dry-run       # Preview without copying
    python copy_evaluation_works.py --authors-only  # Only copy author files
    python copy_evaluation_works.py --works-only    # Only copy works
"""
import json
import csv
import uuid
import argparse
from typing import Set
from azure.storage.blob import BlobServiceClient, ContentSettings
from collections import defaultdict

# --- CONFIGURATION ---
ACCOUNT_URL = "https://aegisscholardata.blob.core.windows.net"
SAS_TOKEN = "?sv=2024-11-04&ss=bfqt&srt=sco&sp=rwdlacupiytfx&se=2026-05-30T08:31:15Z&st=2026-02-12T01:16:15Z&spr=https&sig=pU5C5a%2B%2BxE1zvMMv3vjUqjlJXC9dMgpsVyM0V%2FfuEIo%3D"

# Source (Read from here)
SOURCE_CONTAINER = "clean"
SOURCE_WORKS_PREFIX = "dtic/works/"
SOURCE_AUTHORS_PREFIX = "dtic/authors/"

# Destination (Write to here)
DEST_CONTAINER = "subsets"
DEST_WORKS_PREFIX = "evaluation/works/"
DEST_AUTHORS_PREFIX = "evaluation/authors/"

# Input CSV
CSV_FILE = "Author Ratings - Overall.csv"


def get_author_guid_from_researcher_id(researcher_id: str) -> str:
    """
    Generate author GUID from researcher ID (same logic as clean_works.py).
    
    Args:
        researcher_id: Researcher ID like ur.015241325677.49
        
    Returns:
        Author GUID with author_ prefix like author_efcff76a-9f19-5e6f-bec0-51e13fce22c6
    """
    namespace = uuid.UUID('00000000-0000-0000-0000-000000000002')
    author_uuid = uuid.uuid5(namespace, researcher_id)
    return f"author_{author_uuid}"


def load_target_authors(csv_path: str) -> tuple[Set[str], Set[str]]:
    """
    Load author IDs from CSV and convert to GUID format.
    
    Args:
        csv_path: Path to the CSV file
        
    Returns:
        Tuple of (researcher_ids, author_guids)
    """
    researcher_ids = set()
    author_guids = set()
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            researcher_id = row.get('author_id', '').strip()
            if researcher_id:
                author_guid = get_author_guid_from_researcher_id(researcher_id)
                researcher_ids.add(researcher_id)
                author_guids.add(author_guid)
                print(f"  {researcher_id} -> {author_guid} ({row.get('Name', 'Unknown')})")
    
    return researcher_ids, author_guids


def copy_blob(source_client, dest_client, source_prefix: str, dest_prefix: str, blob_name: str, dry_run: bool = False) -> bool:
    """
    Copy a blob from source to destination.
    
    Args:
        source_client: Source container client
        dest_client: Destination container client
        source_prefix: Source prefix path
        dest_prefix: Destination prefix path
        blob_name: Name of the blob (without prefix)
        dry_run: If True, only simulate the copy
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if dry_run:
            # In dry-run mode, just check if source exists
            source_blob = source_client.get_blob_client(f"{source_prefix}{blob_name}")
            source_blob.get_blob_properties()  # Will raise if doesn't exist
            return True
        
        # Read from source
        source_blob = source_client.get_blob_client(f"{source_prefix}{blob_name}")
        blob_data = source_blob.download_blob().readall()
        
        # Write to destination
        dest_blob = dest_client.get_blob_client(f"{dest_prefix}{blob_name}")
        dest_blob.upload_blob(
            blob_data,
            overwrite=True,
            content_settings=ContentSettings(content_type='application/json')
        )
        
        return True
    except Exception as e:
        print(f"    Error copying {blob_name}: {e}")
        return False


def copy_authors(source_client, dest_client, researcher_ids: Set[str], dry_run: bool = False) -> dict:
    """
    Copy author files for target authors.
    
    Args:
        source_client: Source container client
        dest_client: Destination container client
        researcher_ids: Set of DTIC researcher IDs (e.g., ur.012313314741.93)
        dry_run: If True, only simulate the copy
        
    Returns:
        Dictionary with statistics
    """
    stats = {'copied': 0, 'errors': 0}
    
    print(f"\nCopying authors from {SOURCE_CONTAINER}/{SOURCE_AUTHORS_PREFIX}...")
    if dry_run:
        print("   (Dry run: will only identify author files)")
    
    for researcher_id in researcher_ids:
        author_filename = f"{researcher_id}.json"
        
        if copy_blob(source_client, dest_client, SOURCE_AUTHORS_PREFIX, DEST_AUTHORS_PREFIX, author_filename, dry_run):
            stats['copied'] += 1
        else:
            stats['errors'] += 1
    
    action = "Would copy" if dry_run else "Copied"
    print(f"   {action} {stats['copied']} author files")
    if stats['errors'] > 0:
        print(f"   Errors: {stats['errors']}")
    
    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Copy works and/or authors for specified authors from clean to subsets container'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview what would be copied without actually copying'
    )
    parser.add_argument(
        '--authors-only',
        action='store_true',
        help='Only copy author files (skip works)'
    )
    parser.add_argument(
        '--works-only',
        action='store_true',
        help='Only copy works (skip author files)'
    )
    args = parser.parse_args()
    
    # Validate arguments
    if args.authors_only and args.works_only:
        print("Error: Cannot specify both --authors-only and --works-only")
        return
    
    # Determine what to copy
    copy_authors_flag = not args.works_only  # Copy authors unless works-only
    copy_works_flag = not args.authors_only  # Copy works unless authors-only
    
    print("="*60)
    print("DTIC Data Copy for Evaluation")
    if args.dry_run:
        print("(DRY RUN MODE - No files will be copied)")
    if args.authors_only:
        print("(AUTHORS ONLY)")
    elif args.works_only:
        print("(WORKS ONLY)")
    print("="*60)
    
    # Load target authors from CSV
    print(f"\n1. Loading target authors from {CSV_FILE}...")
    researcher_ids, author_guids = load_target_authors(CSV_FILE)
    print(f"   Found {len(author_guids)} target authors")
    
    # Connect to Azure
    print("\n2. Connecting to Azure Blob Storage...")
    blob_service_client = BlobServiceClient(account_url=ACCOUNT_URL, credential=SAS_TOKEN)
    source_container = blob_service_client.get_container_client(SOURCE_CONTAINER)
    dest_container = blob_service_client.get_container_client(DEST_CONTAINER)
    print(f"   Source: {SOURCE_CONTAINER}")
    print(f"   Destination: {DEST_CONTAINER}")
    
    # Copy authors first (if requested)
    author_stats = None
    if copy_authors_flag:
        print("\n3. Copying author files...")
        author_stats = copy_authors(source_container, dest_container, researcher_ids, dry_run=args.dry_run)
    
    # Scan works and copy those by target authors (if requested)
    stats = None
    if copy_works_flag:
        step_num = 4 if copy_authors_flag else 3
        print(f"\n{step_num}. Scanning works in {SOURCE_CONTAINER}/{SOURCE_WORKS_PREFIX}...")
        if args.dry_run:
            print("   (Dry run: will only identify matching works)")
        
        stats = {
            'total_works': 0,
            'matching_works': 0,
            'copied_works': 0,
            'errors': 0,
            'works_per_author': defaultdict(int)
        }
        
        blobs = source_container.list_blobs(name_starts_with=SOURCE_WORKS_PREFIX)
        
        for blob in blobs:
            if not blob.name.endswith('.json'):
                continue
                
            stats['total_works'] += 1
            
            try:
                # Download and parse work
                blob_client = source_container.get_blob_client(blob.name)
                work_data = blob_client.download_blob().readall()
                work = json.loads(work_data)
                
                # Check if any author is in target list
                work_authors = work.get('authors', [])
                matching_authors = []
                
                for author_entry in work_authors:
                    author_id = author_entry.get('author_id', '')
                    if author_id in author_guids:
                        matching_authors.append(author_id)
                
                # If match found, copy the work
                if matching_authors:
                    stats['matching_works'] += 1
                    
                    # Extract just the filename from the full blob path
                    work_filename = blob.name[len(SOURCE_WORKS_PREFIX):]
                    
                    # Copy to destination (or simulate in dry-run)
                    if copy_blob(source_container, dest_container, SOURCE_WORKS_PREFIX, DEST_WORKS_PREFIX, work_filename, dry_run=args.dry_run):
                        stats['copied_works'] += 1
                        
                        # Track per-author stats
                        for author_id in matching_authors:
                            stats['works_per_author'][author_id] += 1
                        
                        if stats['copied_works'] % 10 == 0:
                            action = "Would copy" if args.dry_run else "Copied"
                            print(f"   {action} {stats['copied_works']} works so far...")
                    else:
                        stats['errors'] += 1
                
                # Progress update
                if stats['total_works'] % 1000 == 0:
                    print(f"   Scanned {stats['total_works']} works, found {stats['matching_works']} matches")
                        
            except Exception as e:
                print(f"   Error processing {blob.name}: {e}")
                stats['errors'] += 1
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    action = "Would be copied" if args.dry_run else "Successfully copied"
    
    if author_stats is not None:
        print("\nAuthors:")
        print(f"  {action}: {author_stats['copied']}")
        if author_stats['errors'] > 0:
            print(f"  Errors: {author_stats['errors']}")
    
    if stats is not None:
        print("\nWorks:")
        print(f"  Total scanned:    {stats['total_works']}")
        print(f"  Matching found:   {stats['matching_works']}")
        print(f"  {action}: {stats['copied_works']}")
        if stats['errors'] > 0:
            print(f"  Errors:           {stats['errors']}")
        
        print("\nWorks per author:")
        # Sort by count descending
        sorted_authors = sorted(stats['works_per_author'].items(), key=lambda x: x[1], reverse=True)
        for author_id, count in sorted_authors:
            print(f"  {author_id}: {count} works")
    
    if args.dry_run:
        print("\nThis was a dry run. Run without --dry-run to actually copy the files.")
    else:
        print("\nDone!")



if __name__ == "__main__":
    main()
