# DTIC Author-Specific Scraper

Scrapes publications for specific author IDs from DTIC and uploads directly to Azure Blob Storage.

## Features

- **Author-Focused**: Scrapes all publications for specified researcher IDs
- **Direct Azure Upload**: Uploads publications to Azure Blob Storage automatically
- **Same Format**: Uses the same data format as the main DTIC scraper
- **State Management**: Tracks processed publications to avoid duplicates
- **Infinite Scroll Support**: Handles DTIC's infinite scroll to get all publications
- **Rate Limiting**: Respects rate limits and includes exponential backoff
- **Resume Capability**: Can resume interrupted scrapes

## Setup

1. Install dependencies:
```bash
cd utils/dtic/scraping
poetry install
```

2. Ensure you have:
   - Azure Storage connection string
   - Chrome browser installed
   - `config.json` file in the scraping directory (uses same config as main scraper)

## Usage

### Basic Usage (Default Author List)

The script includes a default list of 32 author IDs. To scrape all of them:

```bash
# Set environment variable
$env:AZURE_STORAGE_CONNECTION_STRING = "YOUR_CONNECTION_STRING"

# Run scraper
poetry run python scrape_authors.py
```

### Custom Author List

To scrape specific authors:

```bash
poetry run python scrape_authors.py --author-ids ur.012313314741.93 ur.015064057315.18
```

### Limit Publications Per Author

To limit the number of publications scraped per author:

```bash
poetry run python scrape_authors.py --max-per-author 50
```

### All Options

```bash
poetry run python scrape_authors.py \
    --connection-string "YOUR_CONNECTION_STRING" \
    --output-dir "dtic_publications" \
    --state "author_scraper_state.json" \
    --config "config.json" \
    --max-per-author 100 \
    --no-headless \
    --author-ids ur.012313314741.93 ur.015064057315.18
```

## Command-Line Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--connection-string` | `-c` | From env | Azure Storage connection string |
| `--output-dir` | `-o` | `dtic_publications` | Local output directory |
| `--state` | `-s` | `author_scraper_state.json` | State file path |
| `--config` | | `config.json` | Config file path |
| `--max-per-author` | `-m` | All | Max publications per author |
| `--headless` | | `True` | Run browser in headless mode |
| `--no-headless` | | | Run browser with visible window |
| `--author-ids` | | Default list | Specific author IDs to scrape |

## Environment Variables

### Required

- `AZURE_STORAGE_CONNECTION_STRING`: Your Azure Storage account connection string

Example:
```bash
# PowerShell
$env:AZURE_STORAGE_CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=..."

# Bash
export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=..."
```

## Default Author List

The script includes these 32 author IDs by default:

```
ur.012313314741.93    ur.015064057315.18    ur.015627215165.71    ur.016406327051.56
ur.014452423664.19    ur.012372653735.21    ur.013062772232.30    ur.01213120542.58
ur.014541512746.21    ur.01033404537.13     ur.01220414055.82     ur.012401467325.50
ur.012065075654.47    ur.015137513356.27    ur.016610110700.09    ur.016161161765.09
ur.07511027635.48     ur.011555712101.53    ur.014361216414.52    ur.014753037012.98
ur.013323061215.08    ur.01341474713.23     ur.01017555417.25     ur.0725745110.07
ur.011054365124.22    ur.0715732366.93      ur.01047264435.23     ur.015527265674.84
ur.01042261017.84     ur.01202401101.33     ur.011703135307.28    ur.011727670435.40
```

## How It Works

1. **Initialize**: Sets up WebDriver, rate limiter, Azure uploader
2. **For Each Author**:
   - Navigates to author-filtered search page
   - Extracts visible publication links
   - Scrolls to load more publications
   - For each publication:
     - Opens in new tab
     - Extracts data from JavaScript config
     - Saves locally
     - Uploads to Azure Blob Storage
     - Marks as processed
3. **Resume**: Uses state file to skip already-processed publications

## Data Format

Publications are saved in the same format as the main scraper:

