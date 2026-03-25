# Test Runner Scripts

Unified test runner scripts for the Aegis Scholar monorepo.

## First-Time Setup

**Install all dependencies:**
```bash
npm run setup
```

This installs:
- Frontend dependencies (npm)
- Python dependencies for all services, jobs, libs, and integration tests (poetry)

## Quick Start

### Run All Tests

```bash
# Option 1: Using npm (recommended)
npm run test:all

# Option 2: Using Python script directly
python scripts/test_runner.py all

```

### Run Specific Components

```bash
# Frontend only
npm run test:frontend

# All services
npm run test:services

# All jobs
npm run test:jobs

# All libraries
npm run test:libs

# Integration tests
npm run test:integration

# All Python components
npm run test:python

# Specific component
python scripts/test_runner.py aegis-api
```

## Available npm Scripts

```bash
npm run test:all           # Run all tests (frontend + Python)
npm run test:frontend      # Run frontend tests only
npm run test:services      # Run all service tests
npm run test:jobs          # Run all job tests
npm run test:libs          # Run all library tests
npm run test:integration   # Run integration tests
npm run test:python        # Run all Python tests
npm run test:coverage      # Run all tests with coverage
```

## Python Script Usage

### Basic Usage

```bash
# Run all tests
python scripts/test_runner.py all

# Run specific components
python scripts/test_runner.py frontend aegis-api

# Run component groups
python scripts/test_runner.py services jobs
python scripts/test_runner.py python
```

### Options

```bash
# Skip coverage reporting (faster)
python scripts/test_runner.py all --no-coverage

# Stop on first failure
python scripts/test_runner.py all --fail-fast

# Combine options
python scripts/test_runner.py services --no-coverage --fail-fast
```

### Available Component Names

- **Individual Components**:
  - `frontend` - React frontend
  - `aegis-api` - Main API service
  - `graph-db` - Graph database service
  - `vector-db` - Vector database service
  - `vector-loader` - Vector loading job
  - `graph-loader` - Graph loading job
  - `example-lib` - Example shared library
  - `integration` - Integration tests

- **Component Groups**:
  - `all` - All components
  - `python` - All Python components
  - `services` - All services
  - `jobs` - All jobs
  - `libs` - All libraries

## Examples

### Development Workflow

```bash
# Quick test before commit (no coverage, fail fast)
python scripts/test_runner.py --no-coverage --fail-fast

# Test what you're working on
python scripts/test_runner.py frontend    # Working on frontend
python scripts/test_runner.py aegis-api   # Working on API
```

### Pre-commit Testing

```bash
# Full test suite with coverage
npm run test:all

# Or specific component with coverage
npm run test:services
```

### CI/CD Testing

```bash
# All tests, fail on first error
python scripts/test_runner.py all --fail-fast

# Python tests only
python scripts/test_runner.py python
```

## Output

The test runner provides:
- ✓ Success indicators (green)
- ✗ Failure indicators (red)
- ℹ Info messages (cyan)
- Summary of all test results
- Exit code 0 for success, 1 for any failures

Example output:
```
================================================================================
Running tests for: frontend, aegis-api, graph-db
================================================================================

ℹ Running frontend tests at frontend
✓ frontend tests passed

ℹ Running tests for aegis-api at services/aegis-scholar-api
✓ aegis-api tests passed

ℹ Running tests for graph-db at services/graph-db
✓ graph-db tests passed

================================================================================
Test Results Summary
================================================================================

✓ frontend           PASSED
✓ aegis-api          PASSED
✓ graph-db           PASSED

Total: 3 passed, 0 failed
```

## Prerequisites

- Python 3.12+
- Node.js 18+
- Poetry (`curl -sSL https://install.python-poetry.org | python3 -`)

**To install all dependencies automatically:**
```bash
npm run setup
```

## Troubleshooting

### Command Not Found

**Problem**: `python` or `poetry` not found

**Solution**:
```bash
# Check Python installation
python --version
python3 --version

# Check Poetry installation
poetry --version

# Install Poetry if needed
curl -sSL https://install.python-poetry.org | python3 -
```

### Tests Failing

**Problem**: Tests fail in some components

**Solution**:
```bash
# Run individual component to see detailed error
cd services/aegis-scholar-api
poetry run pytest -v

# Check dependencies are installed
poetry install
```

### Permission Denied (Unix/Linux/Mac)

**Problem**: Permission denied when running script

**Solution**:
```bash
# Make script executable
chmod +x scripts/test_runner.py

# Then run
./scripts/test_runner.py all
```

## Integration with IDEs

### VS Code

Add to `.vscode/tasks.json`:
```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Run All Tests",
      "type": "shell",
      "command": "npm run test:all",
      "group": {
        "kind": "test",
        "isDefault": true
      }
    },
    {
      "label": "Run Python Tests",
      "type": "shell",
      "command": "npm run test:python"
    }
  ]
}
```

### PyCharm

1. Open Settings → Tools → External Tools
2. Add new tool:
   - **Name**: Run All Tests
   - **Program**: `python`
   - **Arguments**: `scripts/test_runner.py all`
   - **Working directory**: `$ProjectFileDir$`

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      
      - name: Install Poetry
        run: curl -sSL https://install.python-poetry.org | python3 -
      
      - name: Set up Node.js
        uses: actions/setup-node@v2
        with:
          node-version: '18'
      
      - name: Install dependencies
        run: |
          cd frontend && npm install
          # Install Poetry deps for each component as needed
      
      - name: Run all tests
        run: python scripts/test_runner.py all --fail-fast
```

## Advanced Usage

### Custom Test Runner

You can modify `test_runner.py` to:
- Add new component types
- Change coverage thresholds
- Add custom test commands
- Integrate with other tools

### Parallel Testing

For faster execution, run components in parallel:
```bash
# Terminal 1
npm run test:frontend

# Terminal 2
npm run test:services

# Terminal 3
npm run test:jobs
```

Or use `pytest-xdist` for parallel Python tests:
```bash
poetry run pytest -n auto
```

## Coverage Reports

After running tests with coverage:

### Python Components
```bash
# View HTML report
cd services/aegis-scholar-api
open htmlcov/index.html  # Mac
start htmlcov/index.html  # Windows
xdg-open htmlcov/index.html  # Linux
```

### Frontend
```bash
cd frontend
open coverage/index.html  # Mac
start coverage/index.html  # Windows
xdg-open coverage/index.html  # Linux
```

## Contributing

When adding new components:

1. Add component path to `COMPONENTS` dict in `test_runner.py`
2. Add to appropriate group (`PYTHON_COMPONENTS`, etc.)
3. Add npm script to root `package.json`
4. Update this README

## Support

For issues with test runner:
1. Check component tests run individually first
2. Verify all dependencies are installed
3. Check Python/Node.js versions
4. Review component-specific test documentation
