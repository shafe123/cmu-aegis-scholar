# Testing Guide

## Quick Start

**First-time setup:**
```bash
npm run setup
```

**Run all tests:**
```bash
npm run test:all
```

**Run by component:**
```bash
npm run test:frontend      # React frontend
npm run test:services      # Python services
npm run test:jobs          # Data loading jobs
npm run test:integration   # Cross-component tests
```

## Test Structure

```
/tests/                     # Integration tests (this folder)
/frontend/src/tests/        # Frontend unit tests
/services/*/tests/          # Service unit tests
/jobs/*/tests/              # Job unit tests
/libs/*/tests/              # Library unit tests
```

## Coverage Target

**80%** across all components. Tests fail if coverage drops below threshold.

## Frameworks

| Component   | Framework                      | Commands                                  |
| ----------- | ------------------------------ | ----------------------------------------- |
| Frontend    | Vitest + React Testing Library | `cd frontend && npm test`                 |
| Services    | pytest + pytest-asyncio        | `cd services/[name] && poetry run pytest` |
| Jobs        | pytest                         | `cd jobs/[name] && poetry run pytest`     |
| Integration | pytest + httpx                 | `cd tests && poetry run pytest`           |

## Setup

**First time:**
```bash
# Frontend
cd frontend && npm install

# Python components (example)
cd services/aegis-scholar-api && poetry install
cd ../graph-db && poetry install
cd ../vector-db && poetry install

# Integration tests
cd tests && poetry install
```

## Integration Tests (This Folder)

Tests interactions between multiple components:
- **`test_api_integration.py`** - API ↔ Database interactions
- **`test_data_loading.py`** - ETL pipeline validation  
- **`test_end_to_end.py`** - Complete user workflows

**Run integration tests:**
```bash
cd tests
poetry run pytest                    # All tests
poetry run pytest -m integration     # Integration-marked only
poetry run pytest -m "not slow"      # Skip slow tests

# Run specific test file
poetry run pytest test_api_integration.py

# Run tests with specific marker
poetry run pytest -m integration

# Skip slow tests
poetry run pytest -m "not slow"

# Skip Docker-dependent tests
poetry run pytest -m "not requires_docker"

# Verbose output
poetry run pytest -v

# Stop on first failure
poetry run pytest -x
```

### Running with Services

```bash
# Option 1: Using docker-compose
cd dev
docker-compose up -d

# Run tests
cd ../tests
poetry run pytest

# Option 2: Using testcontainers (automatic)
poetry run pytest -m requires_docker
```

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── pyproject.toml           # Dependencies and pytest config
├── test_api_integration.py  # API integration tests
├── test_data_loading.py     # Data loading tests
├── test_end_to_end.py       # E2E workflow tests
└── README.md               # This file
```

## Writing Integration Tests

### Basic Integration Test

```python
import pytest

@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_to_database(http_client, base_api_url):
    """Test API interaction with database."""
    response = await http_client.get(f"{base_api_url}/api/v1/health")
    
    assert response.status_code == 200
    assert response.json()["database"] == "connected"
```

### Using Test Fixtures

```python
@pytest.mark.integration
async def test_with_sample_data(sample_integration_data):
    """Test using pre-defined sample data."""
    authors = sample_integration_data["authors"]
    assert len(authors) > 0
```

### Testing Complete Workflows

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_workflow(http_client, base_api_url):
    """Test complete search workflow."""
    # 1. Search
    search_response = await http_client.post(
        f"{base_api_url}/api/v1/search",
        json={"query": "machine learning"}
    )
    assert search_response.status_code == 200
    results = search_response.json()["results"]
    
    # 2. Get details for first result
    first_id = results[0]["id"]
    detail_response = await http_client.get(
        f"{base_api_url}/api/v1/works/{first_id}"
    )
    assert detail_response.status_code == 200
```

### Using Testcontainers

```python
import pytest
from testcontainers.postgres import PostgresContainer

@pytest.mark.requires_docker
def test_with_real_database():
    """Test with a real database using testcontainers."""
    with PostgresContainer() as postgres:
        connection_url = postgres.get_connection_url()
        # Use connection_url to test with real database
```

## Test Markers

Use markers to categorize tests:

```python
@pytest.mark.integration     # Integration test
@pytest.mark.slow           # Slow running test (>30 seconds)
@pytest.mark.requires_docker # Requires Docker to run
```

