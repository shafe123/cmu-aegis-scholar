# Graph Loader Job

The Graph Loader is an ETL utility that initializes the Neo4j database by processing compressed DTIC scholarly data.

## Overview

Unlike the Vector Loader (focused on semantic meaning), the Graph Loader establishes the **structural connective tissue** of the platform:

1. **Nodes**: Populates Authors, Organizations, Topics, and Works.
2. **Relationships**: Establishes `AUTHORED`, `COVERS_TOPIC`, and `AFFILIATED_WITH` edges.
3. **Idempotency**: Includes "Skip-if-Loaded" logic that queries the API `/stats` endpoint to prevent redundant ingestion if the database is already populated.

## Ingestion Order

To maintain referential integrity and prevent orphaned relationships, data is loaded in this sequence:
1. `authors`
2. `orgs`
3. `topics`
4. `works` (Creates the Work nodes AND all connecting edges simultaneously)

## Development & Quality Gate

This job maintains a **10/10 Pylint score** and **91% test coverage**.

### Usage (Local Development)
Ensure you are in the `jobs/graph-loader` directory:
```bash
poetry install --with dev

# Run the loader (points to http://localhost:8003 by default)
PYTHONPATH=. poetry run python -m app.loader