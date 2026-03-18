import json
import gzip
import io
import time
from azure.storage.blob import BlobServiceClient, ContentSettings

# --- CONFIGURATION ---
ACCOUNT_URL = "https://aegisscholardata.blob.core.windows.net"
SAS_TOKEN = "?sv=2024-11-04&ss=bfqt&srt=sco&sp=rwdlacupiytfx&se=2026-05-30T08:31:15Z&st=2026-02-12T01:16:15Z&spr=https&sig=pU5C5a%2B%2BxE1zvMMv3vjUqjlJXC9dMgpsVyM0V%2FfuEIo%3D"

SOURCE_CONTAINER = "raw"
SOURCE_PREFIX = "openalex/works/"  # The root of the works data

DEST_CONTAINER = "clean"
DEST_PREFIX = "openalex/"        # Where we want it to end up

# --- HELPER FUNCTIONS ---

def reconstruct_abstract(inverted_index):
    """Rebuilds the abstract text from the inverted index."""
    if not inverted_index:
        return None
    
    # Collect all (position, word) pairs
    word_list = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_list.append((pos, word))
    
    # Sort by position and join
    word_list.sort(key=lambda x: x[0])
    return " ".join([word for _, word in word_list])

def process_record(record):
    """
    Maximalist extraction for Graph + Vector DBs.
    Captures all IDs, relationships, and semantic text.
    """
    # 1. Basic Validation
    if not record.get('id'):
        return None

    # 2. Extract Authors & Affiliations (The "Who" and "Where")
    # Graph Edge: (Work) -> [AUTHORED_BY] -> (Author)
    # Graph Edge: (Author) -> [AFFILIATED_WITH] -> (Institution)
    clean_authors = []
    if 'authorships' in record:
        for authorship in record.get('authorships', []):
            author = authorship.get('author')
            if not author or not author.get('id'):
                continue
            
            # Extract Institutions for this specific paper
            clean_institutions = []
            for inst in authorship.get('institutions', []):
                if inst.get('id'):
                    clean_institutions.append({
                        "id": inst.get("id"),
                        "display_name": inst.get("display_name"),
                        "country_code": inst.get("country_code"),
                        "type": inst.get("type")
                    })
            
            clean_authors.append({
                "id": author.get("id"),
                "display_name": author.get("display_name"),
                "orcid": author.get("orcid"),
                "position": authorship.get("author_position"), # "first", "last", etc. (Crucial for identifying lead researchers)
                "is_corresponding": authorship.get("is_corresponding"),
                "institutions": clean_institutions
            })

    # 3. Extract Topics (The "New" Taxonomy)
    # Graph Edge: (Work) -> [ABOUT_TOPIC] -> (Topic)
    clean_topics = []
    for topic in record.get('topics', []):
        if topic.get('id'):
            clean_topics.append({
                "id": topic.get("id"),
                "display_name": topic.get("display_name"),
                "score": topic.get("score"), # How strong is the match?
                "subfield": topic.get("subfield", {}).get("display_name"),
                "field": topic.get("field", {}).get("display_name"),
                "domain": topic.get("domain", {}).get("display_name")
            })

    # 4. Extract Concepts (The "Old" Taxonomy - GOLD for Vector Search)
    # Vector Value: These are high-quality keywords to embed with your abstract.
    clean_concepts = []
    for concept in record.get('concepts', []):
        if concept.get('id'):
            clean_concepts.append({
                "id": concept.get("id"),
                "display_name": concept.get("display_name"),
                "score": concept.get("score"),
                "level": concept.get("level") # 0 = General (Physics), 5 = Specific (Neutrino)
            })

    # 5. Extract Source (Journal/Conference)
    # Graph Edge: (Work) -> [PUBLISHED_IN] -> (Source)
    primary_location = record.get("primary_location") or {}
    source = primary_location.get("source") or {}
    
    # 6. Extract Grants / Funders (Who paid for it?)
    # Graph Edge: (Work) -> [FUNDED_BY] -> (Funder)
    clean_grants = []
    for grant in record.get('grants', []):
        if grant.get('funder'):
            clean_grants.append({
                "funder_id": grant.get("funder"), # usually an ID
                "funder_display_name": grant.get("funder_display_name"),
                "award_id": grant.get("award_id")
            })

    # 7. Assemble the Master Record
    clean_record = {
        # --- Core Identity ---
        "id": record.get("id"),
        "doi": record.get("doi"),
        "title": record.get("title"),
        "publication_year": record.get("publication_year"),
        "publication_date": record.get("publication_date"),
        "type": record.get("type"),
        "language": record.get("language"),
        
        # --- The Semantic Payload (For Vector DB) ---
        "abstract": reconstruct_abstract(record.get("abstract_inverted_index")),
        "concepts": clean_concepts, # Rich keywords
        "topics": clean_topics,     # Hierarchical categories
        
        # --- The Graph Connections (For Neo4j/Gremlin) ---
        "authors": clean_authors,
        "referenced_works": record.get("referenced_works", []), # IDs of papers this paper cites
        "related_works": record.get("related_works", []),       # IDs of similar papers (OpenAlex calculated)
        
        # --- Metadata ---
        "cited_by_count": record.get("cited_by_count"),
        "journal_id": source.get("id"),
        "journal_name": source.get("display_name"),
        "is_oa": primary_location.get("is_oa"), # Is it Open Access?
        "pdf_url": primary_location.get("pdf_url"),
        "grants": clean_grants
    }
    
    return clean_record

