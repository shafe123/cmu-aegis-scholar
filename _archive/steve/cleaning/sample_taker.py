import json
import gzip
import io
from azure.storage.blob import BlobServiceClient

# --- CONFIGURATION ---
ACCOUNT_URL = "https://aegisscholardata.blob.core.windows.net"
SAS_TOKEN = "?sv=2024-11-04&ss=bfqt&srt=sco&sp=rwdlacupiytfx&se=2026-05-30T08:31:15Z&st=2026-02-12T01:16:15Z&spr=https&sig=pU5C5a%2B%2BxE1zvMMv3vjUqjlJXC9dMgpsVyM0V%2FfuEIo%3D"
CONTAINER = "raw"
PREFIX = "openalex/works/"

def inspect_modern():
    print("Connecting...")
    client = BlobServiceClient(account_url=ACCOUNT_URL, credential=SAS_TOKEN)
    container = client.get_container_client(CONTAINER)
    
    print("Scanning for a MODERN file (2024+)...")
    # We iterate until we find a file with a recent date in the name
    blob_iterator = container.list_blobs(name_starts_with=PREFIX)
    target_blob = None
    
    for blob in blob_iterator:
        # LOOK FOR 2024 or 2025 in the filename
        if ("updated_date=2024" in blob.name or "updated_date=2025" in blob.name) and blob.name.endswith('.gz'):
            target_blob = blob
            break
            
    if not target_blob:
        print("ERROR: Could not find any files from 2024 or 2025!")
        return

    print(f"Downloading header from: {target_blob.name}")
    blob_client = container.get_blob_client(target_blob.name)
    stream = blob_client.download_blob()
    data = stream.readall()
    
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data), mode='rb') as f:
            # Read the first line only
            first_line = f.readline()
            record = json.loads(first_line)
            
            print("\n" + "="*40)
            print(" MODERN DATA VERIFICATION ")
            print("="*40)
            print(f"Record ID: {record.get('id', 'MISSING')}")
            print(f"Title:     {record.get('title', 'No Title')[:60]}...")
            
            # 1. TOPICS (The new taxonomy)
            print("\n--- 1. TOPICS (Crucial for Vector Search) ---")
            topics = record.get('topics', [])
            if topics:
                t = topics[0]
                print(f"✅ Found {len(topics)} topics.")
                print(f"   Sample: {t.get('display_name')} (Score: {t.get('score')})")
                print(f"   Domain: {t.get('domain', {}).get('display_name')}")
            else:
                print("⚠️ No topics found.")

            # 2. INSTITUTIONS (Crucial for Graph)
            print("\n--- 2. INSTITUTIONS (Crucial for Experts) ---")
            has_inst = False
            if 'authorships' in record:
                for auth in record['authorships']:
                    insts = auth.get('institutions', [])
                    if insts:
                        print(f"✅ Found Institution: {insts[0].get('display_name')}")
                        print(f"   Country: {insts[0].get('country_code')}")
                        print(f"   ID: {insts[0].get('id')}")
                        has_inst = True
                        break # Just show one
            if not has_inst:
                print("⚠️ No institutions listed in this record.")

            # 3. FUNDER / GRANTS (Crucial for 'Who Paid')
            print("\n--- 3. FUNDING (Crucial for Analysis) ---")
            grants = record.get('grants', [])
            if grants:
                print(f"✅ Found {len(grants)} grants.")
                print(f"   Funder: {grants[0].get('funder_display_name')}")
            else:
                print("ℹ️ No grants listed (Common for many papers).")

            # 4. REFERENCES
            print("\n--- 4. REFERENCES (Crucial for Citations) ---")
            refs = record.get('referenced_works', [])
            print(f"Found {len(refs)} references.")

    except Exception as e:
        print(f"Error reading file: {e}")

if __name__ == "__main__":
    inspect_modern()