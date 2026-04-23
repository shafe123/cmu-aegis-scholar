"""Integration test configuration and shared fixtures."""

import pytest
import httpx


@pytest.fixture(scope="session")
def base_api_url():
    """Base URL for API integration tests."""
    return "http://localhost:8000"


@pytest.fixture(scope="session")
def vector_db_url():
    """Vector database service URL."""
    return "http://localhost:8001"


@pytest.fixture(scope="session")
def graph_db_url():
    """Graph database service URL."""
    return "http://localhost:8002"


@pytest.fixture
async def http_client():
    """Async HTTP client for integration tests."""
    async with httpx.AsyncClient() as client:
        yield client


@pytest.fixture
def sample_integration_data():
    """Sample data for integration testing across components."""
    return {
        "authors": [
            {
                "id": "A123456",
                "display_name": "Dr. Jane Smith",
                "affiliation": "Carnegie Mellon University",
            },
            {
                "id": "A234567",
                "display_name": "Dr. John Doe",
                "affiliation": "MIT",
            },
        ],
        "works": [
            {
                "id": "W789012",
                "title": "Advanced AI Research",
                "authors": ["A123456", "A234567"],
                "year": 2025,
            }
        ],
        "organizations": [
            {
                "id": "O111111",
                "display_name": "Carnegie Mellon University",
                "type": "education",
            }
        ],
    }


@pytest.fixture
def sample_search_query():
    """Sample search query for end-to-end tests."""
    return {
        "query": "machine learning artificial intelligence",
        "filters": {
            "year_min": 2020,
            "year_max": 2026,
            "author_affiliation": "Carnegie Mellon University",
        },
        "limit": 20,
    }


# Docker/testcontainers fixtures (uncomment when ready to use):
# @pytest.fixture(scope="session")
# def milvus_container():
#     """Start Milvus container for integration tests."""
#     from testcontainers.milvus import MilvusContainer
#     with MilvusContainer() as milvus:
#         yield milvus
#
#
# @pytest.fixture(scope="session")
# def neo4j_container():
#     """Start Neo4j container for integration tests."""
#     from testcontainers.neo4j import Neo4jContainer
#     with Neo4jContainer() as neo4j:
#         yield neo4j
