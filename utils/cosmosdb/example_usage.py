"""
Example script demonstrating programmatic usage of the Cosmos DB loader.

This script shows how to use the CosmosDBLoader class in your own Python code
for custom integration scenarios.
"""

import os
import sys
from load_dtic import CosmosDBLoader


def example_basic_load():
    """Example 1: Basic load from environment variables."""
    print("Example 1: Basic Load")
    print("=" * 70)
    
    # Initialize loader with environment variables
    loader = CosmosDBLoader(
        blob_connection_string=os.environ['AZURE_STORAGE_CONNECTION_STRING'],
        blob_container_name='dtic-publications',
        cosmos_endpoint=os.environ['COSMOS_ENDPOINT'],
        cosmos_key=os.environ['COSMOS_KEY'],
        cosmos_database='aegis-scholar',
        cosmos_container='publications'
    )
    
    # Load all blobs
    loaded, failed = loader.load_all_blobs()
    
    print(f"\nResults: {loaded} loaded, {failed} failed")
    print("=" * 70)
    print()


def example_custom_prefix():
    """Example 2: Load with custom blob prefix."""
    print("Example 2: Custom Blob Prefix")
    print("=" * 70)
    
    loader = CosmosDBLoader(
        blob_connection_string=os.environ['AZURE_STORAGE_CONNECTION_STRING'],
        blob_container_name='dtic-publications',
        cosmos_endpoint=os.environ['COSMOS_ENDPOINT'],
        cosmos_key=os.environ['COSMOS_KEY'],
        cosmos_database='aegis-scholar',
        cosmos_container='publications',
        blob_prefix='dtic/special-works/',  # Custom prefix
        state_file='custom_load_state.json'
    )
    
    loaded, failed = loader.load_all_blobs()
    
    print(f"\nResults: {loaded} loaded, {failed} failed")
    print("=" * 70)
    print()


def example_individual_blob():
    """Example 3: Load a specific blob."""
    print("Example 3: Load Individual Blob")
    print("=" * 70)
    
    loader = CosmosDBLoader(
        blob_connection_string=os.environ['AZURE_STORAGE_CONNECTION_STRING'],
        blob_container_name='dtic-publications',
        cosmos_endpoint=os.environ['COSMOS_ENDPOINT'],
        cosmos_key=os.environ['COSMOS_KEY'],
        cosmos_database='aegis-scholar',
        cosmos_container='publications'
    )
    
    # Load a specific blob
    blob_name = 'dtic/works/pub.1000004508.json'
    success = loader.load_blob_to_cosmos(blob_name)
    
    if success:
        print(f"\nSuccessfully loaded: {blob_name}")
        loader.state_manager.mark_loaded(blob_name)
    else:
        print(f"\nFailed to load: {blob_name}")
        loader.state_manager.mark_failed(blob_name)
    
    print("=" * 70)
    print()


def example_list_blobs():
    """Example 4: List available blobs without loading."""
    print("Example 4: List Available Blobs")
    print("=" * 70)
    
    loader = CosmosDBLoader(
        blob_connection_string=os.environ['AZURE_STORAGE_CONNECTION_STRING'],
        blob_container_name='dtic-publications',
        cosmos_endpoint=os.environ['COSMOS_ENDPOINT'],
        cosmos_key=os.environ['COSMOS_KEY'],
        cosmos_database='aegis-scholar',
        cosmos_container='publications'
    )
    
    # List all blobs
    blobs = loader.list_blobs()
    
    print(f"\nFound {len(blobs)} blobs:")
    for i, blob in enumerate(blobs[:10], 1):  # Show first 10
        print(f"  {i}. {blob}")
    
    if len(blobs) > 10:
        print(f"  ... and {len(blobs) - 10} more")
    
    print("=" * 70)
    print()


def example_stats():
    """Example 5: Get loading statistics."""
    print("Example 5: Get Statistics")
    print("=" * 70)
    
    loader = CosmosDBLoader(
        blob_connection_string=os.environ['AZURE_STORAGE_CONNECTION_STRING'],
        blob_container_name='dtic-publications',
        cosmos_endpoint=os.environ['COSMOS_ENDPOINT'],
        cosmos_key=os.environ['COSMOS_KEY'],
        cosmos_database='aegis-scholar',
        cosmos_container='publications'
    )
    
    # Get stats
    stats = loader.get_stats()
    
    print("\nLoading Statistics:")
    print(f"  Total loaded: {stats['total_loaded']}")
    print(f"  Total failed: {stats['total_failed']}")
    print(f"  Last updated: {stats['last_updated']}")
    
    print("=" * 70)
    print()


def example_force_reload():
    """Example 6: Force reload of all documents."""
    print("Example 6: Force Reload")
    print("=" * 70)
    
    loader = CosmosDBLoader(
        blob_connection_string=os.environ['AZURE_STORAGE_CONNECTION_STRING'],
        blob_container_name='dtic-publications',
        cosmos_endpoint=os.environ['COSMOS_ENDPOINT'],
        cosmos_key=os.environ['COSMOS_KEY'],
        cosmos_database='aegis-scholar',
        cosmos_container='publications'
    )
    
    # Force reload all blobs (ignore state)
    loaded, failed = loader.load_all_blobs(force_reload=True)
    
    print(f"\nResults: {loaded} loaded, {failed} failed")
    print("=" * 70)
    print()


def example_openalex_load():
    """Example 7: Load OpenAlex data (compressed JSONL with URL IDs)."""
    print("Example 7: Load OpenAlex Data")
    print("=" * 70)
    
    loader = CosmosDBLoader(
        blob_connection_string=os.environ['AZURE_STORAGE_CONNECTION_STRING'],
        blob_container_name='raw',
        cosmos_endpoint=os.environ['COSMOS_ENDPOINT'],
        cosmos_key=os.environ['COSMOS_KEY'],
        cosmos_database='aegisraw',
        cosmos_container='openalex-works',
        blob_prefix='openalex/works/',  # OpenAlex JSONL files
        partition_key='id'  # Will be cleaned from URL format
    )
    
    print("\nNote: OpenAlex IDs like 'https://openalex.org/W2741809807'")
    print("      will be automatically cleaned to 'W2741809807'")
    print()
    
    # Load compressed JSONL files
    files_loaded, files_failed, total_docs = loader.load_all_blobs()
    
    print("\nResults:")
    print(f"  Files loaded: {files_loaded}")
    print(f"  Files failed: {files_failed}")
    print(f"  Total documents: {total_docs}")
    print("=" * 70)
    print()


def main():
    """Run examples."""
    # Check required environment variables
    required_vars = ['AZURE_STORAGE_CONNECTION_STRING', 'COSMOS_ENDPOINT', 'COSMOS_KEY']
    missing = [var for var in required_vars if var not in os.environ]
    
    if missing:
        print("Error: Missing required environment variables:")
        for var in missing:
            print(f"  - {var}")
        print("\nSet them using:")
        print('  export AZURE_STORAGE_CONNECTION_STRING="..."')
        print('  export COSMOS_ENDPOINT="https://..."')
        print('  export COSMOS_KEY="..."')
        return 1
    
    # Run examples
    print("\nCosmos DB Loader - Example Usage")
    print("=" * 70)
    print()
    
    try:
        # Uncomment the example you want to run:
        
        # example_basic_load()
        # example_custom_prefix()
        # example_individual_blob()
        example_list_blobs()
        example_stats()
        # example_force_reload()
        # example_openalex_load()  # Load OpenAlex compressed JSONL with URL cleaning
        
        print("\nAll examples completed successfully!")
        return 0
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 1
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
