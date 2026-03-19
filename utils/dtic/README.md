# DTIC Utilities

Utilities for working with DTIC (Defense Technical Information Center) data.

## Prerequisites

Install the required dependencies:

```powershell
pip install -r requirements.txt
```

This includes:
- `azure-storage-blob` - For Azure Blob Storage operations
- `orjson` - Fast JSON serialization (optional but recommended)

---

## Download DTIC Data from Azure Blob Storage

The `download_dtic_from_blob.py` script downloads all DTIC data from the Azure Blob Storage "clean" container to your local machine.

### Authentication

You need either:
1. **Connection String**: Set the `AZURE_STORAGE_CONNECTION_STRING` environment variable, OR
2. **SAS Token**: Pass it with `--sas-token` argument

```powershell
# Option 1: Using environment variable
$env:AZURE_STORAGE_CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net"

# Option 2: Using SAS token in command
```

### Usage

```powershell
# Basic usage - downloads all dtic/ blobs to data/dtic/
python download_dtic_from_blob.py

# Dry run to preview what would be downloaded
python download_dtic_from_blob.py --dry-run

# Download to a custom directory
python download_dtic_from_blob.py --output-dir "C:\my\custom\path"

# Download only first 100 files (for testing)
python download_dtic_from_blob.py --max-files 100

# Use SAS token for authentication
python download_dtic_from_blob.py --sas-token "?sv=2024-11-04&ss=bfqt&srt=sco&sp=rwdlacupiytfx..."

# Increase parallel downloads
python download_dtic_from_blob.py --max-workers 10

# Verbose logging
python download_dtic_from_blob.py --verbose
```

### Examples

```powershell
# Common workflow: First check what would be downloaded
python download_dtic_from_blob.py --dry-run

# Then download everything
python download_dtic_from_blob.py

# Download specific subset for testing
python download_dtic_from_blob.py --max-files 50 --output-dir "data/dtic_test"
```

### Output Structure

The script maintains the same directory structure from Azure Blob Storage:

```
data/dtic/
├── authors/
│   ├── author_abc123.json
│   └── ...
├── works/
│   ├── work_xyz789.json
│   └── ...
├── organizations/
│   └── ...
└── topics/
    └── ...
```

### Options

- `--connection-string`: Azure Storage connection string (alternative to env var)
- `--sas-token`: Azure Storage SAS token (including the `?` prefix)
- `--output-dir`: Local directory to save files (default: `data/dtic`)
- `--container`: Blob container name (default: `clean`)
- `--prefix`: Blob prefix to filter (default: `dtic/`)
- `--max-files`: Limit number of files to download (useful for testing)
- `--max-workers`: Number of parallel download threads (default: 5)
- `--dry-run`: Preview without actually downloading
- `--verbose`: Enable detailed logging

### Notes

- Files that already exist locally will be skipped (to re-download, delete local files first)
- Downloads run in parallel for better performance (default: 5 concurrent downloads)
- Progress is logged every 10 files
- Failed downloads are logged at the end

---

## Compress JSON Files to JSONL

The `compress_to_jsonl.py` script converts individual JSON files into compressed JSONL (JSON Lines) format, with chunks of approximately 50MB compressed size.

### What it does

- Reads individual JSON files from `data/dtic/` subdirectories
- Combines them into JSONL format (one JSON object per line, no indentation)
- Compresses with gzip
- Splits into ~50MB chunks per entity type
- Outputs to `data/dtic_compressed/`

### Usage

```powershell
# Compress all entity types (authors, works, organizations, topics)
python compress_to_jsonl.py

# Dry run to preview compression
python compress_to_jsonl.py --dry-run

# Compress specific entity types only
python compress_to_jsonl.py --entity-types authors works

# Custom input/output directories
python compress_to_jsonl.py --input-dir data/dtic --output-dir data/compressed

# Different target chunk size (100MB instead of 50MB)
python compress_to_jsonl.py --target-size 100

# Verbose logging
python compress_to_jsonl.py --verbose
```

### Output Structure

```
data/dtic_compressed/
├── dtic_authors_001.jsonl.gz       (~50 MB)
├── dtic_authors_002.jsonl.gz       (~50 MB)
├── dtic_works_001.jsonl.gz         (~50 MB)
├── dtic_works_002.jsonl.gz         (~50 MB)
├── dtic_works_003.jsonl.gz         (~50 MB)
├── dtic_organizations_001.jsonl.gz (~50 MB)
└── dtic_topics_001.jsonl.gz        (~50 MB)
```

### Options

- `--input-dir`: Input directory with entity subdirectories (default: `data/dtic`)
- `--output-dir`: Output directory for compressed files (default: `data/dtic_compressed`)
- `--entity-types`: Specific entity types to process (default: all)
- `--target-size`: Target compressed chunk size in MB (default: 50)
- `--dry-run`: Preview without actually compressing
- `--verbose`: Enable detailed logging

### Reading Compressed JSONL Files

You can read the compressed JSONL files in Python:

```python
import gzip
import json

# Read compressed JSONL file
with gzip.open('data/dtic_compressed/dtic_authors_001.jsonl.gz', 'rt', encoding='utf-8') as f:
    for line in f:
        obj = json.loads(line)
        # Process each object
        print(obj['id'])
```

Or with orjson for faster parsing:

```python
import gzip
import orjson

with gzip.open('data/dtic_compressed/dtic_authors_001.jsonl.gz', 'rb') as f:
    for line in f:
        obj = orjson.loads(line)
        # Process each object
        print(obj['id'])
```

### Notes

- Uses `orjson` library for fast JSON serialization (falls back to standard `json` if not available)
- JSONL format is more efficient than pretty-printed JSON (no indentation)
- Compressed files are typically 10-20% of original pretty-printed JSON size
- Each chunk contains complete JSON objects (no objects split across files)
- Files are processed in sorted order for consistent output

---

## Check Data Pipeline Status

The `check_status.py` script checks the status of data loading and verifies the vector database.

### Usage

```powershell
# Check status of data loader and vector database
python check_status.py

# Install httpx for vector DB checks (optional)
pip install httpx
```

### What it checks

- **Data Loader State**: Reads `data/loader_state.json` to check completion status
- **Vector DB Health**: Queries the vector-db service health endpoint
- **Collection Status**: Checks if the collection exists and has data

### Example Output

```
DTIC Data Pipeline Status Check

======================================================================
DATA LOADER STATE
======================================================================
Status: completed
Last Run: 2026-03-19 14:23:45
Total Records Loaded: 125,432
Files Processed: 3

✓ Data loading completed successfully!

======================================================================
VECTOR DATABASE STATUS
======================================================================
Service: healthy
Milvus Connected: True

Collection: aegis_vectors
Entities: 45,678
Indexed: True

✓ Vector database has data!

======================================================================
SUMMARY
======================================================================
✓ Data pipeline is complete and healthy
```

---

## Complete Data Pipeline

For the complete workflow from download to vector database loading, see:

**[📖 Data Pipeline Quick Start Guide](../../docs/QUICKSTART_DATA_PIPELINE.md)**

The complete pipeline includes:
1. Download data from Azure Blob Storage (`download_dtic_from_blob.py`)
2. Compress to JSONL format (`compress_to_jsonl.py`)
3. Load into vector database (Docker service: `vector-loader`)
4. Verify status (`check_status.py`)

## Related Services

- **[jobs/vector-loader](../../jobs/vector-loader/)** - Job that loads compressed data into vector DB
- **[services/vector-db](../../services/vector-db/)** - Vector database API service
- **[dev/docker-compose.yml](../../dev/docker-compose.yml)** - Docker Compose configuration for all services
