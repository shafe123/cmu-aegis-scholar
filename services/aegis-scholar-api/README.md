# Aegis Scholar API

The Aegis Scholar API is the primary interface between external entities and the Aegis Scholar research discovery system. This read-only API provides search capabilities across research authors, organizations, topics, and published works.

## Features

- **RESTful API** built with FastAPI
- **Search Endpoints** for authors, organizations, topics, and works
- **Pydantic Models** for type-safe request/response handling
- **Docker Support** for easy deployment
- **OpenAPI Documentation** automatically generated at `/docs`

## API Endpoints

### Core Search Endpoints

- `GET /search` - Search for authors (alias for `/search/authors`)
- `GET /search/authors` - Search for research authors
- `GET /search/orgs` - Search for organizations (institutions, funders, publishers)
- `GET /search/topics` - Search for research topics and subject areas
- `GET /search/works` - Search for research works and publications

### Detail Endpoints

- `GET /search/authors/{author_id}` - Get author details by ID
- `GET /search/orgs/{org_id}` - Get organization details by ID
- `GET /search/topics/{topic_id}` - Get topic details by ID
- `GET /search/works/{work_id}` - Get work details by ID

### System Endpoints

- `GET /` - API information and available endpoints
- `GET /health` - Health check endpoint

## Query Parameters

### Common Parameters

All search endpoints support:
- `q` (required) - Search query string
- `limit` (optional, default: 10) - Maximum number of results (1-100)
- `offset` (optional, default: 0) - Number of results to skip for pagination

### Endpoint-Specific Parameters

#### `/search/authors`
- `sort_by` - Sort field (e.g., 'h_index', 'citation_count')
- `order` - Sort order ('asc' or 'desc')

#### `/search/orgs`
- `org_type` - Filter by type ('institution', 'funder', 'publisher')
- `country` - Filter by country code (e.g., 'US', 'GB')

#### `/search/topics`
- `field` - Filter by research field
- `domain` - Filter by domain (e.g., 'Physical Sciences')

#### `/search/works`
- `year_from` - Filter by publication year (from)
- `year_to` - Filter by publication year (to)
- `min_citations` - Minimum citation count

## Installation

### Using Poetry (Development)

```bash
# Install dependencies
poetry install

# Run the development server
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Using Docker

```bash
# Build the image
docker build -t aegis-scholar-api:latest .

# Run the container
docker run -p 8000:8000 aegis-scholar-api:latest
```

### Using Docker Compose

```bash
# From the project root, start all services including dependencies
docker-compose -f dev/docker-compose.yml up --build aegis-scholar-api

# Or start just aegis-scholar-api (dependencies will start automatically)
docker-compose -f dev/docker-compose.yml up -d aegis-scholar-api

# View logs
docker-compose -f dev/docker-compose.yml logs -f aegis-scholar-api

# Stop the service
docker-compose -f dev/docker-compose.yml down
```

The API will be available at http://localhost:8000

## Development

### Project Structure

```
aegis-scholar-api/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI application and routes
│   ├── schemas.py       # Pydantic data models
│   └── config.py        # Application configuration
├── tests/
│   └── __init__.py
├── .env.example         # Environment variables template
├── .gitignore
├── Dockerfile
├── pyproject.toml       # Poetry dependencies
└── README.md
```

### Running Tests

```bash
poetry run pytest
```

### Code Formatting

```bash
# Format code with Black
poetry run black .

# Lint with Ruff
poetry run ruff check .
```

## API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/openapi.json

## Example Requests

### Search for Authors

```bash
curl "http://localhost:8000/search/authors?q=machine%20learning&limit=5"
```

### Search for Organizations

```bash
curl "http://localhost:8000/search/orgs?q=carnegie%20mellon&org_type=institution"
```

### Search for Topics

```bash
curl "http://localhost:8000/search/topics?q=artificial%20intelligence&domain=Physical%20Sciences"
```

### Search for Works

```bash
curl "http://localhost:8000/search/works?q=neural%20networks&year_from=2020&min_citations=10"
```

## Implementation Status

**Current Status**: Scaffolding Complete ✅

The API structure is complete with:
- ✅ All endpoint routes defined
- ✅ Pydantic models matching database schema
- ✅ Request validation and query parameters
- ✅ Docker configuration
- ✅ OpenAPI documentation

**Next Steps**: Backend Integration 🚧

The following components need to be implemented:
- [ ] Database connection (Azure Cosmos DB, PostgreSQL, or other)
- [ ] Vector search integration (based on `steve/search_aegis.py`)
- [ ] Actual search logic for each endpoint
- [ ] Caching layer (Redis or similar)
- [ ] Authentication/authorization (if required)
- [ ] Rate limiting
- [ ] Monitoring and logging

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

See `.env.example` for all available configuration options including:
- API configuration (host, port, logging)
- Vector DB service URL
- Database connection strings
- Cache configuration
- CORS settings

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests and formatting checks
4. Submit a pull request

## License

[Your License Here]

## Contact

For questions or support, contact the Aegis Scholar team.
