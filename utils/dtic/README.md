# DTIC Scraper

A robust, high-performance Selenium-based scraper for extracting publications and technical reports from [DTIC Dimensions](https://dtic.dimensions.ai/discover/publication).

## Performance

⚡ **Optimized for large-scale scraping** (~600k publications)

- **Fast Mode**: JavaScript-first extraction (5-10x faster than DOM parsing)

**Time Estimates:**
- 100 pubs: ~2-5 minutes
- 1,000 pubs: ~20-40 minutes
- 10,000 pubs: ~3-7 hours
- 100,000 pubs: ~1.5-3 days
- 600,000 pubs: ~9-18 days

See [PERFORMANCE.md](PERFORMANCE.md) for detailed optimization guide.

## Quick Start

### Method 1: Single-threaded Scraping (Simple)

```bash
# 1. Ensure dependencies are installed (already done if you ran poetry add selenium)
poetry install

# 2. Verify setup
python verify_setup.py

# 3. Run scraper with a small test (fast mode enabled by default)
python scraper.py --max-publications 5

# 4. Check the output
# Results are in: dtic_publications/ directory (one JSON file per publication)
# State is in: scraper_state.json
# Logs are in: YYYYMMDD_HHMMSS_dtic_scraper.log

# 5. Analyze the data
python analyze.py --summary
```

**Important Note**: The website structure may require selector customization. If you don't see data being extracted, you'll need to:
1. Run with `--no-headless` to see the browser
2. Use browser DevTools (F12) to inspect the actual HTML structure
3. Update selectors in `config.json` to match the current website structure

## Features

### Performance
- ⚡ **Fast Mode**: JavaScript-first extraction (5-10x faster than traditional DOM parsing)
- ⚡ **Optimized Waits**: Smart waiting strategies that minimize page load time
- ⚡ **Scalable**: Designed to handle ~600k publications efficiently

### Reliability
- ✅ **State Persistence**: Automatically saves progress and can resume from where it left off
- ✅ **Rate Limiting**: Configurable delays with exponential backoff to handle rate limiting gracefully
- ✅ **Error Resilience**: Handles network errors, timeouts, and other failures gracefully

### Data Quality
- ✅ **JavaScript Extraction**: Primarily extracts data from embedded `__NUXT__` JavaScript objects
- ✅ **Fallback DOM Parsing**: Uses traditional DOM scraping when JavaScript data unavailable
- ✅ **Author & Organization Data**: Captures detailed information including researcher IDs and affiliations
- ✅ **Rich Metadata**: DOI, publication dates, keywords, citations, document types, abstracts

### Output
- ✅ **Structured Data**: Clean, validated data structures
- ✅ **Analysis Tools**: Built-in utilities for analyzing scraped data

## Installation

```bash
poetry install
```

This will install all required dependencies including:
- selenium
- Chrome WebDriver (automatic)

## Usage

### Single-threaded Scraping (Basic)

For smaller jobs or testing:

```bash
# Scrape with default settings (headless mode)
python scraper.py

# Scrape first 10 pages
python scraper.py --max-pages 10

# Scrape first 100 publications
python scraper.py --max-publications 100

# Run with visible browser window
python scraper.py --no-headless
```

### Resuming Interrupted Sessions

```bash
# Resume from last saved state
python scraper.py --resume

# Resume and scrape up to 50 more publications
python scraper.py --resume --max-publications 50
```

### Advanced Options

```bash
python scraper.py \
  --output custom_output.jsonl \
  --state custom_state.json \
  --max-pages 20 \
  --no-headless
```

## Command Line Arguments

| Argument | Short | Description | Default |
|----------|-------|-------------|---------|
| `--output-dir` | `-o` | Output directory path | `dtic_publications` |
| `--state` | `-s` | State file path | `scraper_state.json` |
| `--config` | `-c` | Config file path | `config.json` |
| `--max-pages` | `-p` | Maximum pages to scrape | None (unlimited) |
| `--max-publications` | `-n` | Maximum publications to scrape | None (unlimited) |
| `--headless` | - | Run browser in headless mode | True |
| `--no-headless` | - | Run browser with visible window | - |
| `--resume` | `-r` | Resume from last saved state | False |

## Configuration

The scraper uses a `config.json` file to customize its behavior. This makes it easy to adjust to website changes without modifying code.

### Configuration Structure

```json
{
  "scraper": {
    "base_url": "https://dtic.dimensions.ai/discover/publication",
    "headless": true
  },
  "rate_limiting": {
    "min_delay": 2.0,
    "max_delay": 10.0,
    "base_backoff": 2.0
  },
  "selectors": {
    "title": ["h1.publication-title", "h1[class*='title']"],
    "abstract": ["div.abstract", "div[class*='abstract']"],
    ...
  }
}
```

### Customizing Selectors

If the website structure changes, you can update the CSS selectors in `config.json`:

1. Open the website with `--no-headless` to see it in action
2. Use browser developer tools (F12) to inspect elements
3. Update the appropriate selector in `config.json`
4. Selectors are tried in order until a match is found

**Example**: To update the title selector:
```json
"selectors": {
  "title": [
    "h1.new-title-class",     // Try this first
    "h1.publication-title",   // Then this
    "h1"                      // Finally, any h1
  ]
}
```

## Output Format

The scraper outputs data as individual JSON files in a directory structure, with one file per publication:

```
dtic_publications/
  ├── pub.1234567890.json
  ├── pub.1234567891.json
  └── pub.1234567892.json
```

Each file contains a formatted JSON object representing a publication:

```json
{
  "publication_id": "pub.1234567890",
  "title": "Example Technical Report",
  "abstract": "This is an abstract...",
  "authors": [
    {
      "name": "John Doe",
      "affiliations": ["Example University"],
      "researcher_id": "res.123456"
    }
  ],
  "organizations": [
    {
      "name": "Example University",
      "org_id": "org.123456",
      "country": null,
      "type": null
    }
  ],
  "publication_date": "2024-01-01",
  "url": "https://dtic.dimensions.ai/details/pub.1234567890",
  "doi": "10.1234/example",
  "document_type": "Technical Report",
  "keywords": ["machine learning", "artificial intelligence"],
  "citations_count": 42,
  "scraped_at": "2026-02-12T10:30:00.123456"
}
```

## State Management

The scraper maintains a state file (`scraper_state.json` by default) that tracks:

- `scraped_ids`: List of successfully scraped publication IDs
- `failed_ids`: List of publication IDs that failed to scrape
- `last_page`: Last processed page number
- `last_updated`: Timestamp of last state update

This allows the scraper to:
1. Skip already-scraped publications when resuming
2. Resume from the last page processed
3. Avoid re-scraping the same data

## Rate Limiting

The scraper includes intelligent rate limiting:

- **Base delay**: 2-10 seconds random delay between requests
- **Exponential backoff**: Automatically increases delay after errors
- **Jitter**: Random delays to avoid detection patterns
- **Error recovery**: Backs off up to 60 seconds on consecutive errors

## Logging

Logs are written to both:
- Console (INFO level and above)
- `YYYYMMDD_HHMMSS_dtic_scraper.log` file (all levels) - timestamped for each run

Log format:
```
2026-02-12 10:30:00,123 - __main__ - INFO - Navigating to https://dtic.dimensions.ai/discover/publication
```

## Customization

### Adjusting Rate Limits

Edit `config.json`:

```json
"rate_limiting": {
  "min_delay": 5.0,      // Minimum delay in seconds
  "max_delay": 15.0,     // Maximum delay in seconds
  "base_backoff": 2.0    // Backoff multiplier
}
```

### Modifying Selectors

If the website structure changes, update the CSS selectors in `config.json`. See the Configuration section above for details.

The scraper will try each selector in order until it finds a match. This makes it resilient to minor website changes.

### Adding Custom Fields

1. Add field to the `Publication` dataclass
2. Extract the data in `_extract_publication_from_page()`
3. The field will automatically be included in the output

## Troubleshooting

### Chrome Driver Issues

If you encounter Chrome driver errors:

```bash
# Make sure Chrome/Chromium is installed
# The driver should be installed automatically by selenium

# If issues persist, try updating selenium:
poetry update selenium
```

### Page Loading Timeout

Increase the wait time in `_extract_publication_from_page()`:

```python
WebDriverWait(self.driver, 20).until(  # Increased from 10 to 20
    EC.presence_of_element_located((By.TAG_NAME, "body"))
)
```

### No Data Extracted

1. Run with `--no-headless` to see what's happening
2. Check the timestamped log file (e.g., `20260212_093000_dtic_scraper.log`) for detailed error messages
3. The website structure may have changed - update CSS selectors

### Rate Limiting Errors

If you're getting blocked:

1. Increase the rate limiting delays
2. Add more random jitter
3. Consider using a VPN or proxy
4. Reduce the scraping speed

## Best Practices

1. **Start small**: Test with `--max-publications 10` first
2. **Use headless mode**: More efficient for long scraping sessions
3. **Monitor logs**: Check the log file regularly for errors
4. **Resume capability**: Use `--resume` if interrupted
5. **Backup data**: Periodically backup the output and state files

## Data Processing

To load and analyze the scraped data:

```python
import json
from pathlib import Path

publications = []
data_dir = Path('dtic_publications')

# Load all JSON files
for json_file in data_dir.glob('*.json'):
    with open(json_file, 'r', encoding='utf-8') as f:
        publications.append(json.load(f))

print(f"Total publications: {len(publications)}")

# Example: Get all unique authors
authors = set()
for pub in publications:
    for author in pub['authors']:
        authors.add(author['name'])

print(f"Unique authors: {len(authors)}")
```

## Azure Blob Storage Upload

The `uploader.py` script automatically uploads scraped publications to Azure Blob Storage.

### Quick Start

```bash
# Set connection string (recommended)
export AZURE_STORAGE_CONNECTION_STRING="YOUR_CONNECTION_STRING"

# One-time upload of all files
poetry run python uploader.py

# Watch mode: continuously upload new files as they're created
poetry run python uploader.py --watch
```

### Run Scraper and Uploader Together

**Windows (PowerShell):**
```powershell
# Set connection string
$env:AZURE_STORAGE_CONNECTION_STRING = "YOUR_CONNECTION_STRING"

# Run script
.\run_scraper_with_uploader.ps1 -MaxPublications 100
```

**Linux/Mac:**
```bash
# Set connection string
export AZURE_STORAGE_CONNECTION_STRING="YOUR_CONNECTION_STRING"

# Run script
chmod +x run_scraper_with_uploader.sh
./run_scraper_with_uploader.sh 100
```

See [UPLOADER_README.md](UPLOADER_README.md) for detailed uploader documentation.

## License

See the main repository for license information.
