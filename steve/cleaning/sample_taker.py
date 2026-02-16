import json
import gzip
import io
from azure.storage.blob import BlobServiceClient

# --- CONFIGURATION ---
ACCOUNT_URL = "https://aegisscholardata.blob.core.windows.net"
SAS_TOKEN = "?sv=2024-11-04&ss=bfqt&srt=sco&sp=rwdlacupiytfx&se=2026-05-30T08:31:15Z&st=2026-02-12T01:16:15Z&spr=https&sig=pU5C5a%2B%2BxE1zvMMv3vjUqjlJXC9dMgpsVyM0V%2FfuEIo%3D"
CONTAINER_NAME = "raw"

# TARGET: Specifically the "works" folder inside "openalex"
TARGET_FOLDER = "openalex/works/"

def get_first_works_blob(container_client):
    print(f"Scanning inside '{TARGET_FOLDER}' for a .gz file...")
    
    # We list blobs starting with that specific prefix
    blob_list = container_client.list_blobs(name_starts_with=TARGET_FOLDER)
    
    for blob in blob_list:
        if blob.name.endswith('.gz'):
            return blob.name
    return None

def main():
    try:
        print("Connecting to Azure...")
        blob_service_client = BlobServiceClient(account_url=ACCOUNT_URL, credential=SAS_TOKEN)
        container_client = blob_service_client.get_container_client(CONTAINER_NAME)

        # 1. Find the file
        blob_name = get_first_works_blob(container_client)
        if not blob_name:
            print(f"Error: No .gz files found in '{TARGET_FOLDER}'. Check the path!")
            return

        print(f"Found file: {blob_name}")
        blob_client = container_client.get_blob_client(blob_name)

        # 2. Download a chunk (1MB to improve chances of finding a good record)
        print("Downloading 1MB chunk...")
        stream = blob_client.download_blob(offset=0, length=1024 * 1024)
        compressed_data = stream.readall()

        print("Decompressing and searching for a record with an abstract...")
        
        found_record = None
        
        # 3. Read line by line from the compressed stream
        with gzip.GzipFile(fileobj=io.BytesIO(compressed_data)) as f:
            for i, line in enumerate(f):
                try:
                    record = json.loads(line)
                    
                    # Prioritize finding a record that has the abstract index
                    if record.get('abstract_inverted_index'):
                        print(f"Found a record WITH an abstract on line {i+1}!")
                        found_record = record
                        break
                    
                    # If we haven't found one with an abstract yet, keep the first valid record as a backup
                    if found_record is None:
                        found_record = record
                        
                except Exception:
                    continue

        if found_record:
            output_filename = "raw_openalex_work.json"
            with open(output_filename, "w", encoding="utf-8") as out_f:
                json.dump(found_record, out_f, indent=4)
            
            print(f"Saved sample to: {output_filename}")
            
            # Check for the abstract field
            if found_record.get('abstract_inverted_index'):
                print("Note: This record has 'abstract_inverted_index'. Your reconstruction script will work.")
            else:
                print("Note: This specific sample record has NO abstract (it might be null).")
                print("Check the file content to see the structure anyway.")

        else:
            print("Error: Could not find any valid JSON records in the first 1MB.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()