# Cosmos DB Loader

Load JSON data from Azure Blob Storage into Cosmos DB.

## Overview

This script downloads JSON files (regular, compressed, or JSONL format) from Azure Blob Storage and inserts them into Cosmos DB. It supports multiple data sources (DTIC, OpenAlex, etc.), maintains state to avoid duplicate loads, and provides comprehensive logging.

## Features

- **Multiple Format Support**: Handles regular JSON, compressed (.gz), and JSONL (JSON Lines) files
- **Data Source Agnostic**: Works with DTIC, OpenAlex, and other JSON-based data sources
- **Blob Storage Integration**: Downloads files from Azure Blob Storage with prefix filtering
- **Cosmos DB Integration**: Inserts documents into Cosmos DB with automatic upsert
- **Compressed File Support**: Automatically decompresses gzipped files
- **JSONL Support**: Parses JSON Lines format where each line is a separate document
- **State Management**: Tracks which files have been loaded to avoid duplicates
- **Error Handling**: Comprehensive error handling with partial success support
- **Logging**: Timestamped logs for debugging and monitoring
- **Batch Processing**: Efficient processing of multiple documents per file
- **Resume Support**: Can resume from previous runs using state file
- **Serverless Compatible**: Works with both serverless and provisioned Cosmos DB accounts

## Prerequisites

1. **Python 3.8+**
2. **Azure Blob Storage account** with JSON files uploaded
3. **Cosmos DB account** (serverless or provisioned)
   - The script automatically works with both serverless and provisioned accounts
   - For serverless accounts, containers are created without throughput settings
   - For provisioned accounts, you may want to manually create containers with desired RU/s

## Installation

Install required dependencies:

```bash
pip install azure-storage-blob azure-cosmos
```

Or if using the project dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

### Environment Variables (Recommended)

Set the following environment variables:

```bash
# Azure Blob Storage
export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net"

# Cosmos DB
export COSMOS_ENDPOINT="https://<your-account>.documents.azure.com:443/"
export COSMOS_KEY="<your-cosmos-key>"
```

**Windows (PowerShell):**
```powershell
$env:AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net"
$env:COSMOS_ENDPOINT="https://<your-account>.documents.azure.com:443/"
$env:COSMOS_KEY="<your-cosmos-key>"
```

### Command-Line Arguments

Alternatively, provide credentials via command-line arguments:

```bash
python load_dtic.py \
  --blob-connection-string "DefaultEndpointsProtocol=https;..." \
  --cosmos-endpoint "https://<your-account>.documents.azure.com:443/" \
  --cosmos-key "<your-cosmos-key>"
```

## Usage

### Basic Usage

Load all JSON/compressed files from Blob Storage into Cosmos DB:

```bash
python load_dtic.py
```

### DTIC Publications

Load DTIC publications with specific prefix:

```bash
python load_dtic.py \
  --blob-prefix "dtic/works/" \
  --cosmos-container "dtic-works" \
  --partition-key "publication_id"
```

Or using PowerShell:

```powershell
.\run_loader.ps1 -BlobPrefix "dtic/works/" -CosmosContainer "dtic-works" -PartitionKey "publication_id"
```

### OpenAlex Data

Load compressed OpenAlex JSONL files:

```bash
python load_dtic.py \
  --blob-prefix "openalex/works/" \
  --cosmos-container "openalex-works" \
  --partition-key "id"
```

Or using PowerShell:

```powershell
.\run_loader.ps1 -BlobPrefix "openalex/works/" -CosmosContainer "openalex-works"
```

### Custom Configuration

```bash
python load_dtic.py \
  --blob-container my-container \
  --blob-prefix custom/data/ \
  --cosmos-database aegis-scholar \
  --cosmos-container my-collection \
  --partition-key "custom_id" \
  --batch-size 100
```

### Force Reload

Reload all files, including already loaded ones:

```bash
python load_dtic.py --force-reload
```

### Custom State File

Use a different state file for tracking:

```bash
python load_dtic.py --state-file my_load_state.json
```

## Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--blob-connection-string` | Azure Blob Storage connection string | `$AZURE_STORAGE_CONNECTION_STRING` |
| `--blob-container` | Blob container name | `dtic-publications` |
| `--blob-prefix` | Blob prefix to filter files (e.g., "dtic/works/", "openalex/works/") | `` (empty, all files) |
| `--cosmos-endpoint` | Cosmos DB endpoint URL | `$COSMOS_ENDPOINT` |
| `--cosmos-key` | Cosmos DB master key | `$COSMOS_KEY` |
| `--cosmos-database` | Cosmos DB database name | `aegis-scholar` |
| `--cosmos-container` | Cosmos DB container name | `publications` |
| `--partition-key` | Partition key path for Cosmos DB | `id` |
| `--state-file` | State file path | `load_state.json` |
| `--batch-size` | Documents per batch | `100` |
| `--force-reload` | Reload already loaded blobs | `False` |

