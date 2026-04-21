# Aegis Scholar Graph API

This service provides a RESTful interface to the **Neo4j** graph database. It maps complex relationships between authors, organizations, topics, and works using high-performance Cypher queries.

## Key Functions

- **Ingestion**: Idempotent endpoints using `MERGE` logic to prevent duplicate data for Authors, Works, Organizations, and Topics.
- **Network Analysis**: Multi-hop discovery of collaborators and institutional research clusters.
- **Visualization**: Specialized `/viz` endpoints returning JSON formatted with metadata (years, citations) for `vis-network` interactive filtering.
- **Security**: IL4-compliant credential handling via memory-mounted Docker Secrets.

## Endpoints

- `GET /`: Service metadata and status.
- `GET /health`: Connectivity check for the Neo4j backend with error logging.
- `GET /stats`: Current node counts (used by data loaders to prevent redundant ingestion).
- `POST /authors`: Upsert an author node with metrics (h-index, works count).
- `POST /orgs`: Upsert an organization node (type, country).
- `POST /topics`: Upsert a research topic node (field, domain).
- `POST /works`: Upsert a research work node (title, year, citations).
- `POST /relationships/authored`: Link an author to a work.
- `POST /relationships/affiliated`: Link an author to an organization.
- `POST /relationships/covers`: Link a work to a topic.
- `GET /authors/{id}/collaborators`: Retrieve professional research networks.
- `GET /viz/author-network/{id}`: Graph data formatted for frontend visualization.

## Security

This service does not accept plaintext passwords via environment variables. In production/Docker, it expects a secret named `neo4j_password` to be mounted at `/run/secrets/neo4j_password`.

## Development & Quality Gate

This service maintains a **10/10 Pylint score** and **>90% test coverage**.

**Local Setup:**
1. `poetry install --with dev`
2. `poetry run uvicorn app.main:app --port 8003 --reload`

**Quality Checks:**
- **Linting**: `poetry run ruff check .`
- **Formatting**: `poetry run ruff format .`
- **Type Checking**: `poetry run pylint app/`
- **Testing**: `poetry run pytest --cov=app`