# Vector Loader Job

One-time initialization job that imports compressed DTIC data into the vector database.

## Overview

This service is designed to run once as a sidecar container. It:

1. Reads compressed JSONL files from `data/dtic_compressed/`
2. Extracts author abstracts from works
3. Generates author embeddings using the vector-db service
4. Uploads embeddings to the vector database
5. Tracks state to avoid duplicate loading

## Features

- **One-time execution**: Checks if data is already loaded before running
- **State tracking**: Maintains state file to track which files have been processed
- **Batch processing**: Processes data in configurable batches
- **Health checks**: Waits for vector-db service to be ready before starting
- **Resume capability**: Can resume from last checkpoint if interrupted
- **Error handling**: Continues processing even if individual records fail

## Configuration

Configure via environment variables:

```bash
# Vector DB API
VECTOR_DB_URL=http://vector-db:8002
VECTOR_DB_TIMEOUT=300

# Data source
DATA_DIR=/data/dtic_compressed

# Collection settings
COLLECTION_NAME=aegis_vectors
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Processing
BATCH_SIZE=100
MAX_RECORDS=  # Leave empty for all records

# State tracking
STATE_FILE=/data/loader_state.json
SKIP_IF_LOADED=true

# Logging
LOG_LEVEL=INFO
```

## Usage

### With Docker Compose

The service is configured in `docker-compose.yml`:

```bash
# Start all services (data-loader will run once and exit)
docker compose -f dev/docker-compose.yml up

# Check logs
docker compose -f dev/docker-compose.yml logs data-loader

# Restart the loader (if needed)
docker compose -f dev/docker-compose.yml restart data-loader
```

### Standalone

```bash
# Install dependencies
cd jobs/vector-loader
poetry install

# Run the loader
poetry run python -m app.loader
```

## State Management

The loader maintains a state file (`loader_state.json`) that tracks:

- List of processed files
- Total records loaded
- Last run timestamp
- Status (never_run, completed, failed)

### Resetting State

To reload all data from scratch:

```bash
# Remove state file
rm data/loader_state.json

# Clear vector database collection
# (use vector-db API or Milvus tools)

# Restart the loader
docker compose -f dev/docker-compose.yml restart data-loader
```

## How It Works

1. **Startup**: Waits for vector-db service health check to pass
2. **Check Status**: Verifies if data is already loaded
   - Checks collection for existing entities
   - Checks state file for completion status
3. **Process Files**: Iterates through compressed JSONL files
   - Reads works from `dtic_works_*.jsonl.gz`
   - Extracts author IDs and abstracts
   - Groups abstracts by author
4. **Generate Embeddings**: For each author:
   - Sends abstracts to vector-db API
   - API generates embeddings using specified model
   - API averages multiple abstracts into single author embedding
5. **Track Progress**: Updates state file after each file
6. **Complete**: Marks state as completed and exits

## Output

The service processes works files and creates author embeddings in the vector database. The embeddings can then be queried using the vector-db service's search endpoints.

**Example Collection Schema:**

```
Collection: aegis_vectors
Fields:
  - id: VARCHAR (primary key)
  - author_id: VARCHAR
  - author_name: VARCHAR
  - embedding: FLOAT_VECTOR (dimension based on model)
  - num_abstracts: INT64
```

## Supported Entity Types

Currently, the loader only processes **works** files to generate author embeddings. Other entity types (authors, organizations, topics) are not yet supported but can be added in future versions.

## Error Handling

- Individual record errors are logged but don't stop processing
- Network errors to vector-db are retried with exponential backoff
- File processing errors skip the file and continue to the next
- Fatal errors mark state as "failed" for investigation

## Development

### Adding New Entity Types

To add support for additional entity types:

1. Add processing method in `loader.py` (e.g., `process_organizations_file`)
2. Add entity type to `entity_types_to_process` list
3. Update vector-db API to accept the new entity type

### Testing

```bash
# Run with limited records for testing
export MAX_RECORDS=100
export SKIP_IF_LOADED=false
poetry run python -m app.loader
```

## Monitoring

Check the logs for progress:

```bash
# Real-time logs
docker compose -f dev/docker-compose.yml logs -f data-loader

# Get container status
docker compose -f dev/docker-compose.yml ps data-loader
```

The loader provides detailed logging:
- File processing progress
- Author upload progress
- Success/failure statistics
- Final summary report
