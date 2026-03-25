# Libraries Testing Guide

This directory contains shared Python libraries used across services and jobs.

## Libraries

- **example_lib**: Example shared library template

## Running Tests

### Individual Library

```bash
# Navigate to library directory
cd libs/example_lib

# Install dependencies (first time only)
poetry install

# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=example_lib

# Run specific test file
poetry run pytest tests/test_example_lib.py

# Run with verbose output
poetry run pytest -v
```

### All Libraries

From the repository root:
```bash
# Run tests for all libraries
python scripts/test_all_libs.py
```

## Test Structure

Each library follows this structure:
```
library-name/
├── library_name/        # Library source code
│   ├── __init__.py
│   ├── module1.py
│   └── module2.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py     # Shared fixtures
│   ├── test_module1.py
│   └── test_module2.py
└── pyproject.toml      # Dependencies and test config
```

## Coverage Requirements

- **Target**: 80% code coverage (libraries should aim for higher)
- **Enforcement**: Tests will fail if coverage drops below 80%
- **View Reports**: After running with `--cov`, open `htmlcov/index.html`

## Writing Library Tests

### Testing Pure Functions

```python
def test_calculation():
    """Test a pure calculation function."""
    from example_lib.utils import calculate
    
    result = calculate(5, 3)
    assert result == 8
```

### Testing with Fixtures

```python
def test_with_fixture(sample_data):
    """Test using a fixture."""
    from example_lib.processors import process
    
    result = process(sample_data)
    assert result is not None
```

### Testing Data Transformations

```python
def test_transform_data():
    """Test data transformation."""
    from example_lib.transforms import transform_author
    
    input_data = {"display_name": "John Doe", "id": "A123"}
    result = transform_author(input_data)
    
    assert result["name"] == "John Doe"
    assert result["author_id"] == "A123"
```

### Testing Validators

```python
import pytest
from example_lib.validators import validate_email

def test_valid_email():
    """Test email validation with valid input."""
    assert validate_email("test@example.com") is True

def test_invalid_email():
    """Test email validation with invalid input."""
    assert validate_email("not-an-email") is False
    
def test_email_raises_error():
    """Test that invalid email raises appropriate error."""
    with pytest.raises(ValueError):
        validate_email(None)
```

### Testing Utilities

```python
def test_string_utility():
    """Test string utility functions."""
    from example_lib.utils import slugify
    
    result = slugify("Hello World! 123")
    assert result == "hello-world-123"
    
    result = slugify("Test@Example.com")
    assert result == "test-example-com"
```

### Testing Classes

```python
def test_class_initialization():
    """Test class initialization."""
    from example_lib.models import DataModel
    
    model = DataModel(name="Test", value=42)
    assert model.name == "Test"
    assert model.value == 42

def test_class_method():
    """Test class methods."""
    from example_lib.models import DataModel
    
    model = DataModel(name="Test", value=10)
    result = model.double_value()
    
    assert result == 20
```

### Parametrized Tests

```python
import pytest

@pytest.mark.parametrize("input,expected", [
    ("hello", "HELLO"),
    ("World", "WORLD"),
    ("123", "123"),
    ("", ""),
])
def test_uppercase(input, expected):
    """Test uppercase function with multiple inputs."""
    from example_lib.utils import to_uppercase
    assert to_uppercase(input) == expected
```

## Best Practices for Library Testing

1. **Test All Public APIs**: Every exported function/class should have tests
2. **Edge Cases**: Test boundary conditions and edge cases
3. **Error Handling**: Test that errors are handled appropriately
4. **Pure Functions**: Libraries should prefer pure functions (easier to test)
5. **No External Dependencies**: Mock any external services
6. **Documentation**: Test examples from docstrings

## Common Fixtures

Available in `conftest.py`:

- `sample_data`: Generic data dictionary
- `sample_list`: Simple list of integers
- `sample_dict_list`: List of dictionaries

Add library-specific fixtures as needed.

## Testing Library Integration

When testing how your library integrates with other components:

```python
def test_library_integration():
    """Test library usage in a realistic scenario."""
    from example_lib.processors import DataProcessor
    
    # Create processor
    processor = DataProcessor()
    
    # Process data
    raw_data = [{"id": "1"}, {"id": "2"}]
    results = processor.process_all(raw_data)
    
    # Verify results
    assert len(results) == 2
    assert all(r.get("processed") for r in results)
```

## Configuration

Test configuration is in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = [
    "--cov=example_lib",
    "--cov-report=html",
    "--cov-report=term-missing",
    "--cov-fail-under=80",
]
```

## Using Libraries in Other Components

When services or jobs import your library, they should mock it in tests:

```python
# In service test
def test_service_uses_library(mocker):
    """Test service that uses the library."""
    mock_lib_function = mocker.patch('example_lib.utils.process')
    mock_lib_function.return_value = {"result": "mocked"}
    
    # Test service code that uses the library
```

## CI/CD Integration

Library tests run:
- On every PR that modifies library code
- Before publishing library packages
- As part of full test suite

## Versioning

Libraries should follow semantic versioning:
- **Major**: Breaking changes to public API
- **Minor**: New features, backwards compatible
- **Patch**: Bug fixes

Update tests when changing library versions.

## Troubleshooting

### Import Errors
```bash
# Ensure library is installed
poetry install

# Verify Python path
poetry run python -c "import example_lib; print(example_lib.__file__)"
```

### Coverage Issues
```bash
# Make sure coverage includes the right package
poetry run pytest --cov=example_lib --cov-report=term-missing
```

### Tests Can't Find Module
Ensure your library has proper `__init__.py` files and is listed in `pyproject.toml`:
```toml
packages = [{include = "example_lib"}]
```

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest parametrize](https://docs.pytest.org/en/stable/parametrize.html)
- [pytest fixtures](https://docs.pytest.org/en/stable/fixture.html)
- [Python packaging](https://packaging.python.org/)
