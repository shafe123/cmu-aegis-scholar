import json
import gzip
import io
import time
import os
import re
from azure.storage.blob import BlobServiceClient, ContentSettings

# --- CONFIGURATION ---
ACCOUNT_URL = "https://aegisscholardata.blob.core.windows.net"
SAS_TOKEN = "?sv=2024-11-04&ss=bfqt&srt=sco&sp=rwdlacupiytfx&se=2026-05-30T08:31:15Z&st=2026-02-12T01:16:15Z&spr=https&sig=pU5C5a%2B%2BxE1zvMMv3vjUqjlJXC9dMgpsVyM0V%2FfuEIo%3D"

SOURCE_CONTAINER = "raw"
DEST_CONTAINER = "subsets"

# Scan order: DTIC (Best for DoD) -> OpenAlex (Best Metadata) -> Crossref (Backup)
SOURCES = [
    {"name": "dtic",     "prefix": "dtic/works/",     "type": "json"},
    {"name": "openalex", "prefix": "openalex/works/", "type": "gzip"},
    {"name": "crossref", "prefix": "crossref/",       "type": "gzip"}
]

TARGET_COUNT = 25000  # Total combined records to collect

# --- DEDUPLICATION MEMORY ---
seen_dois = set()
seen_titles = set()

# --- FILTER KEYWORDS ---
DOD_KEYWORDS = [
    "department of defense", "department of war", "dept. of defense", 
    "us army", "u.s. army", "us navy", "u.s. navy", "us air force", 
    "darpa", "office of naval research", "onr", "army research lab", 
    "walter reed", "pentagon", "dtic", "defense technical information center"
]

AI_KEYWORDS = ["artificial intelligence", "machine learning", "neural network", "deep learning", "computer vision", "autonomous systems"]
DEC_KEYWORDS = ["deception", "disinformation", "misinformation", "psyops", "psychological operations", "information warfare"]

# --- NORMALIZERS ---

def normalize_title(title):
    """Strip punctuation/case for deduplication."""
    if not title: return ""
    return re.sub(r'[^a-z0-9]', '', str(title).lower())

def normalize_dtic(record):
    """DTIC -> Standard Schema"""
    return {
        "id": f"dtic:{record.get('accessionNumber') or record.get('id')}",
        "doi": record.get("doi"),
        "title": record.get("title"),
        "abstract_text": record.get("abstract") or record.get("description", ""),
        "publication_year": record.get("publicationDate", "")[:4] if record.get("publicationDate") else None,
        "source": "dtic",
        "raw": record # Save original for graph extraction later
    }

def normalize_crossref(record):
    """Crossref -> Standard Schema"""
    title_list = record.get("title", [])
    title = title_list[0] if title_list else ""
    return {
        "id": f"crossref:{record.get('DOI')}",
        "doi": record.get("DOI"),
        "title": title,
        "abstract_text": record.get("abstract", ""), # Often needs HTML stripping later
        "publication_year": record.get("created", {}).get("date-parts", [[None]])[0][0],
        "source": "crossref",
        "raw": record
    }

def normalize_openalex(record):
    """OpenAlex -> Standard Schema"""
    # Reconstruct abstract
    abstract = ""
    idx = record.get("abstract_inverted_index")
    if idx:
        word_list = []
        for word, positions in idx.items():
            for pos in positions:
                word_list.append((pos, word))
        word_list.sort(key=lambda x: x[0])
        abstract = " ".join([w for _, w in word_list])

    return {
        "id": record.get("id"),
        "doi": record.get("doi"),
        "title": record.get("title"),
        "abstract_text": abstract,
        "publication_year": record.get("publication_year"),
        "source": "openalex",
        "raw": record
    }

# --- MAIN LOGIC ---

def is_duplicate(clean_record):
    """Returns True if paper was seen in a higher-priority source."""
    # 1. DOI Check
    if clean_record.get("doi"):
        if clean_record["doi"] in seen_dois:
            return True
        seen_dois.add(clean_record["doi"])
    
    # 2. Title Check
    norm_title = normalize_title(clean_record.get("title"))
    if norm_title:
        if norm_title in seen_titles:
            return True
        seen_titles.add(norm_title)
        
    return False

