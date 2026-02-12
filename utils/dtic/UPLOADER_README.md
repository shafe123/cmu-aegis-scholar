# Azure Blob Storage Uploader

Uploads DTIC publication JSON files to Azure Blob Storage with state tracking.

## Setup

1. Install dependencies:
```bash
poetry install
```

2. Get your Azure Storage connection string from the Azure Portal

## Usage

### Using Environment Variable (Recommended)

Set the connection string as an environment variable:

**Windows (PowerShell):**
```powershell
$env:AZURE_STORAGE_CONNECTION_STRING = "YOUR_CONNECTION_STRING"
poetry run python uploader.py --watch
```

**Windows (Command Prompt):**
```cmd
set AZURE_STORAGE_CONNECTION_STRING=YOUR_CONNECTION_STRING
poetry run python uploader.py --watch
```

**Linux/Mac:**
```bash
export AZURE_STORAGE_CONNECTION_STRING="YOUR_CONNECTION_STRING"
poetry run python uploader.py --watch
```

### Using Command Line Argument

Alternatively, pass the connection string directly:

```bash
poetry run python uploader.py --connection-string "YOUR_CONNECTION_STRING" --watch
```

### One-time Upload

Upload all files once and exit:

```bash
poetry run python uploader.py --connection-string "YOUR_CONNECTION_STRING"
```

### Watch Mode

Continuously monitor the directory and upload new files:

```bash
poetry run python uploader.py --connection-string "YOUR_CONNECTION_STRING" --watch
```

### Custom Configuration

```bash
poetry run python uploader.py \
  --connection-string "YOUR_CONNECTION_STRING" \
  --container "my-container" \
  --publications-dir "dtic_publications" \
  --blob-prefix "data/" \
  --watch \
  --interval 30
```

## Options

- `--connection-string`, `-c`: Azure Storage connection string (optional if `AZURE_STORAGE_CONNECTION_STRING` env var is set)
- `--container`, `-n`: Container name (default: `dtic-publications`)
- `--publications-dir`, `-d`: Publications directory (default: `dtic_publications`)
- `--state`, `-s`: State file path (default: `upload_state.json`)
- `--blob-prefix`, `-p`: Blob prefix in container (default: `publications/`)
- `--watch`, `-w`: Enable watch mode
- `--interval`, `-i`: Watch interval in seconds (default: 10)

## Environment Variable

The uploader checks for the `AZURE_STORAGE_CONNECTION_STRING` environment variable automatically. This is the **recommended approach** as it:
- Keeps secrets out of command history
- Makes scripts cleaner
- Works consistently across runs

Set it once per session or add to your shell profile for persistence.

## State Management

The uploader maintains a `upload_state.json` file that tracks:
- Files successfully uploaded
- Files that failed to upload
- Last update timestamp

This allows the uploader to:
- Resume after interruption
- Avoid re-uploading existing files
- Track upload progress

## Example Workflow

Run the scraper and uploader together:

```bash
# Set connection string once
export AZURE_STORAGE_CONNECTION_STRING="YOUR_CONNECTION_STRING"

# Terminal 1: Run scraper
poetry run python scraper.py --max-publications 1000

# Terminal 2: Run uploader in watch mode
poetry run python uploader.py --watch --interval 5
```

The uploader will automatically detect and upload new files as the scraper creates them.
