"""
Configuration and fixtures for Aegis Scholar API integration tests.

This module configures the Python path to allow importing from aegis_scholar_api.
All fixtures are defined in the root tests/conftest.py and automatically available.

Available fixtures:
- neo4j_container: Neo4j testcontainer (from root conftest)
- graph_db_container: Graph DB service container (from root conftest)
- neo4j_driver: Connected Neo4j driver (from root conftest)
- app_client: FastAPI test client (from root conftest)
- ensure_test_data: Auto-loads test data (from root conftest)
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file (if present)
load_dotenv()

# --- Service Configuration ---
# Add aegis_scholar_api to path for importing app modules
service_root = Path(__file__).resolve().parents[2] / "services" / "aegis_scholar_api"
if str(service_root) not in sys.path:
    sys.path.insert(0, str(service_root))