def check_filters(record):
    """Classifies record into DoD, AI, and Deception."""
    text = (str(record.get("title")) + " " + str(record.get("abstract_text"))).lower()
    
    # Check DoD context
    is_dod = False
    if record["source"] == "dtic":
        is_dod = True
    else:
        # Check raw metadata for affiliations/funders
        raw_str = str(record.get("raw", "")).lower()
        if any(k in raw_str for k in DOD_KEYWORDS):
            is_dod = True
            
    if not is_dod: return None, False, False

    is_ai = any(k in text for k in AI_KEYWORDS)
    is_dec = any(k in text for k in DEC_KEYWORDS)
    
    return "dod", is_ai, is_dec

def main():
    print("Connecting to Azure...")
    client = BlobServiceClient(account_url=ACCOUNT_URL, credential=SAS_TOKEN)
    container = client.get_container_client(SOURCE_CONTAINER)
    dest_container = client.get_container_client(DEST_CONTAINER)

    # Temporary local files
    temp_files = {
        "master": "temp_unified_master.jsonl",
        "ai":     "temp_unified_ai.jsonl",
        "dec":    "temp_unified_dec.jsonl"
    }
    
    # Open handles
    handles = {k: open(v, "w", encoding="utf-8") for k, v in temp_files.items()}
    
    counts = {"master": 0, "ai": 0, "dec": 0}
    start_time = time.time()

    print(f"Starting Unified Scan... Target: {TARGET_COUNT}")

    for source in SOURCES:
        if counts["master"] >= TARGET_COUNT: break
        
        print(f"\n--- Scanning Source: {source['name'].upper()} ---")
        blobs = container.list_blobs(name_starts_with=source['prefix'])
        
        for blob in blobs:
            if counts["master"] >= TARGET_COUNT: break
            
            try:
                blob_client = container.get_blob_client(blob.name)
                stream = blob_client.download_blob()
                content = stream.readall()
                
                records = []
                
                # Parse based on file type
                if source["type"] == "json":
                    try:
                        data = json.loads(content)
                        records = data if isinstance(data, list) else [data]
                    except: continue 
                elif source["type"] == "gzip":
                    with gzip.GzipFile(fileobj=io.BytesIO(content), mode='rb') as f:
                        for line in f:
                            records.append(json.loads(line))
                            
                # Process batch
                for raw in records:
                    # Normalize
                    clean = None
                    if source["name"] == "dtic": clean = normalize_dtic(raw)
                    elif source["name"] == "crossref": clean = normalize_crossref(raw)
                    elif source["name"] == "openalex": clean = normalize_openalex(raw)
                    
                    if not clean or not clean.get("title"): continue

                    # Deduplicate
                    if is_duplicate(clean):
                        continue

                    # Filter
                    category, is_ai, is_dec = check_filters(clean)
                    
                    if category == "dod":
                        line = json.dumps(clean) + "\n"
                        handles["master"].write(line)
                        counts["master"] += 1
                        
                        if is_ai:
                            handles["ai"].write(line)
                            counts["ai"] += 1
                        if is_dec:
                            handles["dec"].write(line)
                            counts["dec"] += 1
            
            except Exception as e:
                print(f"Skipping {blob.name}: {e}")
                continue
            
            if counts["master"] % 100 == 0:
                print(f"Collected: {counts['master']} (AI: {counts['ai']} | Dec: {counts['dec']})")

    # Close local files
    for h in handles.values(): h.close()
    
    print("\n--- Uploading to Azure 'subsets' Container ---")
    
    # Upload Logic
    def upload(local_path, folder_name):
        if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
            blob_path = f"{folder_name}/dataset.jsonl"
            print(f"Uploading to {blob_path}...")
            with open(local_path, "rb") as data:
                dest_container.upload_blob(blob_path, data, overwrite=True)
    
    upload(temp_files["master"], "unified_dod_master")
    upload(temp_files["ai"],     "unified_dod_ai")
    upload(temp_files["dec"],    "unified_dod_deception")
    
    # Cleanup
    for f in temp_files.values():
        if os.path.exists(f): os.remove(f)

    print(f"\nDone! Unified datasets created in {time.time() - start_time:.2f}s")

if __name__ == "__main__":
    main()
    