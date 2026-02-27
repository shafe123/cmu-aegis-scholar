# DTIC Entity Extractors

These scripts extract entities (organizations, authors, topics, and works) from raw DTIC works in Azure Blob Storage and save them as individual JSON files according to the AEGIS Scholar database schema.

## Available Extractors

- **`clean_orgs.py`**: Extracts organizations from DTIC works
- **`clean_authors.py`**: Extracts authors from DTIC works
- **`clean_topics.py`**: Extracts topics/keywords from DTIC works
- **`clean_works.py`**: Transforms raw works to clean schema format

## Storage Structure

### Organizations
- **Source**: Container `raw`, prefix `dtic/works/`
- **Destination**: Container `clean`, prefix `dtic/orgs/`
- **Filename**: Named by GRID ID (e.g., `grid.213917.f.json`)

### Authors
- **Source**: Container `raw`, prefix `dtic/works/`
- **Destination**: Container `clean`, prefix `dtic/authors/`
- **Filename**: Named by researcher ID (e.g., `ur.015241325677.49.json`)

### Topics
- **Source**: Container `raw`, prefix `dtic/works/`
- **Destination**: Container `clean`, prefix `dtic/topics/`
- **Filename**: Named by entity ID from DTIC (e.g., `80208.json` for uber_cat_id)

### Works
- **Source**: Container `raw`, prefix `dtic/works/`
- **Destination**: Container `clean`, prefix `dtic/works/`
- **Filename**: Named by publication ID (e.g., `pub.1000004508.json`)

## Features

### Organization Extractor
- **Organization Extraction**: Reads raw DTIC works and extracts all organizations
- **Individual Files**: Each organization is saved as a separate JSON file named by its GRID ID
- **Schema Transformation**: Converts raw organization data to match the Organization schema in `database_schemas.json`
- **Entity ID Generation**: Creates deterministic GUIDs for organizations
- **API Amplification**: Fetches additional data from DTIC API endpoints:
  - `/details/facets/publication/funder/{grid}/box.json`
  - `/discover/publication/results.json?and_facet_funder={grid}`
- **Upsert Functionality**: Updates existing organization files with new information
- **State Management**: Tracks processed files to support resumable operations

### Author Extractor
- **Author Extraction**: Reads raw DTIC works and extracts all authors
- **Individual Files**: Each author is saved as a separate JSON file named by researcher ID
- **Schema Transformation**: Converts author data to match the Author schema in `database_schemas.json`
- **Entity ID Generation**: Creates deterministic GUIDs for authors based on researcher ID
- **Organization Linking**: Maps author affiliations to organization IDs
- **API Amplification**: Fetches additional metrics from DTIC API:
  - `/details/facets/publication/researcher/{researcher_id}/box.json`
- **ORCID Integration**: Extracts ORCID IDs from API response and adds them to sources
- **Metrics Extraction**: Citation count and works count (h-index not available from DTIC API)
- **Upsert Functionality**: Updates existing author files and merges org_ids
- **State Management**: Separate state tracking for author extraction

### Topic Extractor
- **Topic Extraction**: Reads raw DTIC works and extracts all topics/keywords
- **Individual Files**: Each topic is saved as a separate JSON file named by entity ID
- **Field/Subfield Hierarchy**: Properly groups 2-digit field codes with 4-digit subfield codes
- **Schema Transformation**: Converts topic data to match the Topic schema in `database_schemas.json`
- **Entity ID Generation**: Creates deterministic GUIDs for topics based on topic name
- **API Amplification**: Optionally fetches additional data from DTIC API for keywords
- **Upsert Functionality**: Updates existing topic files with new information
- **State Management**: Separate state tracking for topic extraction

### Work Extractor
- **Work Transformation**: Reads raw DTIC works and transforms them to clean schema format
- **Individual Files**: Each work is saved as a separate JSON file named by publication ID
- **Schema Transformation**: Converts work data to match the Work schema in `database_schemas.json`
- **Entity ID Generation**: Creates deterministic GUIDs for works based on publication ID
- **Relationship Linking**: Links to author_ids, org_ids, and topic_ids using deterministic GUIDs
- **Author-Org Mapping**: Maps author affiliations to organizations within each work
- **Topic Extraction**: Extracts topics from keywords with relevance scores
- **Upsert Functionality**: Updates existing work files with new information
- **State Management**: Separate state tracking for work extraction

## Requirements

Same as the scraping scripts:
- Python 3.13+
- Azure Storage connection (Blob Storage)
- Poetry for dependency management

