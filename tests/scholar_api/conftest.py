# tests/integration/scholar_api/conftest.py
import sys
from pathlib import Path
import pytest
from httpx import ASGITransport

# 1. The Pathing Logic (Satisfies Owner's concern about global pythonpath)
service_root = Path(__file__).resolve().parents[3] / "services" / "aegis-scholar-api"
if str(service_root) not in sys.path:
    sys.path.insert(0, str(service_root))

# 2. Service-Specific Fixtures
@pytest.fixture
def app_client():
    """
    Returns an async client specifically bound to the Scholar API app.
    This allows us to test the API logic directly.
    """
    from app.main import app  # Now safe to import because of the path above
    return app
