# Vector DB Service

A FastAPI microservice for performing vector similarity search using Milvus vector database.

## Overview

This service provides RESTful API endpoints for interacting with a Milvus vector database, enabling semantic search capabilities for the AEGIS Scholar project.

## Features

- **Vector Similarity Search**: Perform efficient similarity searches using pre-computed embedding vectors
- **Text-Based Semantic Search**: Query using natural language - automatically converts text to embeddings
- **Author Embeddings**: Generate and store author embeddings from paper abstracts using sentence transformers
- **Automatic Averaging**: Intelligently average multiple abstract embeddings to create representative author vectors
- **Collection Management**: List and inspect Milvus collections
- **Health Monitoring**: Check service and database connection health
- **Configurable**: Environment-based configuration for different deployment scenarios
- **Pagination Support**: Efficiently paginate through large search results

## Prerequisites

- Python 3.12+
- Poetry (for dependency management)
- Milvus 2.3+ (vector database)

## Installation

### Using Poetry

```bash
cd services/vector-db
poetry install
```

### Using Docker

Build the Docker image:

```bash
docker build -t vector-db:latest .
```

## Configuration

The service can be configured using environment variables or a `.env` file:

```env
# Milvus Configuration
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_USER=
MILVUS_PASSWORD=

# Collection Configuration
DEFAULT_COLLECTION=aegis_vectors
EMBEDDING_DIM=768

# Pagination Configuration
DEFAULT_LIMIT=10
MAX_LIMIT=100

# Embedding Model Configuration
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2

# API Configuration
API_TITLE=AEGIS Scholar Vector DB Service
API_VERSION=0.1.0
```

## Running the Service

### Development Mode

```bash
cd services/vector-db
poetry run uvicorn app.main:app --reload --port 8002
```

### Production Mode

```bash
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8002
```

### Using Docker Compose

From the project root:

```bash
docker compose -f dev/docker-compose.yml up --build -d vector-db
```

## Service Initialization

On startup, the service automatically:
1. **Connects to Milvus** - Establishes connection to the vector database
2. **Loads the embedding model** - Downloads and initializes the sentence transformer model (first run only)
3. **Creates the default collection** - Automatically creates the `aegis_vectors` collection with the proper schema if it doesn't exist

This ensures the service is ready to accept author embedding requests immediately after startup.

## API Endpoints

### Root
- `GET /` - Service information

### Health
- `GET /health` - Health check with Milvus connection status

### Collections
- `GET /collections` - List all available collections
- `GET /collections/{collection_name}` - Get information about a specific collection

### Search
- `POST /search/vector` - Perform vector similarity search with a pre-computed embedding vector
- `POST /search/text` - Perform semantic search using natural language text queries

#### Vector Search Request Example

For direct vector search with pre-computed embeddings:

```json
{
  "query_vector": [0.1, 0.2, 0.3, ...],
  "collection_name": "aegis_vectors",
  "limit": 10,
  "offset": 0,
  "output_fields": ["id", "title", "content"],
  "filter_expr": "year > 2020"
}
```

#### Text Search Request Example

For natural language text queries (automatically converted to embeddings):

```json
{
  "query_text": "machine learning applications in healthcare",
  "collection_name": "aegis_vectors",
  "limit": 10,
  "offset": 0,
  "output_fields": ["id", "author_name", "num_abstracts"],
  "filter_expr": null
}
```

**Pagination Parameters:**
- `limit`: Maximum number of results to return (1-100, default: 10)
- `offset`: Number of results to skip (default: 0)

**Search Methods:**
- **Vector Search** (`/search/vector`): Use when you already have embedding vectors
- **Text Search** (`/search/text`): Use for natural language queries - automatically converts text to embeddings

**Use Cases:**
- `/search/vector`: When integrating with external embedding models or pre-computed vectors
- `/search/text`: For end-user search interfaces, chatbots, or natural language queries

#### Search Response Example

```json
{
  "results": [
    {
      "id": "123",
      "distance": 0.85,
      "entity": {
        "id": "123",
        "title": "Example Paper",
        "content": "..."
      }
    }
  ],
  "collection_name": "aegis_vectors",
  "search_time_ms": 15.3,
  "pagination": {
    "offset": 0,
    "limit": 10,
    "returned": 10,
    "has_more": true
  }
}
```

**Pagination Metadata:**
- `offset`: The offset value used in the request
- `limit`: The limit value used in the request
- `returned`: Actual number of results returned
- `has_more`: Boolean indicating if more results are available

### Authors
- `POST /authors/embeddings` - Create or update author embedding from abstracts (upsert operation)
- `POST /authors/vector` - Create or update author with pre-computed embedding vector (upsert operation)

#### Create Author Embedding Request Example