## Installation

```powershell
# Install dependencies
poetry install
```

## Configuration

Set your Azure Storage connection string:

```powershell
$env:AZURE_STORAGE_CONNECTION_STRING="your-connection-string-here"
```

Or use the `--connection-string` argument.

## Usage

### Basic Usage

Extract organizations from all raw works:

```powershell
poetry run python clean_orgs.py
```

Extract authors from all raw works:

```powershell
poetry run python clean_authors.py
```

Extract topics from all raw works:

```powershell
poetry run python clean_topics.py
```

Transform works to clean schema format:

```powershell
poetry run python clean_works.py
```

### Common Options

```powershell
# Organizations
poetry run python clean_orgs.py --max-files 100
poetry run python clean_orgs.py --source-container my-raw --dest-container my-clean
poetry run python clean_orgs.py --no-amplification
poetry run python clean_orgs.py --stats

# Authors
poetry run python clean_authors.py --max-files 100
poetry run python clean_authors.py --source-container my-raw --dest-container my-clean
poetry run python clean_authors.py --no-amplification
poetry run python clean_authors.py --stats

# Topics
poetry run python clean_topics.py --max-files 100
poetry run python clean_topics.py --source-container my-raw --dest-container my-clean
poetry run python clean_topics.py --no-amplification
poetry run python clean_topics.py --stats

# Works
poetry run python clean_works.py --max-files 100
poetry run python clean_works.py --source-container my-raw --dest-container my-clean
poetry run python clean_works.py --stats

# Run all in parallel (PowerShell)
Start-Job { poetry run python clean_orgs.py }
Start-Job { poetry run python clean_authors.py }
Start-Job { poetry run python clean_topics.py }
Start-Job { poetry run python clean_works.py }
Get-Job | Wait-Job | Receive-Job
```

### Run Scripts

```powershell
# PowerShell - Run all extractors in parallel
.\run_cleaner.ps1

# PowerShell - Run only organization extractor
.\run_cleaner.ps1 -Orgs

# PowerShell - Run only author extractor
.\run_cleaner.ps1 -Authors

# PowerShell - Run only topic extractor
.\run_cleaner.ps1 -Topics

# PowerShell - Run only work extractor
.\run_cleaner.ps1 -Works

# Bash - Run all extractors in parallel
./run_cleaner.sh

# Bash - Run only organization extractor
./run_cleaner.sh orgs

# Bash - Run only author extractor
./run_cleaner.sh authors

# Bash - Run only topic extractor
./run_cleaner.sh topics

# Bash - Run only work extractor
./run_cleaner.sh works
```

## Data Flow

### Organizations

1. **Input**: Reads from container `raw`, prefix `dtic/works/`
   - Example: `raw/dtic/works/pub.1000004508.json`

2. **Processing**: Extracts organization data from each work

3. **Output**: Saves to container `clean`, prefix `dtic/orgs/`
   - Example: `clean/dtic/orgs/grid.213917.f.json`

### Topics

1. **Input**: Reads from container `raw`, prefix `dtic/works/`
   - Example: `raw/dtic/works/pub.1000004508.json`

2. **Processing**: Extracts topic/keyword data from each work (fetches from API if needed)

3. **Output**: Saves to container `clean`, prefix `dtic/topics/`
   - Example: `clean/dtic/topics/machine_learning.json`

### Input (raw/dtic/works/)

Raw DTIC publication data scraped from dtic.dimensions.ai:

```json
{
  "publication_id": "pub.1000004508",
  "title": "Work Title",
  "abstract": "Abstract text...",
  "authors": [
    {
      "name": "Author Name",
      "affiliations": ["Institution Name"],
      "researcher_id": "ur.015241325677.49"
    }
  ],
  "organizations": [
    {
      "name": "Institution Name",
      "org_id": "grid.213917.f",
      "country": "United States"
    }
  ],
  "publication_date": "1988-07",
  "doi": "10.1002/mma.1670100309",
  "keywords": ["/details/sources/publication/pub.1000004508/for.json"],
  "citations_count": 42
}
```

### Output (clean/dtic/topics/)

Each topic is saved as a separate file named by its sanitized name:

**File: clean/dtic/topics/machine_learning.json**
```json
{
  "id": "topic_12345678-1234-5678-1234-567812345678",
  "name": "Machine Learning",
  "sources": [
    {
      "source": "other",
      "id": "dtic:machine_learning"
    }
  ],
  "created_at": "2026-02-26T10:30:00.000000",
  "last_updated": "2026-02-26T11:45:00.000000"
}
```

