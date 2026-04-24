"""
Configuration and fixtures for the Aegis Scholar API integration tests.
"""

# pylint: disable=redefined-outer-name
import os
import gzip
import json
import sys
from pathlib import Path
import pytest
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load the variables from the .env file
load_dotenv()

# Pathing setup
service_root = Path(__file__).resolve().parents[3] / "services" / "aegis-scholar-api"
if str(service_root) not in sys.path:
    sys.path.insert(0, str(service_root))


@pytest.fixture
def app_client(monkeypatch):
    """
    Ensures the Scholar API points to the Graph DB SERVICE (8003)
    rather than the raw Neo4j instance.
    """
    # Based on your docker ps: dev-graph-db is on 8003
    monkeypatch.setenv("GRAPH_DB_URL", "http://localhost:8003")

    # Also update Vector DB while we are at it (it's on 8002)
    monkeypatch.setenv("VECTOR_DB_URL", "http://localhost:8002")

    from app.main import app  # pylint: disable=import-outside-toplevel

    return app


@pytest.fixture(scope="session")
def neo4j_driver(graph_db_url):
    """
    Connects neo4j driver.
    """
    # Fallback logic:
    # 1. Use the ENV var if it exists
    # 2. Otherwise default to 'password'
    db_password = os.getenv("NEO4J_PASSWORD", "neo4j_password")

    bolt_url = graph_db_url.replace("http://", "bolt://")
    if "8002" in bolt_url:
        bolt_url = "bolt://localhost:7687"

    driver = GraphDatabase.driver(bolt_url, auth=("neo4j", db_password))
    yield driver
    driver.close()


@pytest.fixture(scope="session", autouse=True)
def ensure_test_data(neo4j_driver):
    """
    Automatically loads the GZipped subset if the database is empty.
    """
    # Use an ID you know exists in dtic_authors_50.jsonl.gz
    canary_id = "author_6671149b-381b-573b-bb3d-81d86a789471"

    # Path logic: one folder up from this conftest, then into dtic_test_subset
    data_dir = Path(__file__).resolve().parent.parent / "dtic_test_subset"

    with neo4j_driver.session() as session:
        result = session.run("MATCH (a:Author {id: $id}) RETURN a", id=canary_id)

        if not result.single():
            print(f"\n[Setup] Database empty. Loading subset from {data_dir}...")

            # 1. Load Authors
            load_gz_jsonl(session, data_dir / "dtic_authors_50.jsonl.gz", "Author")

            # 2. Load Topics (if you want them in the viz)
            load_gz_jsonl(session, data_dir / "dtic_topics_50.jsonl.gz", "Topic")

            # 3. Load Works & Create Relationships
            load_gz_jsonl(session, data_dir / "dtic_works_50.jsonl.gz", "Work")

            print("[Setup] Integration data loading complete.")


def load_gz_jsonl(session, file_path, label):
    """
    Unzips the test subset.
    """
    if not file_path.exists():
        print(f"[Warning] Skipping {file_path.name} - file not found.")
        return

    with gzip.open(file_path, "rt", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)

            if label == "Author":
                session.run(
                    "MERGE (a:Author {id: $id}) SET a.name = $name",
                    id=item["id"],
                    name=item.get("display_name"),
                )

            elif label == "Topic":
                session.run(
                    "MERGE (t:Topic {id: $id}) SET t.name = $display_name",
                    id=item["id"],
                    display_name=item.get("display_name"),
                )

            elif label == "Work":
                # Create Work and link to Authors/Topics in one transaction
                session.run(
                    """
                    MERGE (w:Work {id: $id})
                    SET w.title = $title
                    WITH w
                    // Link Authors
                    UNWIND $author_ids AS a_id
                    MATCH (a:Author {id: a_id})
                    MERGE (a)-[:AUTHORED]->(w)
                    WITH w
                    // Link Topics (if your works data has topic_ids)
                    UNWIND $topic_ids AS t_id
                    MATCH (t:Topic {id: t_id})
                    MERGE (w)-[:HAS_TOPIC]->(t)
                """,
                    id=item["id"],
                    title=item.get("title"),
                    author_ids=item.get("author_ids", []),
                    topic_ids=item.get("topic_ids", []),
                )