def main():
    print("Connecting to Azure...")
    blob_service_client = BlobServiceClient(account_url=ACCOUNT_URL, credential=SAS_TOKEN)
    source_container = blob_service_client.get_container_client(SOURCE_CONTAINER)
    dest_container = blob_service_client.get_container_client(DEST_CONTAINER)

    print(f"Scanning {SOURCE_CONTAINER}/{SOURCE_PREFIX} recursively...")
    
    # List all blobs (files) starting with the prefix. This is recursive by default.
    source_blobs = source_container.list_blobs(name_starts_with=SOURCE_PREFIX)
    
    processed_count = 0

    for blob in source_blobs:
        if not blob.name.endswith('.gz'):
            continue

        if "updated_date=" in blob.name:
            try:
                # Extracts "2024-01-01" from the path
                folder_date = blob.name.split("updated_date=")[1].split("/")[0]
                
                if folder_date < "2025-01-01":
                    continue 
            except:
                pass
        # --- PATH CALCULATION ---
        # 1. Get the full path: "openalex/works/updated_date=2024-01-01/part_0000.gz"
        full_source_path = blob.name
        
        # 2. Remove the prefix "openalex/works/" to get the relative path
        #    Result: "updated_date=2024-01-01/part_0000.gz"
        relative_path = full_source_path.replace(SOURCE_PREFIX, "")
        
        # 3. Create destination path
        #    Result: "openalex/updated_date=2024-01-01/part_0000.jsonl"
        dest_blob_name = f"{DEST_PREFIX}{relative_path.replace('.gz', '.jsonl')}"
        
        # Check if already processed
        dest_blob_client = dest_container.get_blob_client(dest_blob_name)
        if dest_blob_client.exists():
            print(f"Skipping {relative_path} (already exists)")
            continue

        print(f"Processing: {relative_path} -> Uncompressed JSONL...")
        start_time = time.time()
        
        try:
            # Download
            source_blob_client = source_container.get_blob_client(blob.name)
            download_stream = source_blob_client.download_blob()
            compressed_data = download_stream.readall() 
            
            # Process
            output_buffer = io.BytesIO()
            record_count = 0
            
            with gzip.GzipFile(fileobj=io.BytesIO(compressed_data), mode='rb') as gz_in:
                for line in gz_in:
                    try:
                        raw_record = json.loads(line)
                        clean_data = process_record(raw_record)
                        
                        if clean_data:
                            json_line = json.dumps(clean_data, ensure_ascii=False) + "\n"
                            output_buffer.write(json_line.encode('utf-8'))
                            record_count += 1
                            
                    except Exception:
                        continue 

            # Upload
            data_size_mb = output_buffer.tell() / (1024 * 1024)
            output_buffer.seek(0)
            
            print(f"Uploading {record_count} records ({data_size_mb:.2f} MB) to {dest_blob_name}...")
            
            dest_blob_client.upload_blob(
                output_buffer, 
                overwrite=True,
                content_settings=ContentSettings(content_type='application/json')
            )
            
            elapsed = time.time() - start_time
            print(f"Success. Time: {elapsed:.2f}s")
            processed_count += 1

        except Exception as e:
            print(f"Error processing {blob.name}: {e}")

    print("-" * 30)
    print(f"Job Complete. Processed {processed_count} files.")

if __name__ == "__main__":
    main()