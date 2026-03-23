# Graph Loader Job

Initializes the Neo4j graph database by processing DTIC scholarly data.

## Overview

Unlike the Vector Loader (which focuses on abstracts and meaning), the Graph Loader maps the **structural relationships** of the research ecosystem:

1. **Nodes**: Creates Authors, Organizations, Topics, and Works.
2. **Relationships**: Links Authors to Works (`AUTHORED`), Works to Topics (`COVERS`), and Authors to Organizations (`AFFILIATED_WITH`).

## Ingestion Order

To prevent "orphaned" relationships, the loader processes data in this order:
1. `authors` nodes
2. `orgs` nodes
3. `topics` nodes
4. `works` nodes (this creates the Work nodes AND all connecting edges)

## Usage

### Local Development (Poetry)
```bash
cd jobs/graph-loader
poetry install
poetry run python -m app.loader