```json
{
  "author_id": "A123456",
  "author_name": "Dr. Jane Smith",
  "abstracts": [
    "This paper presents a novel machine learning approach...",
    "We investigate deep learning techniques for...",
    "Our research focuses on neural networks..."
  ],
  "collection_name": "aegis_vectors",
  "metadata": {
    "institution": "MIT",
    "field": "Computer Science"
  }
}
```

**Parameters:**
- `author_id` (required): Unique identifier for the author
- `author_name` (required): Name of the author
- `abstracts` (required): List of paper abstracts (minimum 1)
- `collection_name` (optional): Target collection (defaults to `aegis_vectors`)
- `metadata` (optional): Additional metadata

#### Create Author Embedding Response Example

```json
{
  "author_id": "A123456",
  "author_name": "Dr. Jane Smith",
  "embedding_dim": 384,
  "num_abstracts_processed": 3,
  "collection_name": "aegis_vectors",
  "success": true,
  "message": "Author embedding created and stored successfully"
}
```

**Note:** The message will indicate whether the embedding was "created" (new author) or "updated" (existing author).

**How it works:**
1. Default collection is automatically created on service startup with the proper schema
2. Takes a list of paper abstracts for an author
3. Generates embeddings for each abstract using a sentence transformer model
4. Averages the embeddings to create a single author representation
5. Upserts the averaged embedding in the specified collection (creates new or updates existing)

**Upsert Behavior:**
- If the author doesn't exist, a new entry is created
- If the author already exists (same `author_id`), their embedding is updated with the new averaged values
- This allows you to refresh author embeddings as new papers become available

#### Create Author Vector Request Example

For uploading pre-computed embedding vectors:

```json
{
  "author_id": "A123456",
  "author_name": "Dr. Jane Smith",
  "embedding": [0.025, -0.134, 0.892, ...],
  "num_abstracts": 15,
  "collection_name": "aegis_vectors",
  "metadata": {
    "source": "external_system",
    "computed_date": "2024-01-15"
  }
}
```

**Parameters:**
- `author_id` (required): Unique identifier for the author
- `author_name` (required): Name of the author
- `embedding` (required): Pre-computed embedding vector (must match collection dimension)
- `num_abstracts` (optional): Number of abstracts used to compute the embedding
- `collection_name` (optional): Target collection (defaults to `aegis_vectors`)
- `metadata` (optional): Additional metadata

#### Create Author Vector Response Example

```json
{
  "author_id": "A123456",
  "author_name": "Dr. Jane Smith",
  "embedding_dim": 384,
  "collection_name": "aegis_vectors",
  "success": true,
  "message": "Author vector created and stored successfully"
}
```

**When to use:**
- `/authors/embeddings`: When you have raw abstracts and want the service to compute embeddings
- `/authors/vector`: When you already have pre-computed embeddings from external models or processes

**Use Cases for `/authors/vector`:**
- Batch uploads from externally computed embeddings
- Integration with different embedding models
- Migration from other vector databases
- Custom embedding pipelines

**Note:** The vector dimension must match the collection schema (384 for default `all-MiniLM-L6-v2` model). The endpoint validates the dimension before insertion.


**Note:** If using a custom collection name (not the default), ensure the collection exists and has the correct schema before calling this endpoint.

## API Documentation

Once the service is running, visit:

- Swagger UI: `http://localhost:8002/docs`
- ReDoc: `http://localhost:8002/redoc`

## Testing

Run tests using pytest:

```bash
cd services/vector-db
poetry run pytest
```

Run tests with coverage:

```bash
poetry run pytest --cov=app --cov-report=html
```

## Development

### Project Structure

```
vector-db/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI application and endpoints
│   └── config.py        # Configuration management
├── tests/
│   └── test_sample.py   # Unit tests
├── Dockerfile           # Docker configuration
├── pyproject.toml       # Poetry dependencies
└── README.md            # This file
```

### Adding New Endpoints

1. Define Pydantic models for request/response in `app/main.py`
2. Implement the endpoint handler function
3. Add corresponding tests in `tests/`

### Milvus Integration

The service uses the `pymilvus` Python SDK to interact with Milvus. Key operations:

- **Connection Management**: Automatic connection on startup, reconnection on health checks
- **Collection Loading**: Collections are loaded on-demand for search operations
- **Search Parameters**: Configurable metric type (L2, IP, COSINE) and search parameters

## Troubleshooting

### Connection Issues

If you see "Failed to connect to Milvus" errors:

1. Verify Milvus is running: `docker ps | grep milvus`
2. Check connection settings in environment variables
3. Ensure network connectivity between service and Milvus

### Search Errors

If searches fail with "Collection not found":

1. Verify the collection exists: `GET /collections`
2. Check the collection name in your request
3. Ensure the collection has been loaded

## Related Services

- **example-service**: Template for creating new services
- Other AEGIS Scholar microservices

## Contributing

Follow the project's contribution guidelines and coding standards.

## License

[Project License]
