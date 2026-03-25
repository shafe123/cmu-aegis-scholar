# Jobs Testing Guide

This directory contains one-time and scheduled jobs for data processing and loading.

## Jobs

- **vector-loader**: Loads DTIC data into Milvus vector database
- **graph-loader**: Loads DTIC data and relationships into Neo4j

## Running Tests

### Individual Job

```bash
# Navigate to job directory
cd jobs/vector-loader

# Install dependencies (first time only)
poetry install

# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=app

# Run specific test file
poetry run pytest tests/test_loader.py

# Run with verbose output
poetry run pytest -v
```

### All Jobs

From the repository root:
```bash
# Run tests for all jobs
python scripts/test_all_jobs.py
```

## Test Structure

Each job follows this structure:
```
job-name/
├── app/                 # Job application code
├── tests/
│   ├── __init__.py
│   ├── conftest.py     # Shared fixtures
│   ├── test_loader.py  # Main job logic tests
│   └── test_utils.py   # Utility function tests
└── pyproject.toml      # Dependencies and test config
```

## Coverage Requirements

- **Target**: 80% code coverage
- **Enforcement**: Tests will fail if coverage drops below 80%
- **View Reports**: After running with `--cov`, open `htmlcov/index.html`

## Writing Tests for Jobs

### Testing Data Loading

```python
import pytest
from unittest.mock import Mock, AsyncMock

@pytest.mark.asyncio
async def test_load_data_batch(mock_database_client):
    """Test loading a batch of data."""
    loader = DataLoader(mock_database_client)
    sample_data = [{"id": "1", "name": "Test"}]
    
    result = await loader.load_batch(sample_data)
    
    assert result.success is True
    assert result.records_loaded == 1
```

### Testing HTTP Clients

```python
@pytest.mark.asyncio
async def test_fetch_dtic_data(mock_http_client):
    """Test fetching data from DTIC API."""
    mock_http_client.get.return_value = {"data": [...]}
    
    fetcher = DTICFetcher(mock_http_client)
    result = await fetcher.fetch_authors()
    
    assert len(result) > 0
    assert mock_http_client.get.called
```

### Testing Data Transformation

```python
def test_transform_author_data():
    """Test transformation of author data."""
    raw_data = {"display_name": "John Doe", "works_count": 42}
    
    transformed = transform_author(raw_data)
    
    assert "name" in transformed
    assert transformed["name"] == "John Doe"
    assert transformed["works_count"] == 42
```

### Testing Error Handling

```python
@pytest.mark.asyncio
async def test_handle_api_failure(mock_http_client):
    """Test handling of API failures."""
    mock_http_client.get.side_effect = Exception("API Error")
    
    fetcher = DTICFetcher(mock_http_client)
    
    with pytest.raises(Exception):
        await fetcher.fetch_authors()
```

### Testing Retry Logic

```python
@pytest.mark.asyncio
async def test_retry_on_failure(mock_http_client):
    """Test retry logic on temporary failures."""
    # Fail first two times, succeed on third
    mock_http_client.get.side_effect = [
        Exception("Timeout"),
        Exception("Timeout"),
        {"data": "success"}
    ]
    
    fetcher = DTICFetcher(mock_http_client, max_retries=3)
    result = await fetcher.fetch_with_retry("/endpoint")
    
    assert result == {"data": "success"}
    assert mock_http_client.get.call_count == 3
```

## Best Practices for Job Testing

1. **Mock External Services**: Never make real API calls or database connections
2. **Test Batch Processing**: Verify jobs handle batches correctly
3. **Test Error Recovery**: Jobs should handle failures gracefully
4. **Test Idempotency**: Jobs should be safely re-runnable
5. **Test Progress Tracking**: Verify progress is reported correctly

## Common Fixtures

Available in `conftest.py`:

- `mock_http_client`: Mock HTTP client for API calls
- `mock_neo4j_client`: Mock Neo4j client
- `mock_milvus_client`: Mock Milvus client
- `sample_dtic_author`: Sample author data
- `sample_dtic_work`: Sample work data
- `sample_batch_data`: Sample batch of records

## Testing Async Code

All async functions must be marked with `@pytest.mark.asyncio`:

```python
@pytest.mark.asyncio
async def test_async_function():
    """Test an async function."""
    result = await async_operation()
    assert result is not None
```

## Configuration

Test configuration is in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = [
    "--cov=app",
    "--cov-report=html",
    "--cov-report=term-missing",
    "--cov-fail-under=80",
]
```

## Running Jobs Locally

Before running tests, you may want to test the job manually:

```bash
# Set environment variables
cp .env.example .env
# Edit .env with appropriate values

# Run the job
poetry run python -m app.main
```

## CI/CD Integration

Jobs are tested in CI/CD pipeline:
- Tests run on every PR
- Coverage reports generated
- Failed tests block deployment

## Troubleshooting

### Import Errors
```bash
poetry install
poetry run pytest
```

### Async Test Failures
Ensure `pytest-asyncio` is installed:
```bash
poetry add --group dev pytest-asyncio
```

### Coverage Issues
```bash
poetry add --group dev pytest-cov
poetry run pytest --cov=app --cov-report=term-missing
```

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
