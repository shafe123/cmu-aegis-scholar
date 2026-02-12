import os
import gzip
import json
from azure.storage.blob import ContainerClient

account_url = "https://aegisscholardata.blob.core.windows.net"

sas_token = "?sv=2024-11-04&ss=bfqt&srt=sco&sp=rwdlacupiytfx&se=2026-05-30T08:31:15Z&st=2026-02-12T01:16:15Z&spr=https&sig=pU5C5a%2B%2BxE1zvMMv3vjUqjlJXC9dMgpsVyM0V%2FfuEIo%3D"

container_name = "raw"
folder_prefix = "openalex/data/works"


def inspect_first_file():
    full_container_url = f"{account_url}/{container_name}{sas_token}"
    client = ContainerClient.from_container_url(full_container_url)

    print(f"Searching for files in '{folder_prefix}'...")
    
    blobs = client.list_blobs(name_starts_with=folder_prefix)
    first_blob = next(blobs, None)

    if not first_blob:
        print("No files found! Check your folder_prefix or container name.")
        return

    print(f"Found file: {first_blob.name}")
    local_filename = "sample_openalex_data.gz"

    print("Downloading file (this might take a few seconds)...")
    with open(local_filename, "wb") as download_file:
        download_file.write(client.download_blob(first_blob.name).readall())

    print("File downloaded. Peeking inside...\n" + "="*50)

    try:
        with gzip.open(local_filename, 'rt', encoding='utf-8') as f:
            for i in range(2):
                line = f.readline()
                if not line: break
                
                data = json.loads(line)
                print(f"\n--- Record #{i+1} ---")
                print(json.dumps(data, indent=2))
                
        print("\n" + "="*50)
        print("Success! You can now analyze the structure of 'sample_openalex_data.gz'")
        
    except Exception as e:
        print(f"Error reading GZIP file: {e}")

if __name__ == "__main__":
    inspect_first_file()