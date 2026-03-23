# Aegis Scholar Graph API

This service provides a RESTful interface to the **Neo4j** graph database. It is responsible for mapping the complex relationships between authors, organizations, topics, and works.

## Key Functions

- **Ingestion**: Endpoints to `MERGE` nodes and relationships (used by the Graph Loader).
- **Network Analysis**: High-performance Cypher queries for finding collaborators and institutional links.
- **Visualization**: Specialized endpoints that return JSON structured for frontend graph libraries like `vis-network`.

## Endpoints

- `GET /health`: Health check and Neo4j connection status.
- `POST /authors`: Upsert an author node.
- `POST /relationships/authored`: Link an author to a work.
- `GET /authors/{id}/collaborators`: Retrieve 2-hop research networks.
- `GET /viz/author-network/{id}`: Graph data formatted for frontend visualization.

## Development

To run locally with Poetry:
1. `poetry install`
2. `poetry run uvicorn app.main:app --port 8003 --reload`