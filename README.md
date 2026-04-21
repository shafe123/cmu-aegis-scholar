# cmu-aegis-scholar

## Getting Started

### Prerequisites
- Docker and Docker Compose installed on your system
- VS Code with the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

### Running the Dev Container

1. Create the `dev_aegisnet` docker network
   ```bash
   docker network create dev_aegisnet
   ```

1. **Open the project in VS Code**
   ```bash
   code /path/to/cmu-aegis-scholar
   ```

1. **Reopen in Dev Container**
   - Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on macOS)
   - Select "Dev Containers: Reopen in Container"
   - Wait for the container to build and start

1. **Start Developing**
   - The dev container is now running with all dependencies pre-installed
   - You can run services, tests, and development commands directly in the integrated terminal

### Common Development Tasks

**Run tests:**
```bash
cd services/example-service
pytest
```

**Start a service:**
```bash
cd services/example-service
python -m app.main
```

**Install Python dependencies:**
```bash
pip install -e .
```


### Project Structure
- `services/` - Microservices and backend applications
- `libs/` - Shared libraries and packages
- `infra/` - Infrastructure and deployment configurations (Terraform)
- `k8s/` - Kubernetes manifests
- `dev/` - Development utilities and Docker Compose configuration
- `tests/` - Integration tests (cross-component)
- `frontend/` - React frontend application
- `jobs/` - One-time and scheduled data processing jobs

## Testing

This project has comprehensive unit and integration testing with an **80% coverage target**.

### Quick Start

**First-time setup:**
```bash
npm run setup
```

**Run all tests:**
```bash
npm run test:all
```

**Run specific components:**
```bash
npm run test:frontend      # Frontend tests
npm run test:services      # All service tests
npm run test:jobs          # All job tests
npm run test:integration   # Integration tests
```

### Test Organization

- **Unit Tests**: Located in `tests/` folder within each component
- **Integration Tests**: Located in root `/tests` folder
- **Coverage Target**: 80% across all components

### Documentation

- **[tests/README.md](tests/README.md)** - Testing guide and commands
- **[scripts/README.md](scripts/README.md)** - Test runner documentation

### Running Component Tests

**Frontend:**
```bash
cd frontend
npm test
```

**Python Services:**
```bash
cd services/aegis-scholar-api
poetry run pytest --cov=app
```

See [tests/README.md](tests/README.md) for complete details.

## Running the Example Service with Docker Compose

To start the example service using Docker Compose, run the following command from the root directory:

```sh
docker compose -f dev/docker-compose.yml up --build -d example-service
```

This will build and start the example service defined in `dev/docker-compose.yml`.

## Switching Dev Data Sets

The dev Compose stack defaults to the small linked test subset in `tests/dtic_test_subset`. The simplest way to switch between that and the full compressed DTIC export is to keep two env files and pick one with `--env-file`.

```sh
cp dev/.env.example.subset dev/.env.subset
cp dev/.env.example.full dev/.env.full
```

The checked-in templates are:

```text
dev/.env.example.subset
dev/.env.example.full
```

Use `dev/.env.subset` for the small linked dataset:

```dotenv
DTIC_DATASET_DIR=../tests/dtic_test_subset
IDENTITY_AUTH_JSONL_FILE=dtic_authors_50.jsonl.gz
IDENTITY_ORG_JSONL_FILE=dtic_orgs_50.jsonl.gz
```

Use `dev/.env.full` for the full compressed dataset:

```dotenv
DTIC_DATASET_DIR=../data/dtic_compressed
IDENTITY_AUTH_JSONL_FILE=dtic_authors_001.jsonl.gz
IDENTITY_ORG_JSONL_FILE=dtic_orgs_001.jsonl.gz
```

Then start whichever version you want:

```sh
docker compose --env-file dev/.env.subset -f dev/docker-compose.yml up --build
docker compose --env-file dev/.env.full -f dev/docker-compose.yml up --build
```