```json
{
  "publication_id": "pub.1234567890",
  "title": "Publication Title",
  "abstract": "Abstract text...",
  "authors": [
    {
      "name": "Author Name",
      "researcher_id": "ur.012313314741.93",
      "affiliations": ["Organization Name"]
    }
  ],
  "organizations": [
    {
      "name": "Organization Name"
    }
  ],
  "publication_date": "1 January 2024",
  "url": "https://dtic.dimensions.ai/...",
  "doi": "10.1234/example",
  "keywords": ["/details/sources/publication/pub.1234567890/for.json"],
  "citations_count": 42,
  "scraped_at": "2026-03-09T12:34:56.789012"
}
```

## Azure Blob Storage

Publications are uploaded to:
- **Container**: `raw`
- **Blob Prefix**: `dtic/works/`
- **Blob Name**: `dtic/works/pub.1234567890.json`

This matches the format used by the main scraper and cleaning scripts.

## State Management

The scraper maintains a state file (`author_scraper_state.json`) that tracks:
- Publications already scraped
- Failed publications
- Last update timestamp

This allows:
- Resuming after interruption
- Avoiding re-scraping publications
- Running multiple times to update with new publications

## Logging

Logs are saved to:
- **Directory**: `logs/`
- **Format**: `YYYYMMDD_HHMMSS_author_scraper.log`

Logs include:
- Author progress (X/Y authors)
- Publication extraction status
- Upload status to Azure
- Errors and warnings

## Example Workflows

### Scrape All Default Authors

```bash
$env:AZURE_STORAGE_CONNECTION_STRING = "YOUR_CONNECTION_STRING"
poetry run python scrape_authors.py
```

### Scrape Specific Authors with Limit

```bash
$env:AZURE_STORAGE_CONNECTION_STRING = "YOUR_CONNECTION_STRING"
poetry run python scrape_authors.py \
    --author-ids ur.012313314741.93 ur.015064057315.18 \
    --max-per-author 100
```

### Test with Visible Browser

```bash
$env:AZURE_STORAGE_CONNECTION_STRING = "YOUR_CONNECTION_STRING"
poetry run python scrape_authors.py \
    --no-headless \
    --max-per-author 5 \
    --author-ids ur.012313314741.93
```

## Troubleshooting

### Connection Errors

If you get Azure connection errors:
1. Verify your connection string is correct
2. Check network connectivity
3. Ensure the container exists (script creates it if not)

### No Publications Found

If no publications are found for an author:
1. Verify the author ID is correct
2. Check the DTIC website manually
3. The author may have no publications in DTIC

### Rate Limiting

If you're being rate limited:
1. The scraper includes automatic exponential backoff
2. Adjust rate limits in `config.json`:
   ```json
   {
     "rate_limiting": {
       "min_delay": 3.0,
       "max_delay": 15.0,
       "base_backoff": 3.0
     }
   }
   ```

### Stale Elements

If you see StaleElementReferenceException errors:
1. These are automatically handled by the scraper
2. The scraper will retry scrolling and link extraction
3. If persistent, try running with `--no-headless` to observe

## Integration with Cleaning Scripts

The publications uploaded by this scraper can be processed by the existing cleaning scripts:

1. **clean_works.py**: Transforms to AEGIS schema
2. **clean_authors.py**: Extracts author entities
3. **clean_topics.py**: Extracts topic/keyword entities
4. **amplify_keywords.py**: Fetches full keyword data

## Performance

- **Speed**: ~2-10 seconds per publication (depends on rate limiting)
- **Memory**: Chrome + Selenium overhead (~200-500 MB)
- **Storage**: ~10-50 KB per publication JSON file

For 32 authors with ~20 publications each:
- Expected time: 2-3 hours
- Expected data: ~30-50 MB

## Notes

- Publications are uploaded to Azure **immediately** after extraction (no need to run separate uploader)
- Local files are also saved for backup
- State file is shared across runs (can resume)
- Uses the same extraction logic as main scraper (JavaScript-only, no DOM fallback)