Run tests by marker:
```bash
pytest -m integration        # Only integration tests
pytest -m "not slow"        # Skip slow tests
pytest -m "integration and not requires_docker"  # Combine markers
```

## Available Fixtures

### Session Fixtures (Shared Across All Tests)
- `neo4j_container`: Neo4j testcontainer (Docker)
- `graph_db_container`: Graph DB service testcontainer (Docker)
- `neo4j_driver`: Direct Neo4j database connection
- `ensure_test_data`: Auto-loads DTIC test data into Neo4j (autouse)
- `base_api_url`: Main API URL (default: http://localhost:8000)
- `vector_db_url`: Vector DB service URL
- `graph_db_url`: Graph DB service URL

### Function Fixtures (Recreated Per Test)
- `http_client`: Async HTTP client (httpx)
- `app_client`: FastAPI test client for aegis_scholar_api
- `sample_integration_data`: Sample data for testing
- `sample_search_query`: Sample search parameters

### Utility Functions
- `get_free_port()`: Find available port for test services
- `load_gz_jsonl()`: Load gzipped JSONL data into Neo4j

See `conftest.py` for complete list and implementation.

## Configuration

### Environment Variables

Set these for integration tests:
```bash
export AEGIS_API_URL=http://localhost:8000
export VECTOR_DB_URL=http://localhost:8001
export GRAPH_DB_URL=http://localhost:8002
```

### pytest Configuration

In `pyproject.toml`:
```toml
[tool.pytest.ini_options]
markers = [
    "integration: Integration tests",
    "slow: Slow running tests",
    "requires_docker: Tests that require Docker",
]
```

## Best Practices

1. **Isolation**: Each test should be independent
2. **Cleanup**: Clean up test data after tests
3. **Realistic Data**: Use realistic test data
4. **Error Cases**: Test both success and failure scenarios
5. **Documentation**: Document what each test verifies

### Example Best Practice

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_example(http_client):
    """Test description explaining what is verified."""
    # Arrange: Set up test data
    test_data = {"query": "test"}
    
    # Act: Perform the action
    response = await http_client.post("/api/search", json=test_data)
    
    # Assert: Verify the results
    assert response.status_code == 200
    assert "results" in response.json()
    
    # Cleanup: Clean up if needed
    # (use fixtures for automatic cleanup)
```

## CI/CD Integration

Integration tests run in CI/CD pipeline:

```yaml
# Example GitHub Actions
- name: Start services
  run: docker-compose up -d
  
- name: Wait for services
  run: ./scripts/wait-for-services.sh
  
- name: Run integration tests
  run: |
    cd tests
    poetry run pytest -m integration
```

## Debugging Integration Tests

### Check Service Health

```bash
# Check if services are running
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
```

### View Service Logs

```bash
# Docker logs
docker-compose logs -f aegis-api
docker-compose logs -f vector-db
docker-compose logs -f graph-db
```

### Run Single Test with Debug Output

```bash
poetry run pytest test_api_integration.py::test_name -v -s
```

### Use Python Debugger

```python
@pytest.mark.integration
async def test_debug_example():
    import pdb; pdb.set_trace()  # Debugger breakpoint
    # Test code
```

## Performance Considerations

Integration tests are slower than unit tests:
- Use `@pytest.mark.slow` for tests >30 seconds
- Run fast tests frequently, slow tests less often
- Consider parallel test execution:

```bash
# Install pytest-xdist
poetry add --group dev pytest-xdist

# Run tests in parallel
poetry run pytest -n auto
```

## Troubleshooting

### Services Not Available
```bash
# Start services
cd dev && docker-compose up -d

# Verify services are healthy
docker-compose ps
```

### Connection Timeouts
Increase timeout in fixtures or use retries:
```python
@pytest.fixture
async def http_client():
    timeout = httpx.Timeout(30.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        yield client
```

### Docker Issues
```bash
# Clean up Docker resources
docker-compose down -v
docker system prune -f

# Restart services
docker-compose up -d
```

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [httpx documentation](https://www.python-httpx.org/)
- [testcontainers documentation](https://testcontainers-python.readthedocs.io/)
- [FastAPI testing guide](https://fastapi.tiangolo.com/tutorial/testing/)
