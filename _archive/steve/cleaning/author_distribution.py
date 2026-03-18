import json
import gzip
import io
import time
import statistics
from collections import defaultdict
from azure.storage.blob import BlobServiceClient

# --- CONFIGURATION ---
ACCOUNT_URL = "https://aegisscholardata.blob.core.windows.net"
SAS_TOKEN = "?sv=2024-11-04&ss=bfqt&srt=sco&sp=rwdlacupiytfx&se=2026-05-30T08:31:15Z&st=2026-02-12T01:16:15Z&spr=https&sig=pU5C5a%2B%2BxE1zvMMv3vjUqjlJXC9dMgpsVyM0V%2FfuEIo%3D"
CONTAINER_NAME = "raw"

# --- MEMORY TRACKERS ---
counts = {
    "dtic": defaultdict(int),
    "openalex": defaultdict(int),
    "crossref": defaultdict(int),
    "overall": defaultdict(int)
}

def extract_authors(source, record):
    """Pulls unique identifiers and logs them in specific and overall trackers."""
    uids = []
    
    if source == "dtic":
        for author in record.get("authors", []):
            uid = author.get("researcher_id") or author.get("name")
            if uid: uids.append(f"dtic:{uid}")

    elif source == "crossref":
        for author in record.get("author", []):
            name = f"{author.get('given', '')} {author.get('family', '')}".strip().lower()
            if name: uids.append(f"crossref:{name}")

    elif source == "openalex":
        if "authors" in record:
            for author in record.get("authors", []):
                uid = author.get("id")
                if uid: uids.append(uid)
        elif "authorships" in record:
            for auth in record.get("authorships", []):
                uid = auth.get("author", {}).get("id")
                if uid: uids.append(uid)

    for uid in uids:
        counts[source][uid] += 1
        counts["overall"][uid] += 1

def print_stats(name, distribution_dict):
    """Calculates and prints stats for a given dataset."""
    distribution = list(distribution_dict.values())
    total_authors = len(distribution)
    
    print(f"\n--- {name.upper()} DATASET ---")
    if total_authors == 0:
        print("No authors found in this dataset.")
        return

    dist_min = min(distribution)
    dist_max = max(distribution)
    dist_mean = statistics.mean(distribution)
    dist_median = statistics.median(distribution)
    dist_stddev = statistics.stdev(distribution) if total_authors > 1 else 0.0

    print(f"Total Unique Authors : {total_authors:,}")
    print(f"  Minimum            : {dist_min}")
    print(f"  Maximum            : {dist_max}")
    print(f"  Mean (Average)     : {dist_mean:.2f}")
    print(f"  Median             : {dist_median}")
    print(f"  Standard Deviation : {dist_stddev:.2f}")

def main():
    print("Connecting to Azure and beginning stream...")
    client = BlobServiceClient(account_url=ACCOUNT_URL, credential=SAS_TOKEN)
    container = client.get_container_client(CONTAINER_NAME)
    
    start_time = time.time()
    files_scanned = 0

    # --- UPDATED PREFIXES BASED ON YOUR FOLDER STRUCTURE ---
    prefixes = ["dtic/works/", "openalex/works/", "crossref/"]
    
    for prefix in prefixes:
        print(f"\nScanning {prefix}...")
        blobs = container.list_blobs(name_starts_with=prefix)
        
        # Identify the source for routing based on the folder name
        source_name = "openalex" if "openalex" in prefix else ("dtic" if "dtic" in prefix else "crossref")
        
        for blob in blobs:
            if not blob.name.endswith(('.gz', '.json')): continue
            
            try:
                stream = container.get_blob_client(blob.name).download_blob()
                data = stream.readall()
                records = []
                
                # Handle compressed vs uncompressed
                if blob.name.endswith('.gz'):
                    with gzip.GzipFile(fileobj=io.BytesIO(data), mode='rb') as f:
                        for line in f: 
                            if line.strip():
                                records.append(json.loads(line))
                else:
                    j = json.loads(data)
                    records = j if isinstance(j, list) else [j]
                
                for record in records:
                    extract_authors(source_name, record)
                    
                files_scanned += 1
                if files_scanned % 100 == 0:
                    print(f"  ...processed {files_scanned} total files.", end="\r")
                    
            except Exception as e:
                pass # Skip corrupted files silently

    print("\n\n" + "="*40)
    print("      FINAL AUTHOR METRICS REPORT")
    print("="*40)
    
    print_stats("DTIC", counts["dtic"])
    print_stats("OpenAlex", counts["openalex"])
    print_stats("Crossref", counts["crossref"])
    
    print("\n" + "="*40)
    print_stats("OVERALL COMBINED", counts["overall"])
    print("="*40)
    
    elapsed = time.time() - start_time
    print(f"\nExecution Time: {elapsed/60:.2f} minutes.")

if __name__ == "__main__":
    main()
    