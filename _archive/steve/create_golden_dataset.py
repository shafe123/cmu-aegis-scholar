import os
import gzip
import json
from azure.storage.blob import ContainerClient

account_url = "https://aegisscholardata.blob.core.windows.net"
sas_token = "?sv=2024-11-04&ss=bfqt&srt=sco&sp=rwdlacupiytfx&se=2026-05-30T08:31:15Z&st=2026-02-12T01:16:15Z&spr=https&sig=pU5C5a%2B%2BxE1zvMMv3vjUqjlJXC9dMgpsVyM0V%2FfuEIo%3D"
container_name = "raw"
folder_prefix = "openalex/works" 

TARGET_KEYWORDS = [
    "artificial intelligence", "machine learning", "neural network", "deep learning", 
    "deception", "disinformation", "misinformation", "fake news", "psychological operations", "psyops",
    "autonomous", "uav", "cyber", "surveillance" 
]

TARGET_COUNT = 50 
OUTPUT_FILE = "aegis_ai_deception_data.json"

def reconstruct_abstract(inverted_index):
    if not inverted_index: return None
    word_map = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_map.append((pos, word))
    word_map.sort(key=lambda x: x[0])
    return " ".join([word for _, word in word_map])

def extract_authors(authorships):
    if not authorships: return []
    clean_authors = []
    for a in authorships:
        try:
            author_obj = a.get('author') or {}
            institutions = a.get('institutions') or []
            clean_authors.append({
                "name": author_obj.get('display_name', 'Unknown'),
                "id": author_obj.get('id', 'Unknown'),
                "institution": institutions[0].get('display_name', 'Unknown') if institutions else 'Unknown'
            })
        except Exception:
            continue
    return clean_authors

def create_dataset():
    full_container_url = f"{account_url}/{container_name}{sas_token}"
    client = ContainerClient.from_container_url(full_container_url)

    print(f"Listing files in '{folder_prefix}'...")
    blobs = client.list_blobs(name_starts_with=folder_prefix)
    
    golden_data = []
    matches_found = 0
    files_processed = 0

    # LOOP THROUGH MULTIPLE FILES
    for blob in blobs:
        if matches_found >= TARGET_COUNT:
            break
            
        if not blob.name.endswith('.gz'):
            continue

        files_processed += 1
        print(f"\nProcessing File #{files_processed}: {blob.name}")
        local_filename = "temp_current_scan.gz"

        # Download
        try:
            print("Downloading...")
            with open(local_filename, "wb") as download_file:
                download_file.write(client.download_blob(blob.name).readall())
        except Exception as e:
            print(f"   ❌ Failed to download {blob.name}: {e}")
            continue

        # Scan
        print("Scanning...")
        local_matches = 0
        try:
            with gzip.open(local_filename, 'rt', encoding='utf-8') as f:
                for line in f:
                    if matches_found >= TARGET_COUNT:
                        break
                    
                    try:
                        data = json.loads(line)
                        title = data.get('title')
                        if not title: continue
                            
                        if any(k in title.lower() for k in TARGET_KEYWORDS):
                            
                            clean_record = {
                                "id": data.get('id'),
                                "title": title,
                                "publication_year": data.get('publication_year'),
                                "abstract": reconstruct_abstract(data.get('abstract_inverted_index')),
                                "cited_by_count": data.get('cited_by_count'),
                                "authors": extract_authors(data.get('authorships', [])),
                                "referenced_works": data.get('referenced_works', [])
                            }
                            
                            golden_data.append(clean_record)
                            matches_found += 1
                            local_matches += 1
                            
                            # Print less frequently to keep console clean
                            if matches_found % 5 == 0:
                                print(f"      [Total Matches: {matches_found}/{TARGET_COUNT}] Last found: {title[:40]}...")

                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"Error reading file: {e}")

        print(f"Finished file. Found {local_matches} matches here.")
        
        # Cleanup temp file to save space
        if os.path.exists(local_filename):
            os.remove(local_filename)

    # Final Save
    print("\n" + "="*50)
    if matches_found > 0:
        print(f"Saving {matches_found} records to {OUTPUT_FILE}...")
        with open(OUTPUT_FILE, "w", encoding='utf-8') as out:
            json.dump(golden_data, out, indent=2)
        print("Done! Dataset created.")
    else:
        print("Scanned multiple files but found 0 matches. Try broader keywords.")

if __name__ == "__main__":
    create_dataset()