## Supported File Formats

The script automatically detects and processes:

### Regular JSON
Single JSON object or array in a file:
```json
{
  "id": "12345",
  "title": "Document Title",
  ...
}
```

### JSON Lines (JSONL)
Multiple JSON objects, one per line (common for OpenAlex):
```
{"id": "W123", "title": "Paper 1", ...}
{"id": "W456", "title": "Paper 2", ...}
{"id": "W789", "title": "Paper 3", ...}
```

### Compressed Files
Any of the above formats compressed with gzip (.gz extension):
- `document.json.gz`
- `works.jsonl.gz`
- `data.gz`

## Document Structure

The script works with any JSON structure. It automatically handles the `id` field required by Cosmos DB:

**DTIC Example:**
```json
{
  "publication_id": "pub.1000004508",
  "title": "Document Title",
  "abstract": "Document abstract...",
  "authors": [...],
  "organizations": [...],
  "publication_date": "1988-07",
  "url": "https://...",
  "doi": "10.1002/...",
  "document_type": "Article",
  "keywords": [...],
  "citations_count": 0,
  "scraped_at": "2026-02-12T15:28:05.593362"
}
```

**OpenAlex Example:**
```json
{
  "id": "https://openalex.org/W2741809807",
  "doi": "https://doi.org/10.7717/peerj.4375",
  "title": "The state of OA: a large-scale analysis",
  "publication_year": 2018,
  "type": "article",
  "open_access": {...},
  "authorships": [...],
  "document_type": "Article",
  "keywords": [...],
  "citations_count": 0,
  "scraped_at": "2026-02-12T15:28:05.593362"
}
```

### ID Field Handling

The script automatically handles the `id` field required by Cosmos DB:
1. If the document has an `id` field, it uses that (after cleaning)
2. Otherwise, it tries common ID fields: `publication_id`, `work_id`, `doi`
3. As a last resort, generates a hash-based ID

**URL Cleaning:** The script automatically strips URL prefixes from IDs:
- `https://openalex.org/W2741809807` → `W2741809807`
- `https://doi.org/10.7717/peerj.4375` → `10.7717/peerj.4375`
- `pub.1000004508` → `pub.1000004508` (no change)

This ensures clean IDs suitable for partitioning and querying in Cosmos DB.

The partition key is configurable via `--partition-key` (default: `id`).

## State File

The script maintains a JSON state file (`load_state.json` by default) with:

```json
{
  "loaded_files": ["dtic/works/pub.1000004508.json", "openalex/works/batch1.jsonl.gz", ...],
  "failed_files": [],
  "last_updated": "2026-02-19T10:30:00",
  "total_documents": 150
}
```

This allows the script to:
- Skip already loaded files
- Track failed loads for retry
- Resume from interruptions
- Track total document count across all files

## Logging

Logs are written to:
- Console (stdout)
- File: `logs/YYYYMMDD_HHMMSS_cosmos_loader.log`

Log levels:
- **INFO**: Normal operations, progress updates
- **WARNING**: Recoverable issues
- **ERROR**: Failed operations

## Error Handling

The script handles:
- Network failures (with retry)
- Invalid JSON files
- Cosmos DB quota errors
- Missing credentials
- Interrupted operations

Failed files are tracked in the state file and can be retried later.

## Examples

### Example 1: Load DTIC Publications

```bash
# Set environment variables
export AZURE_STORAGE_CONNECTION_STRING="..."
export COSMOS_ENDPOINT="https://my-cosmos.documents.azure.com:443/"
export COSMOS_KEY="..."

# Run the loader for DTIC data
python load_dtic.py --blob-prefix "dtic/works/" --cosmos-container "dtic-works"
```

Output:
```
2026-02-19 10:30:00 - Connected to Azure Blob Storage container: raw
2026-02-19 10:30:01 - Connected to Cosmos DB container: dtic-works
2026-02-19 10:30:02 - Found 150 JSON blobs in Azure Blob Storage
2026-02-19 10:30:03 - [1/150] Processing: dtic/works/pub.1000004508.json
2026-02-19 10:30:03 - [OK] Loaded: dtic/works/pub.1000004508.json (1 document(s))
...
======================================================================
Load Summary:
  New files loaded: 150
  Total documents inserted: 150
  Files failed: 0
  Total files loaded (all time): 150
  Total files failed (all time): 0
  Last updated: 2026-02-19T10:35:00
======================================================================
```