**File: clean/dtic/topics/neural_networks.json**
```json
{
  "id": "topic_87654321-8765-4321-8765-432187654321",
  "name": "Neural Networks",
  "field": "Computer Science",
  "sources": [
    {
      "source": "other",
      "id": "dtic:neural_networks"
    }
  ],
  "created_at": "2026-02-26T10:30:00.000000",
  "last_updated": "2026-02-26T11:45:00.000000"
}
```

### Output (clean/dtic/orgs/)

Each organization is saved as a separate file named by its GRID ID:

**File: clean/dtic/orgs/grid.213917.f.json**
```json
{
  "id": "org_87654321-4321-4321-4321-0987654321ba",
  "name": "Georgia Institute of Technology",
  "country": "United States",
  "type": "institution",
  "sources": [
    {
      "source": "dtic",
      "id": "grid.213917.f"
    }
  ],
  "created_at": "2026-02-26T10:30:00.000000",
  "last_updated": "2026-02-26T11:45:00.000000"
}
```

**File: clean/dtic/orgs/grid.7728.a.json**
```json
{
  "id": "org_11223344-5566-7788-99aa-bbccddeeff00",
  "name": "Brunel University London",
  "country": "United Kingdom",
  "type": "institution",
  "sources": [
    {
      "source": "dtic",
      "id": "grid.7728.a"
    }
  ],
  "created_at": "2026-02-26T10:30:00.000000",
  "last_updated": "2026-02-26T11:45:00.000000"
}
```

## State Management

Each extractor maintains its own state file that tracks:

### Organization Extractor (`extraction_state.json`)
- **processed_files**: List of successfully processed work blobs
- **failed_files**: List of blobs that failed processing
- **organizations**: GRID ID → org_id mappings
- **total_processed**: Count of files processed
- **total_orgs_found**: Count of unique organizations discovered

### Topic Extractor (`extraction_state_topics.json`)
- **processed_files**: List of successfully processed work blobs
- **failed_files**: List of blobs that failed processing
- **topics**: topic_name → topic_id mappings
- **total_processed**: Count of files processed
- **total_topics_found**: Count of unique topics discovered

This enables:
- **Resumable processing**: Re-run without re-processing completed files
- **Consistent IDs**: Same entities get the same IDs across runs
- **Incremental updates**: Add new works without affecting existing IDs
- **Independent execution**: Organization and topic extractors can run in parallel

## Schema Compliance

The extractors ensure all output matches the Organization and Topic schemas defined in `data_schema/database_schemas.json`:

- ✅ Proper ID format (e.g., `org_`, `topic_` prefixes)
- ✅ Required fields present
- ✅ Correct data types
- ✅ Valid enum values (e.g., source types)
- ✅ Proper date/datetime formats (ISO 8601)
- ✅ Source tracking for data provenance

## Performance

- **Rate Limiting**: Configurable delay between API requests (default: 0.5s)
- **Batch Processing**: Processes files in sequence with progress logging
- **State Persistence**: Automatic state saving after each file
- **Error Handling**: Failed files are logged and can be retried

## Textractor maintains an `extraction_state.json` file that tracks:

- **processed_files**: List of successfully processed work blobs
- **failed_files**: List of blobs that failed processing
- **organizations**: Consistent ID mappings (grid_id → org_id)

This enables:
- **Resumable processing**: Re-run without re-processing completed files
- **Consistent IDs**: Same organizations get the same IDs across runs
- **Upsert behavior**: New work files can add or update organization data
   ```

3. **State file corruption**
   ```
   Delete cleaning_state.json to start fresh (will regenerate IDs)
   ```
extractor ensures all output matches the Organization schema defined in `data_schema/database_schemas.json`:
extraction_state.json to start fresh (will regenerate IDs)
   ```

## Output Structure

Organizations are saved to container `clean` with prefix `dtic/orgs/` as individual JSON files:
- **Container**: `clean`
- **Prefix**: `dtic/orgs/`
- **Filename**: `{grid_id}.json` (e.g., `grid.213917.f.json`)
- **Content**: Organization entity following the schema
- **Upsert**: If file exists, it's updated with `last_updated` timestamp

## Logs

Logs are saved to `logs/YYYYMMDD_HHMMSS_extract_org
- ✅ Source tracking for data provenance
- ✅ Files named by GRID ID (e.g., `grid.213917.f.json`)