# Services Testing Guide

This directory contains Python-based microservices, each with their own test suite.

## Services

- **aegis-scholar-api**: Main API gateway for search functionality
- **graph-db**: Neo4j graph database service
- **vector-db**: Milvus vector search service

## Running Tests

### Individual Service

```bash
# Navigate to service directory
cd services/aegis-scholar-api

# Install dependencies (first time only)
poetry install

# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=app

# Run specific test file
poetry run pytest tests/test_api.py

# Run tests matching a pattern
poetry run pytest -k "test_search"

# Run in verbose mode
poetry run pytest -v

# Run tests and stop at first failure
poetry run pytest -x
```

### All Services

From the repository root:
```bash
# Run tests for all services (see root-level test runner scripts)
python scripts/test_all_services.py
```

## Test Structure

Each service follows this structure:
```
service-name/
├── app/                  # Application code
├── tests/
│   ├── __init__.py
│   ├── conftest.py      # Shared fixtures
│   ├── test_api.py      # API endpoint tests
│   ├── test_service.py  # Business logic tests
│   └── test_utils.py    # Utility function tests
└── pyproject.toml       # Dependencies and test config
```

## Coverage Requirements

- **Target**: 80% code coverage
- **Enforcement**: Tests will fail if coverage drops below 80%
- **View Reports**: After running with `--cov`, open `htmlcov/index.html`

## Writing Tests

### Basic Test Structure

```python
import pytest
from fastapi.testclient import TestClient

def test_example():
    """Test description following Google style."""
    # Arrange
    expected = "value"
    
    # Act
    result = function_to_test()
    
    # Assert
    assert result == expected
```

### Async Tests

```python
@pytest.mark.asyncio
async def test_async_function():
    """Test async operations."""
    result = await async_function()
    assert result is not None
```

### Using Fixtures

```python
def test_with_fixture(sample_author_result):
    """Test using a fixture from conftest.py."""
    assert sample_author_result["id"] is not None
```

### Mocking External Dependencies

```python
from unittest.mock import Mock, AsyncMock

def test_with_mock(mocker):
    """Test with mocked external service."""
    mock_client = mocker.patch('app.services.external_api')
    mock_client.get.return_value = {"data": "test"}
    
    result = function_that_calls_external_api()
    assert result == {"data": "test"}
```

## Best Practices

1. **Isolate Tests**: Each test should be independent
2. **Mock External Services**: Don't make real API calls or database connections
3. **Use Fixtures**: Share common setup code via conftest.py
4. **Descriptive Names**: Test names should describe what they test
5. **One Assertion**: Prefer one logical assertion per test
6. **Fast Tests**: Keep unit tests under 1 second each

## Test Categories

### Unit Tests
Test individual functions/methods in isolation:
```python
def test_parse_author_name():
    """Unit test for name parsing function."""
    result = parse_author_name("Doe, John")
    assert result == {"first": "John", "last": "Doe"}
```

### Integration Tests
Test interaction between components:
```python
@pytest.mark.asyncio
async def test_api_to_database_integration():
    """Integration test for API calling database."""
    # Test with real database connection or testcontainers
    pass
```

### API Tests
Test FastAPI endpoints:
```python
def test_search_endpoint():
    """Test the search API endpoint."""
    from app.main import app
    client = TestClient(app)
    
    response = client.get("/api/v1/search?q=test")
    assert response.status_code == 200
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

## Continuous Integration

Tests run automatically on:
- Pull requests
- Commits to main branch
- Pre-deployment

CI will fail if:
- Any test fails
- Coverage drops below 80%
- Linting issues are found

## Troubleshooting

### Import Errors
```bash
# Ensure package is installed in development mode
poetry install
```

### Async Test Issues
```bash
# Make sure pytest-asyncio is installed
poetry add --group dev pytest-asyncio
```

### Coverage Not Working
```bash
# Reinstall pytest-cov
poetry add --group dev pytest-cov --force
```

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [FastAPI testing guide](https://fastapi.tiangolo.com/tutorial/testing/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [Coverage.py](https://coverage.readthedocs.io/)
