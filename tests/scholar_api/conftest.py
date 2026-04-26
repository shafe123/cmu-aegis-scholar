"""
Configuration and fixtures for Aegis Scholar API integration tests.

This module provides:
- neo4j_driver: Connected driver to the Neo4j testcontainer
- app_client: FastAPI test client with proper environment configuration
- ensure_test_data: Automatic test data loading into Neo4j
"""

import sys
import gzip
import json
import time
import logging
from pathlib import Path

import pytest
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load environment variables from .env file (if present)
load_dotenv()

# Suppress Neo4j notification warnings
logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)

# --- Path Configuration ---
# Add parent directory to path to import shared conftest fixtures
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conftest import NEO4J_USER, NEO4J_PASSWORD, VECTOR_DB_DEFAULT_URL  # pylint: disable=wrong-import-position

# --- Service Configuration ---
# Add aegis_scholar_api to path for importing app modules
service_root = Path(__file__).resolve().parents[2] / "services" / "aegis_scholar_api"
if str(service_root) not in sys.path:
    sys.path.insert(0, str(service_root))


@pytest.fixture(scope="function")
def app_client(monkeypatch, graph_db_container):
    """
    FastAPI test client with dynamically configured environment.

    Scope: Function (recreated for each test to ensure clean environment)
    
    Sets GRAPH_DB_URL and VECTOR_DB_URL to match testcontainer instances.
    Forces module reimport to ensure settings are initialized with updated env vars.
    """
    # Configure environment with testcontainer URLs
    monkeypatch.setenv("GRAPH_DB_URL", graph_db_container)
    monkeypatch.setenv("VECTOR_DB_URL", VECTOR_DB_DEFAULT_URL)

    # Force reimport of app modules to pick up updated environment variables.
    # The Settings object initializes at module import time, so we must reload
    # the modules after setting environment variables.
    for module_name in ("app.config", "app.services.graph_db", "app.main"):
        if module_name in sys.modules:
            del sys.modules[module_name]

    from app.main import app  # pylint: disable=import-outside-toplevel

    return app


@pytest.fixture(scope="session")
def neo4j_driver(neo4j_container):
    """
    Neo4j driver connected to the testcontainer.

    Uses credentials from centralized test config.
    Closes connection after tests complete.
    """
    neo4j_host = neo4j_container.get_container_host_ip()
    neo4j_port = neo4j_container.get_exposed_port(7687)
    bolt_url = f"bolt://{neo4j_host}:{neo4j_port}"

    driver = GraphDatabase.driver(bolt_url, auth=(NEO4J_USER, NEO4J_PASSWORD))
    yield driver
    driver.close()


@pytest.fixture(scope="session", autouse=True)
def ensure_test_data(neo4j_driver):
    """
    Automatically loads test data into Neo4j if the database is empty.

    Checks for a canary author ID. If not found, loads:
    - Authors from dtic_authors_50.jsonl.gz
    - Topics from dtic_topics_50.jsonl.gz
    - Works from dtic_works_50.jsonl.gz with relationships

    This fixture runs automatically once per session.
    """
    time.sleep(2)

    # Use a known author ID as a canary to detect if data is already loaded
    canary_id = "author_703841d2-b558-53e2-8454-11689b6251db"
    data_dir = Path(__file__).resolve().parent.parent / "dtic_test_subset"

    with neo4j_driver.session() as session:
        result = session.run("MATCH (a:Author {id: $id}) RETURN a", id=canary_id)

        if not result.single():
            print(f"\n[Setup] Database empty. Loading test subset from {data_dir}...")

            load_gz_jsonl(session, data_dir / "dtic_authors_50.jsonl.gz", "Author")
            load_gz_jsonl(session, data_dir / "dtic_topics_50.jsonl.gz", "Topic")
            load_gz_jsonl(session, data_dir / "dtic_works_50.jsonl.gz", "Work")

            print("[Setup] Test data loading complete.")


def load_gz_jsonl(session, file_path, label):
    """
    Loads a gzipped JSONL file into Neo4j.

    Handles three node types:
    - Author: MERGE on id, SET name (from 'name' or 'display_name'), h_index, works_count
    - Topic: MERGE on id, SET name from 'display_name'
    - Work: MERGE on id, SET title, create AUTHORED relationships with Authors,
            and HAS_TOPIC relationships with Topics

    The Work data format supports both nested objects (authors: [{author_id: ...}])
    and direct arrays (author_ids: [...]) for flexibility across data sources.
    """
    if not file_path.exists():
        print(f"[Warning] Skipping {file_path.name} - file not found.")
        return

    with gzip.open(file_path, "rt", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            try:
                item = json.loads(line)

                if label == "Author":
                    session.execute_write(
                        lambda tx: tx.run(
                            """
                            MERGE (a:Author {id: $id})
                            SET a.name = $name,
                                a.h_index = $h_index,
                                a.works_count = $works_count
                            """,
                            id=item["id"],
                            name=item.get("name") or item.get("display_name"),
                            h_index=item.get("h_index", 0),
                            works_count=item.get("works_count", 0),
                        )
                    )

                elif label == "Topic":
                    session.execute_write(
                        lambda tx: tx.run(
                            "MERGE (t:Topic {id: $id}) SET t.name = $name",
                            id=item["id"],
                            name=item.get("display_name"),
                        )
                    )

                elif label == "Work":
                    # Handle both nested object format and direct array format
                    authors_data = item.get("authors", [])
                    author_ids = (
                        [a.get("author_id") for a in authors_data]
                        if authors_data
                        else item.get("author_ids", [])
                    )

                    topics_data = item.get("topics", [])
                    topic_ids = (
                        [t.get("topic_id") for t in topics_data]
                        if topics_data
                        else item.get("topic_ids", [])
                    )

                    session.execute_write(
                        lambda tx: tx.run(
                            """
                            MERGE (w:Work {id: $id})
                            SET w.title = $title
                            WITH w
                            UNWIND $author_ids AS a_id
                            MATCH (a:Author {id: a_id})
                            MERGE (a)-[:AUTHORED]->(w)
                            WITH w
                            UNWIND $topic_ids AS t_id
                            MATCH (t:Topic {id: t_id})
                            MERGE (w)-[:HAS_TOPIC]->(t)
                            """,
                            id=item["id"],
                            title=item.get("title"),
                            author_ids=author_ids,
                            topic_ids=topic_ids,
                        )
                    )
            except Exception as e:
                print(f"[Warning] Error loading {label} at line {line_num}: {e}")
                continue

    print(f"[Setup] Loaded {label} from {file_path.name}")
