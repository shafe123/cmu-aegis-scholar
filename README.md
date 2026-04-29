# CMU Aegis Scholar

A defense research intelligence platform for discovering and analyzing DTIC (Defense Technical Information Center) researchers. Users search by name, affiliation, or research interest; the system returns ranked results using a hybrid relevance formula combining semantic similarity, citation impact, and publication recency — visualized as an interactive author–work–organization network.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Usage](#usage)
- [Running Tests](#running-tests)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [Known Limitations](#known-limitations)
- [License](#license)

---

## Architecture Overview

Aegis Scholar is a Docker Compose monorepo of five microservices communicating over an internal bridge network (`aegisnet`).

```
Browser (React/Vite or Nginx)
        │
        ▼
aegis-scholar-api (:8000)   ← primary gateway (read-only for end users)
        │
        ├──▶ vector-db (:8002)          FastAPI → Milvus standalone
        │         └── vector-loader     one-shot job: DTIC → embeddings → Milvus
        │
        ├──▶ graph-db (:8003)           FastAPI → Neo4j 5.12
        │         └── graph-loader      one-shot job: DTIC → graph nodes → Neo4j
        │
        └──▶ identity (:8005)           FastAPI → OpenLDAP
```

### Services

| Service | Port | Responsibility |
|---|---|---|
| `aegis-scholar-api` | 8000 | Orchestrates search; computes hybrid relevance scores; proxies identity lookups |
| `vector-db` | 8002 | Text-to-embedding + Milvus similarity search |
| `graph-db` | 8003 | Neo4j graph operations (authors, works, orgs, topics) |
| `identity` | 8005 | LDAP directory sync and fuzzy name lookup |
| `frontend` | 5173 (dev) / 80+443 (prod) | React/Vite app with interactive vis-network graph, served by Nginx in production |

### Relevance Scoring

Author search results are ranked by a composite formula:

```
score(x, y, t) = ⅓·(1−x) + ⅓·σ(0.005·(y−100)) + ⅓·½·(1−tanh(t−2))
```

- **x** — vector L2 distance converted to a 0–1 relevance score
- **y** — total citation count for the author
- **t** — decades since most recent publication, capped at 4

### Data Model

Four entity types sourced from DTIC, stored across both databases:

| Entity | Neo4j label | Milvus collection |
|---|---|---|
| Author | `Author` | `aegis_vectors` (averaged abstract embedding) |
| Work | `Work` | — |
| Organization | `Organization` | — |
| Topic | `Topic` | — |

Graph relationships: `AUTHORED`, `AFFILIATED_WITH`, `COVERS_TOPIC`

### Repository Layout

```
services/
  aegis_scholar_api/   Main API gateway
  vector-db/           Milvus wrapper service
  graph-db/            Neo4j wrapper service
  identity/            LDAP sync service
jobs/
  vector-loader/       One-shot DTIC → Milvus ingest
  graph-loader/        One-shot DTIC → Neo4j ingest
frontend/              React/Vite application
libs/                  Shared Python libraries
tests/                 Cross-service integration test suite
infra/                 Terraform modules
k8s/                   Kubernetes manifests
dev/                   Docker Compose stack and env templates
data/                  Schema definitions and sample data
utils/                 DTIC scraping and data preparation utilities
```

---

## Prerequisites

- **Docker** ≥ 24 and **Docker Compose** v2
- **Python 3.12** (for the root test runner and utility scripts)
- **Node.js** ≥ 18 (for `npm run setup` and frontend-only development)
- **VS Code** with the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) *(recommended for local development)*
- At least **8 GB of free RAM** — Milvus standalone and Neo4j are memory-intensive

---

## Getting Started

### 1. Clone and create the shared Docker network

```bash
git clone https://github.com/shafe123/cmu-aegis-scholar.git
cd cmu-aegis-scholar
docker network create dev_aegisnet
```

### 2. Prepare your environment file

Copy one of the two dataset templates depending on how much data you want:

```bash
# Small subset (50 entities per type) — fastest for local development
cp dev/.env.example.subset dev/.env

# Full compressed DTIC export
cp dev/.env.example.full dev/.env
```

Edit `dev/.env` and set the required secrets before continuing:

```dotenv
NEO4J_PASSWORD=<choose a strong password>
LDAP_ADMIN_PASSWORD=<choose a strong password>
SEAWEEDFS_ACCESS_KEY=minioadmin
SEAWEEDFS_SECRET_KEY=minioadmin
```

### 3. Start the stack

```bash
docker compose --env-file dev/.env -f dev/docker-compose.yml up --build
```

The `vector-loader` and `graph-loader` jobs run once automatically on first start, populate their respective databases, and exit. The five long-running services stay up.

### 4. Verify the stack is healthy

```bash
curl http://localhost:8000/health   # aegis-scholar-api
curl http://localhost:8002/health   # vector-db
curl http://localhost:8003/health   # graph-db
curl http://localhost:8005/health   # identity
```

Open the frontend at **http://localhost:5173**.

### Dev Container (alternative)

1. Open the project folder in VS Code
2. Press `Ctrl+Shift+P` → **Dev Containers: Reopen in Container**
3. Wait for the container to build, then run the compose stack from the integrated terminal

---

## Configuration

All runtime configuration is supplied through environment variables. Secrets must never be committed to source control.

| Variable | Service(s) | Default | Description |
|---|---|---|---|
| `NEO4J_PASSWORD` | `neo4j`, `graph-db` | *(required)* | Neo4j admin password |
| `LDAP_ADMIN_PASSWORD` | `ldap-server`, `identity` | *(required)* | OpenLDAP admin password |
| `SEAWEEDFS_ACCESS_KEY` | `milvus-seaweedfs` | `minioadmin` | S3-compatible object store key |
| `SEAWEEDFS_SECRET_KEY` | `milvus-seaweedfs` | `minioadmin` | S3-compatible object store secret |
| `DTIC_DATASET_DIR` | `vector-loader`, `graph-loader`, `identity` | `../tests/dtic_test_subset` | Host path to JSONL dataset directory |
| `IDENTITY_AUTH_JSONL_FILE` | `identity` | `dtic_authors_50.jsonl.gz` | Author data filename within `DTIC_DATASET_DIR` |
| `IDENTITY_ORG_JSONL_FILE` | `identity` | `dtic_orgs_50.jsonl.gz` | Organization data filename |
| `VECTOR_DB_URL` | `aegis-scholar-api` | `http://vector-db:8002` | Internal vector-db address |
| `GRAPH_DB_URL` | `aegis-scholar-api` | `http://graph-db:8003` | Internal graph-db address |
| `API_PORT` | `aegis-scholar-api` | `8000` | Listening port |
| `LOG_LEVEL` | all Python services | `INFO` | Python logging level |
| `EMBEDDING_MODEL` | `vector-loader` | `sentence-transformers/all-MiniLM-L6-v2` | Sentence embedding model |
| `BATCH_SIZE` | `vector-loader` | `100` | Embedding batch size |

Service-specific `.env.example` files live alongside each service's `pyproject.toml`.

### Switching datasets at runtime

```bash
# Small test subset (default)
docker compose --env-file dev/.env.subset -f dev/docker-compose.yml up --build

# Full compressed DTIC export
docker compose --env-file dev/.env.full -f dev/docker-compose.yml up --build
```

---

## Usage

### Author search

```bash
# Search by name or research area
curl "http://localhost:8000/search/authors?q=network+security&limit=10"

# Sort by citation count descending
curl "http://localhost:8000/search/authors?q=machine+learning&sort_by=citation_count&order=desc"
```

Response fields per result: `id`, `name`, `citation_count`, `works_count`, `relevance_score`

### Author detail and network visualization

```bash
# Fetch author metadata from the graph database
curl http://localhost:8000/search/authors/<author_id>

# Fetch graph visualization data (nodes + edges for the frontend)
curl http://localhost:8000/viz/author-network/<author_id>
```

### Identity lookup

```bash
# Fuzzy name lookup proxied through the main API
curl "http://localhost:8000/identity/lookup?name=John+Smith"

# Or directly against the identity service
curl "http://localhost:8005/lookup?name=John+Smith"
```

Returns an exact match (if found) plus fuzzy-scored suggestions from the LDAP directory.

### Interactive graph UI

Open **http://localhost:5173**, enter a search query, select a result, and explore the author–work–co-author–organization network. Use the **Export JSON** button to download the visible subgraph.

### API documentation (Swagger / ReDoc)

| Service | Swagger | ReDoc |
|---|---|---|
| aegis-scholar-api | http://localhost:8000/docs | http://localhost:8000/redoc |
| vector-db | http://localhost:8002/docs | http://localhost:8002/redoc |
| graph-db | http://localhost:8003/docs | http://localhost:8003/redoc |

---

## Running Tests

### One-liner (all components)

```bash
npm run setup       # first run only: installs per-component dependencies
npm run test:all    # runs every test suite
```

Requires Python 3.12 on PATH as `py -3.12` (Windows) or `python3.12` (Linux/macOS).

### Component-level shortcuts

```bash
npm run test:frontend     # Vitest (React components)
npm run test:services     # pytest for all backend services
npm run test:jobs         # pytest for vector-loader and graph-loader
npm run test:libs         # pytest for shared libraries
npm run test:integration  # full integration test suite (requires Docker)
```

### Running a single service manually

```bash
# Python service (Poetry)
cd services/graph-db
poetry install
poetry run pytest --cov=app --cov-report=term-missing

# Frontend
cd frontend
npm install
npm test -- --run
```

### Integration tests (testcontainers)

The `tests/` directory contains 27 integration tests using [testcontainers-python](https://github.com/testcontainers/testcontainers-python) that spin up real containers. See [`tests/TEST_MAP.md`](tests/TEST_MAP.md) for a full breakdown.

```bash
cd tests
poetry install
poetry run pytest -v
```

### Code quality gates (required before every PR)

```bash
ruff check .                          # linting
ruff format --check .                 # formatting
pylint app --fail-under=9.0           # style score
mypy app/ --ignore-missing-imports    # type checking
bandit -r app/ -ll                    # static security analysis
```

### Coverage target

All Python services enforce **80% line coverage** via `pytest-cov`. CI fails builds that drop below this threshold.

---

## Deployment

### CI/CD pipeline

GitHub Actions runs on every pull request and push to `main`:

| Job | What it checks |
|---|---|
| `lint-python` | ruff lint + format, pylint ≥ 9.0 (all services) |
| `lint-frontend` | ESLint |
| `test-frontend` | Vitest build + unit tests |
| `security-scan` | bandit SAST + mypy type checking (all services) |
| `test-python` | pytest with 80% coverage (all services) |
| `build-images` | Docker Buildx build for all images |
| `test-integration` | 27 testcontainers integration tests (runs after all above pass) |
| `docker-scout` | Critical/high CVE scan on PRs (requires `DOCKERHUB_USERNAME` + `DOCKERHUB_TOKEN` secrets) |

### Production: HTTPS via Nginx (domain: aegisscholar.org)

The frontend container uses Nginx in production and supports TLS. Ports 80 and 443 are published on the host.

1. Add an `A` record for `aegisscholar.org` pointing to your server's public IP.
2. Obtain TLS certificates (e.g., via Certbot) and place them at:
   - `dev/certs/fullchain.pem`
   - `dev/certs/privkey.pem`
3. Start the stack:

```bash
docker compose --env-file dev/.env -f dev/docker-compose.yml up --build
```

- When cert files are present, Nginx serves HTTPS on port 443.
- When cert files are absent, Nginx falls back to HTTP on port 80.

The browser sends all API calls to `/api/...` on the same origin; Nginx proxies `/api` to `aegis-scholar-api:8000` inside the Docker network. Do not use `localhost` in frontend API calls when running behind Nginx.

> **Never commit TLS private keys.** The repository ignores `dev/certs/*` except `.gitkeep`.

### Switching the frontend to production mode

Follow the three `# [PRODUCTION SWITCH]` comments in `dev/docker-compose.yml` to change the Docker build target and port mapping from Vite dev mode to the Nginx production image.

### Kubernetes

Kubernetes manifests are in `k8s/`. See [`k8s/README.md`](k8s/README.md) for cluster setup and rollout steps.

### Infrastructure (Terraform)

Cloud infrastructure is defined in `infra/` using Terraform modules. `infra/vector-db/` provisions the managed vector database; `infra/example-service/` is a template for new modules. See [`infra/README.md`](infra/README.md) for provider setup and `terraform apply` steps.

---

## Contributing

### Branch conventions

- `main` — production-ready; direct pushes are blocked
- Feature branches: `<issue-number>-short-description` (e.g., `42-add-topic-search`)
- Hotfix branches: `hotfix/<description>`

### Workflow

1. Open an issue or claim an existing one
2. Branch off `main`
3. Write code and tests; keep per-service coverage at or above 80%
4. Run all quality gates locally before pushing
5. Open a pull request using the [PR template](.github/pull_request_template.md)
6. Obtain at least one approval before merging

### PR checklist highlights

- `ruff`, `mypy`, and `bandit` pass with no errors
- `pylint` score ≥ 9.0 for each affected service
- New functionality is covered by tests
- Docker images build cleanly
- Any new environment variables are documented here and in the relevant `.env.example` file
- No hardcoded secrets

---

## Known Limitations

- **Organization, topic, and work search endpoints are stubs.** `GET /search/orgs`, `/search/topics`, `/search/works`, and their `/{id}` detail variants all return HTTP 501. Only author search is fully wired.
- **Identity sync is not automatic on startup.** The LDAP directory is populated by calling `POST http://localhost:8005/sync-file` after the stack is running.
- **Milvus cold-start is slow.** The `vector-db` service has a 120-second start period while it connects to Milvus and preloads the default embedding model. Reduce `BATCH_SIZE` if the loader OOMs on memory-constrained hardware.
- **Unit test coverage for `aegis-scholar-api` is in progress.** CI currently uses a temporary lower threshold for that service; it will be raised to 80% when the unit test suite is complete.
- **No authentication on internal service APIs.** The `vector-db`, `graph-db`, and `identity` services rely on the Docker bridge network for isolation. Do not expose ports 8002, 8003, or 8005 to the public internet.

---

## License

MIT — see [LICENSE](LICENSE) for the full text.