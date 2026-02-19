# DTIC Keyword Amplifier

This tool amplifies DTIC publication data by fetching actual keywords from the URLs stored in the `keywords` field.

## Overview

DTIC publications initially have keywords stored as URL references like:
```json
"keywords": [
    "/details/sources/publication/pub.1000004508/for.json"
]
```

This script:
1. Reads publications from Azure Blob Storage
2. Fetches the actual keywords from `https://dtic.dimensions.ai` + the URL path
3. Replaces the URL references with the actual keyword data
4. Saves the amplified publications to a new prefix in blob storage

## Prerequisites

- Python 3.7+
- Azure Storage account with DTIC publications
- Required packages: `azure-storage-blob`, `requests`

## Setup

1. Set your Azure Storage connection string:
   ```powershell
   # PowerShell
   $env:AZURE_STORAGE_CONNECTION_STRING = "your-connection-string"
   ```
   
   ```bash
   # Bash
   export AZURE_STORAGE_CONNECTION_STRING="your-connection-string"
   ```

2. Install required packages (if not already installed):
   ```bash
   pip install azure-storage-blob requests
   ```

## Usage

### Quick Start (PowerShell)

```powershell
cd utils/dtic
.\run_amplify_keywords.ps1
```

### Quick Start (Bash)

```bash
cd utils/dtic
chmod +x run_amplify_keywords.sh
./run_amplify_keywords.sh
```

### Advanced Usage

Run the Python script directly for more control:

```bash
python amplify_keywords.py --help
```

#### Options

- `--connection-string`: Azure Storage connection string (or use `AZURE_STORAGE_CONNECTION_STRING` env var)
- `--container`: Blob container name (default: `raw`)
- `--source-prefix`: Source blob prefix (default: `dtic/works/`)
- `--dest-prefix`: Destination blob prefix (default: `dtic/works_amplified/`)
- `--state-file`: State file to track progress (default: `amplify_state.json`)
- `--delay`: Delay between HTTP requests in seconds (default: `0.5`)
- `--max-files`: Maximum number of files to process (default: all)

#### Examples

Process only 10 files for testing:
```bash
python amplify_keywords.py --max-files 10
```

Use faster polling (be careful not to overload the server):
```bash
python amplify_keywords.py --delay 0.2
```

Amplify to a different destination:
```bash
python amplify_keywords.py --dest-prefix "dtic/works_keywords/"
```

## How It Works

1. **List Source Blobs**: Lists all JSON files in the source prefix
2. **Download**: Downloads each publication JSON
3. **Fetch Keywords**: For each keyword URL in the publication:
   - Prepends `https://dtic.dimensions.ai`
   - Fetches the keywords JSON
   - Replaces the URL with actual keywords
4. **Upload**: Uploads the amplified publication to the destination prefix
5. **State Tracking**: Saves progress to avoid reprocessing

## State Management

The script maintains a state file (`amplify_state.json`) that tracks:
- Successfully amplified files
- Failed files
- Skipped files

This allows you to:
- Resume interrupted runs
- Avoid reprocessing already amplified files
- Track failures for manual review

To reset and start over, delete the state file:
```bash
rm amplify_state.json
```

## Output

### Amplified Publications

Amplified publications are saved to `dtic/works_amplified/` with:
- Original data preserved
- `keywords` field replaced with actual keywords
- `keywords_urls` field added with the original keyword URLs
- `keywords_amplified: true` flag added
- `keywords_amplified_at` timestamp added

Example output structure:
```json
{
  "publication_id": "pub.1000004508",
  "title": "Example Publication",
  "keywords": ["Mathematics", "Finite Element Method", "Numerical Analysis"],
  "keywords_urls": ["/details/sources/publication/pub.1000004508/for.json"],
  "keywords_amplified": true,
  "keywords_amplified_at": "2026-02-19T14:30:00.123456"
}
```

### Logs

Logs are saved to `logs/YYYYMMDD_HHMMSS_amplify_keywords.log`

## Error Handling

The script handles various error conditions:
- Network failures when fetching keywords
- Malformed JSON responses
- Missing or invalid keyword URLs
- Azure Storage errors

Failed files are tracked in the state file and logged for review.

## Rate Limiting

The script includes a configurable delay between HTTP requests (default: 0.5 seconds) to avoid overloading the DTIC dimensions.ai server. Adjust with `--delay` if needed.

## Monitoring Progress

The script logs progress every 10 files:
```
Progress: 10/150 processed
Progress: 20/150 processed
...
```

Check the state file for detailed counts:
```powershell
cat amplify_state.json
```

## Troubleshooting

### Connection String Issues
```
Error: Azure Storage connection string not provided
```
Solution: Set the `AZURE_STORAGE_CONNECTION_STRING` environment variable.

### No Blobs Found
```
Warning: No blobs found to process
```
Solution: Check that:
- The container name is correct (default: `raw`)
- The source prefix is correct (default: `dtic/works/`)
- Blobs exist in the source location

### Keyword Fetch Failures
```
Failed to fetch keywords from /details/sources/...
```
Solution: This is logged as a warning. The original URL is kept in place. Check logs for details.

## Performance

- Processing speed depends on:
  - Number of keyword URLs per publication
  - Network latency
  - Rate limiting delay
- Typical: ~2-5 seconds per publication (with 0.5s delay)
- Use `--max-files` for testing before full run
