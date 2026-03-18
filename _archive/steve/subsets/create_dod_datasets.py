import json
import gzip
import io
import time
import os
from azure.storage.blob import BlobServiceClient, ContentSettings

# --- CONFIGURATION ---
ACCOUNT_URL = "https://aegisscholardata.blob.core.windows.net"
SAS_TOKEN = "?sv=2024-11-04&ss=bfqt&srt=sco&sp=rwdlacupiytfx&se=2026-05-30T08:31:15Z&st=2026-02-12T01:16:15Z&spr=https&sig=pU5C5a%2B%2BxE1zvMMv3vjUqjlJXC9dMgpsVyM0V%2FfuEIo%3D"

# Input (Read from here)
SOURCE_CONTAINER = "raw"
SOURCE_PREFIX = "openalex/works/"

# Output (Write to here)
DEST_CONTAINER = "subsets"

# TARGETS
TARGET_DOD_COUNT = 20000  # Stop after finding this many DoD records

# --- KEYWORDS & FILTERS ---
DOD_KEYWORDS = [
    "department of defense", "department of war", "dept. of defense", "dept. of war",
    "us army", "u.s. army", "united states army",
    "us navy", "u.s. navy", "united states navy",
    "us air force", "u.s. air force", "united states air force",
    "us marine corps", "u.s. marine corps",
    "defense advanced research projects agency", "darpa",
    "office of naval research", "onr",
    "army research laboratory", "arl",
    "air force research laboratory", "afrl",
    "naval research laboratory", "nrl",
    "walter reed", "pentagon", "national geospatial-intelligence agency"
]

AI_KEYWORDS = [
    "artificial intelligence", "machine learning", "neural network", 
    "deep learning", "computer vision", "natural language processing",
    "reinforcement learning", "autonomous systems", "robotics", "generative ai"
]
AI_CONCEPT_IDS = ["C154945302", "C41008148"] 

DECEPTION_KEYWORDS = [
    "deception", "deceptive", "disinformation", "misinformation", 
    "propaganda", "psyops", "psychological operations", "information warfare",
    "influence operation", "social engineering", "fake news", "counter-intelligence",
    "manipulation", "strategic communication", "narrative warfare"
]

# --- HELPER FUNCTIONS ---

def reconstruct_abstract(inverted_index):
    if not inverted_index: return ""
    word_list = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_list.append((pos, word))
    word_list.sort(key=lambda x: x[0])
    return " ".join([word for _, word in word_list])

def check_dod_affiliation(record):
    txt_blob = ""
    for authorship in record.get('authorships', []):
        for inst in authorship.get('institutions', []):
            txt_blob += " " + (inst.get('display_name') or "")
    for grant in record.get('grants', []):
        txt_blob += " " + (grant.get('funder_display_name') or "")
    txt_blob = txt_blob.lower()
    return any(k in txt_blob for k in DOD_KEYWORDS)

def check_topic(record, abstract_text, keywords, concept_ids=None):
    if concept_ids:
        for concept in record.get('concepts', []):
            if concept.get('id') and any(cid in concept.get('id') for cid in concept_ids):
                return True
    text_content = ((record.get('title') or "") + " " + abstract_text).lower()
    return any(k in text_content for k in keywords)

def upload_file(blob_service_client, container, folder_name, file_name, local_path):
    """Uploads a local file to a specific folder in Azure Blob Storage."""
    blob_path = f"{folder_name}/{file_name}"
    print(f"Uploading {local_path} to {container}/{blob_path}...")
    
    blob_client = blob_service_client.get_blob_client(container=container, blob=blob_path)
    
    with open(local_path, "rb") as data:
        blob_client.upload_blob(data, overwrite=True, content_settings=ContentSettings(content_type='application/json'))
    print("Upload complete.")

# --- MAIN ---

def main():
    print("Connecting to Azure...")
    blob_service_client = BlobServiceClient(account_url=ACCOUNT_URL, credential=SAS_TOKEN)
    source_container = blob_service_client.get_container_client(SOURCE_CONTAINER)
    
    # Temporary Local Staging Files
    temp_files = {
        "all": "temp_dod_all.jsonl",
        "ai": "temp_dod_ai.jsonl",
        "dec": "temp_dod_deception.jsonl"
    }
    
    # Open local file handles for writing
    handles = {
        "all": open(temp_files["all"], "w", encoding="utf-8"),
        "ai": open(temp_files["ai"], "w", encoding="utf-8"),
        "dec": open(temp_files["dec"], "w", encoding="utf-8")
    }
    
    counts = {"total_scanned": 0, "dod": 0, "ai": 0, "deception": 0}
    start_time = time.time()

    print(f"Starting scan. Target: {TARGET_DOD_COUNT} DoD records.")

    blobs = source_container.list_blobs(name_starts_with=SOURCE_PREFIX)
    
    try:
        for blob in blobs:
            if counts["dod"] >= TARGET_DOD_COUNT:
                break
                
            if not blob.name.endswith('.gz'): continue
            
            stream = source_container.get_blob_client(blob.name).download_blob()
            data = stream.readall()
            
            with gzip.GzipFile(fileobj=io.BytesIO(data), mode='rb') as gz:
                for line in gz:
                    try:
                        record = json.loads(line)
                        counts["total_scanned"] += 1
                        
                        # 1. Filter: DoD/DoW
                        if not check_dod_affiliation(record):
                            continue
                        
                        # Reconstruct Abstract
                        abstract_text = reconstruct_abstract(record.get('abstract_inverted_index'))
                        record['abstract_text'] = abstract_text 
                        
                        # Write to Master Set
                        json_str = json.dumps(record) + "\n"
                        handles["all"].write(json_str)
                        counts["dod"] += 1
                        
                        # 2. Filter: AI
                        if check_topic(record, abstract_text, AI_KEYWORDS, AI_CONCEPT_IDS):
                            handles["ai"].write(json_str)
                            counts["ai"] += 1
                            
                        # 3. Filter: Deception
                        if check_topic(record, abstract_text, DECEPTION_KEYWORDS):
                            handles["dec"].write(json_str)
                            counts["deception"] += 1
                            
                    except Exception:
                        continue

            print(f"Scanned {counts['total_scanned']} docs. Found: {counts['dod']} DoD | {counts['ai']} AI | {counts['deception']} Deception")
            
    finally:
        # Close local files safely
        for h in handles.values():
            h.close()

    print("\n--- PROCESSING COMPLETE. STARTING UPLOAD ---")

    # Upload to Azure (Subsets Container)
    # Folder Structure:
    # subsets/dod_master/dataset.jsonl
    # subsets/dod_ai/dataset.jsonl
    # subsets/dod_deception/dataset.jsonl

    if counts["dod"] > 0:
        upload_file(blob_service_client, DEST_CONTAINER, "dod_master", "dataset.jsonl", temp_files["all"])
    
    if counts["ai"] > 0:
        upload_file(blob_service_client, DEST_CONTAINER, "dod_ai", "dataset.jsonl", temp_files["ai"])
        
    if counts["deception"] > 0:
        upload_file(blob_service_client, DEST_CONTAINER, "dod_deception", "dataset.jsonl", temp_files["dec"])

    # Cleanup Local Files
    print("Cleaning up temporary local files...")
    for f in temp_files.values():
        if os.path.exists(f):
            os.remove(f)

    elapsed = time.time() - start_time
    print(f"Job Finished in {elapsed:.2f}s")

if __name__ == "__main__":
    main()
    