### Example 2: Load OpenAlex Compressed Data

```powershell
# PowerShell - Load compressed JSONL files from OpenAlex
.\run_loader.ps1 -BlobPrefix "openalex/works/" -CosmosContainer "openalex-works"
```

Output shows multiple documents per file:
```
2026-02-19 11:00:00 - [1/50] Processing: openalex/works/updated_date=2024-01-15/part_000.jsonl.gz
2026-02-19 11:00:05 - [OK] Loaded: openalex/works/...part_000.jsonl.gz (1000 document(s))
2026-02-19 11:00:10 - [2/50] Processing: openalex/works/updated_date=2024-01-15/part_001.jsonl.gz
2026-02-19 11:00:15 - [OK] Loaded: openalex/works/...part_001.jsonl.gz (1000 document(s))
...
======================================================================
Load Summary:
  New files loaded: 50
  Total documents inserted: 50000
  Files failed: 0
======================================================================
```

### Example 3: Resume After Interruption

The script automatically resumes from where it left off:

```bash
python load_dtic.py
```

Output:
```
2026-02-19 11:00:00 - Loaded state: 75 files loaded
2026-02-19 11:00:01 - Found 150 JSON blobs in Azure Blob Storage
2026-02-19 11:00:02 - [1/150] Skipping already loaded: dtic/works/pub.1000004508.json
...
2026-02-19 11:00:03 - [76/150] Processing: dtic/works/pub.1000098148.json
...
```

### Example 3: Force Reload

Force reload all documents (useful for schema updates):

```bash
python load_dtic.py --force-reload
```

## Troubleshooting

### Connection Errors

**Problem**: `Failed to connect to Azure Blob Storage`

**Solution**: Check your connection string:
```bash
echo $AZURE_STORAGE_CONNECTION_STRING
```

### Cosmos DB Errors

**Problem**: `Failed to connect to Cosmos DB`

**Solution**: Verify endpoint and key:
```bash
echo $COSMOS_ENDPOINT
echo $COSMOS_KEY
```

**Problem**: `Setting offer throughput or autopilot on container is not supported for serverless accounts`

**Solution**: This error should not occur with the current version of the script, which automatically detects serverless accounts. If you see this error:
1. Ensure you're using the latest version of the script
2. The script now creates containers without throughput settings, which works for both serverless and provisioned accounts
3. For existing containers, the script will use them regardless of account type

### Rate Limiting

**Problem**: `Request rate too large`

**Solution**: Cosmos DB throughput may be insufficient. Either:
1. Increase RU/s in Azure Portal
2. Reduce `--batch-size`
3. Add delays between requests

### State File Issues

**Problem**: State file corrupted

**Solution**: Delete and start fresh:
```bash
rm load_state.json
python load_dtic.py
```

## Integration with Workflow

This loader fits into various data pipelines:

### DTIC Workflow
1. **Scrape**: `scraper.py` scrapes DTIC publications
2. **Upload**: `uploader.py` uploads JSON to Azure Blob Storage  
3. **Load**: `load_dtic.py` loads into Cosmos DB (this script)
4. **Query**: Applications query Cosmos DB

### OpenAlex Workflow
1. **Download**: Download OpenAlex snapshots (compressed JSONL files)
2. **Upload**: Upload to Azure Blob Storage
3. **Load**: `load_dtic.py` with `--blob-prefix "openalex/"` loads into Cosmos DB
4. **Query**: Applications query Cosmos DB

### Generic Workflow
1. **Data Source**: Any system producing JSON/JSONL data
2. **Storage**: Store in Azure Blob Storage (compressed or not)
3. **Load**: This script loads into Cosmos DB with appropriate prefix
4. **Query**: Applications query Cosmos DB

## Best Practices

1. **Use environment variables** for credentials (never commit credentials)
2. **Use blob prefixes** to organize different data sources
3. **Monitor logs** for failed loads and partial successes
4. **Backup state file** before force-reload operations
5. **Set appropriate partition keys** for your data model
6. **Use compressed formats** for large datasets to reduce storage costs
7. **Regular incremental loads** rather than force-reload
8. **Separate state files** for different data sources/prefixes

## Performance

Typical performance:
- **Small files (< 50KB)**: ~10-20 documents/second
- **Large files (> 100KB)**: ~5-10 documents/second
- **Network dependent**: Varies by Azure region and connection

## License

See project LICENSE file.
