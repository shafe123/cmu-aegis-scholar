import sys
import json
import gzip
import io
import time
from azure.storage.blob import BlobServiceClient, ContentSettings

# --- CONFIGURATION ---
ACCOUNT_URL = "https://aegisscholardata.blob.core.windows.net"
SAS_TOKEN = "?sv=2024-11-04&ss=bfqt&srt=sco&sp=rwdlacupiytfx&se=2026-05-30T08:31:15Z&st=2026-02-12T01:16:15Z&spr=https&sig=pU5C5a%2B%2BxE1zvMMv3vjUqjlJXC9dMgpsVyM0V%2FfuEIo%3D"
SOURCE_CONTAINER = "raw"
DEST_CONTAINER = "clean"

# --- ENTITY PROCESSORS ---

def process_author(record):
    """
    Nodes for Graph DB: (Author)
    """
    if not record.get('id'): return None
    
    # Get last known institution (useful for 'Experts at CMU' queries)
    last_known = record.get('last_known_institution') or {}
    
    return {
        "id": record.get("id"),
        "display_name": record.get("display_name"),
        "orcid": record.get("orcid"),
        "works_count": record.get("works_count"),
        "cited_by_count": record.get("cited_by_count"),
        "last_known_institution": {
            "id": last_known.get("id"),
            "name": last_known.get("display_name"),
            "country_code": last_known.get("country_code")
        }
    }

def process_institution(record):
    """
    Nodes for Graph DB: (Institution)
    Geo-Spatial Data included for 'Universities near me' queries.
    """
    if not record.get('id'): return None
    
    geo = record.get('geo', {})
    
    return {
        "id": record.get("id"),
        "display_name": record.get("display_name"),
        "ror": record.get("ror"),
        "country_code": record.get("country_code"),
        "type": record.get("type"), # education, healthcare, company, etc.
        "homepage_url": record.get("homepage_url"),
        "geo": {
            "city": geo.get("city"),
            "latitude": geo.get("latitude"),
            "longitude": geo.get("longitude")
        },
        "works_count": record.get("works_count"),
        "cited_by_count": record.get("cited_by_count")
    }

def process_topic(record):
    """
    Nodes for Vector DB: (Topic)
    CRITICAL: Captures descriptions/keywords for semantic embedding.
    """
    if not record.get('id'): return None
    
    return {
        "id": record.get("id"),
        "display_name": record.get("display_name"),
        "description": record.get("description"), # EMBED THIS LATER
        "keywords": record.get("keywords", []),   # EMBED THIS LATER
        "subfield": {
            "id": record.get("subfield", {}).get("id"),
            "display_name": record.get("subfield", {}).get("display_name")
        },
        "field": {
            "id": record.get("field", {}).get("id"),
            "display_name": record.get("field", {}).get("display_name")
        },
        "domain": {
            "id": record.get("domain", {}).get("id"),
            "display_name": record.get("domain", {}).get("display_name")
        }
    }

def process_source(record):
    """
    Nodes for Graph DB: (Journal/Conference)
    """
    if not record.get('id'): return None
    
    return {
        "id": record.get("id"),
        "display_name": record.get("display_name"),
        "issn_l": record.get("issn_l"),
        "issn": record.get("issn"),
        "publisher": record.get("host_organization_name"),
        "type": record.get("type"), # journal, conference, repository
        "is_oa": record.get("is_oa"), # Open Access?
        "works_count": record.get("works_count")
    }

# --- MAIN LOGIC ---

def main():
    if len(sys.argv) < 2:
        print("Usage: python clean_entities.py [authors|institutions|topics|sources]")
        sys.exit(1)
        
    entity_type = sys.argv[1]
    
    # Map input argument to folder path and processor function
    config = {
        "authors":      {"prefix": "openalex/authors/",      "func": process_author},
        "institutions": {"prefix": "openalex/institutions/", "func": process_institution},
        "topics":       {"prefix": "openalex/topics/",       "func": process_topic},
        "sources":      {"prefix": "openalex/sources/",      "func": process_source}
    }
    
    if entity_type not in config:
        print(f"Invalid entity type. Choose from: {list(config.keys())}")
        sys.exit(1)
        
    settings = config[entity_type]
    SOURCE_PREFIX = settings["prefix"]
    DEST_PREFIX = settings["prefix"] # Keep same structure
    process_func = settings["func"]
    
    print(f"--- STARTING JOB: {entity_type.upper()} ---")
    
    blob_service_client = BlobServiceClient(account_url=ACCOUNT_URL, credential=SAS_TOKEN)
    source_container = blob_service_client.get_container_client(SOURCE_CONTAINER)
    dest_container = blob_service_client.get_container_client(DEST_CONTAINER)
    
    print(f"Scanning {SOURCE_CONTAINER}/{SOURCE_PREFIX}...")
    source_blobs = source_container.list_blobs(name_starts_with=SOURCE_PREFIX)
    
    processed_count = 0
    
    for blob in source_blobs:
        if not blob.name.endswith('.gz'):
            continue
            
        # Path Calculation
        # Source: openalex/authors/updated_date=2024.../part_000.gz
        # Dest:   openalex/authors/updated_date=2024.../part_000.jsonl
        relative_path = blob.name.replace(SOURCE_PREFIX, "")
        dest_blob_name = f"{DEST_PREFIX}{relative_path.replace('.gz', '.jsonl')}"
        
        # Check Exists
        dest_blob_client = dest_container.get_blob_client(dest_blob_name)
        if dest_blob_client.exists():
            print(f"Skipping {relative_path} (exists)")
            continue
            
        print(f"Processing: {relative_path}")
        start_time = time.time()
        
        try:
            # Download & Process
            stream = source_container.get_blob_client(blob.name).download_blob()
            data = stream.readall()
            
            output_buffer = io.BytesIO()
            record_count = 0
            
            with gzip.GzipFile(fileobj=io.BytesIO(data), mode='rb') as gz_in:
                for line in gz_in:
                    try:
                        raw = json.loads(line)
                        clean = process_func(raw) # <--- Calls the specific function
                        if clean:
                            output_buffer.write((json.dumps(clean) + "\n").encode('utf-8'))
                            record_count += 1
                    except:
                        continue
                        
            # Upload
            output_buffer.seek(0)
            dest_blob_client.upload_blob(
                output_buffer, 
                overwrite=True,
                content_settings=ContentSettings(content_type='application/json')
            )
            print(f"Uploaded {record_count} records. Time: {time.time() - start_time:.2f}s")
            processed_count += 1
            
        except Exception as e:
            print(f"Error on {blob.name}: {e}")
            
    print(f"Job Complete. Processed {processed_count} files.")

if __name__ == "__main__":
    main()
    