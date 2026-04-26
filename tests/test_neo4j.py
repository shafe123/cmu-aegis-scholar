"""Integration tests for data loading workflows using live containers."""

import pytest
from testcontainers.neo4j import Neo4jContainer


# ---------------------------------------------------------------------------
# Neo4j container fixture — starts once for all tests in this module
# ---------------------------------------------------------------------------

NEO4J_IMAGE = "neo4j:5.12"


@pytest.fixture(scope="module")
def neo4j_container():
    """Start a real Neo4j container for integration testing."""
    with Neo4jContainer(image=NEO4J_IMAGE) as container:
        yield container


@pytest.fixture(scope="module")
def neo4j_driver(neo4j_container):
    """Provide a connected Neo4j driver pointed at the test container."""
    driver = neo4j_container.get_driver()
    yield driver
    driver.close()


@pytest.fixture(autouse=True)
def clean_database(neo4j_driver):
    """Wipe all nodes and relationships before each test for a clean slate."""
    with neo4j_driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")


# ---------------------------------------------------------------------------
# Helper — mirrors the graph-db API ingestion logic directly via driver
# ---------------------------------------------------------------------------

def ingest_author(driver, author: dict):
    """Insert an Author node directly into the test Neo4j instance."""
    with driver.session() as session:
        session.run(
            """
            MERGE (a:Author {id: $id})
            SET a.name = $name, a.h_index = $h_index, a.works_count = $works_count
            """,
            id=author["id"],
            name=author["name"],
            h_index=author.get("h_index", 0),
            works_count=author.get("works_count", 0),
        )


def ingest_work(driver, work: dict):
    """Insert a Work node directly into the test Neo4j instance."""
    with driver.session() as session:
        session.run(
            """
            MERGE (w:Work {id: $id})
            SET w.title = $title, w.year = $year, w.citation_count = $citation_count
            """,
            id=work["id"],
            title=work["title"],
            year=work.get("year", 0),
            citation_count=work.get("citation_count", 0),
        )


def link_author_work(driver, author_id: str, work_id: str):
    """Create an AUTHORED relationship between an Author and a Work."""
    with driver.session() as session:
        session.run(
            """
            MATCH (a:Author {id: $author_id})
            MATCH (w:Work {id: $work_id})
            MERGE (a)-[:AUTHORED]->(w)
            """,
            author_id=author_id,
            work_id=work_id,
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.requires_docker
def test_neo4j_container_is_healthy(neo4j_driver):
    """Verify the Neo4j container starts and accepts connections."""
    with neo4j_driver.session() as session:
        result = session.run("RETURN 1 AS value")
        record = result.single()
        assert record["value"] == 1


@pytest.mark.integration
@pytest.mark.requires_docker
def test_author_node_created(neo4j_driver, sample_authors):
    """Author node should be created and retrievable by ID."""
    author = sample_authors[0]
    ingest_author(neo4j_driver, author)

    with neo4j_driver.session() as session:
        result = session.run(
            "MATCH (a:Author {id: $id}) RETURN a.name AS name",
            id=author["id"],
        )
        record = result.single()

    assert record is not None
    assert record["name"] == author["name"]


@pytest.mark.integration
@pytest.mark.requires_docker
def test_author_upsert_is_idempotent(neo4j_driver, sample_authors):
    """Inserting the same author twice should not create duplicate nodes."""
    author = sample_authors[0]
    ingest_author(neo4j_driver, author)
    ingest_author(neo4j_driver, author)

    with neo4j_driver.session() as session:
        result = session.run(
            "MATCH (a:Author {id: $id}) RETURN count(a) AS count",
            id=author["id"],
        )
        record = result.single()

    assert record["count"] == 1


@pytest.mark.integration
@pytest.mark.requires_docker
def test_work_node_created(neo4j_driver, sample_works):
    """Work node should be created and retrievable by ID."""
    work = sample_works[0]
    ingest_work(neo4j_driver, work)

    with neo4j_driver.session() as session:
        result = session.run(
            "MATCH (w:Work {id: $id}) RETURN w.title AS title",
            id=work["id"],
        )
        record = result.single()

    assert record is not None
    assert record["title"] == work["title"]


@pytest.mark.integration
@pytest.mark.requires_docker
def test_authored_relationship_created(neo4j_driver, sample_authors, sample_works):
    """AUTHORED relationship should link Author to Work correctly."""
    author = sample_authors[0]
    work = sample_works[0]
    ingest_author(neo4j_driver, author)
    ingest_work(neo4j_driver, work)
    link_author_work(neo4j_driver, author["id"], work["id"])

    with neo4j_driver.session() as session:
        result = session.run(
            """
            MATCH (a:Author {id: $author_id})-[:AUTHORED]->(w:Work {id: $work_id})
            RETURN a.name AS author_name, w.title AS work_title
            """,
            author_id=author["id"],
            work_id=work["id"],
        )
        record = result.single()

    assert record is not None
    assert record["author_name"] == author["name"]
    assert record["work_title"] == work["title"]


@pytest.mark.integration
@pytest.mark.requires_docker
def test_collaborator_discovery(neo4j_driver, sample_authors, sample_works):
    """Two authors sharing a work should appear as collaborators."""
    author1 = sample_authors[0]
    author2 = sample_authors[1]
    work = sample_works[0]

    ingest_author(neo4j_driver, author1)
    ingest_author(neo4j_driver, author2)
    ingest_work(neo4j_driver, work)
    link_author_work(neo4j_driver, author1["id"], work["id"])
    link_author_work(neo4j_driver, author2["id"], work["id"])

    with neo4j_driver.session() as session:
        result = session.run(
            """
            MATCH (a:Author {id: $id})-[:AUTHORED]->(w:Work)<-[:AUTHORED]-(collab:Author)
            WHERE a <> collab
            RETURN DISTINCT collab.name AS name
            """,
            id=author1["id"],
        )
        collaborators = [record["name"] for record in result]

    assert author2["name"] in collaborators


@pytest.mark.integration
@pytest.mark.requires_docker
def test_multiple_works_per_author(neo4j_driver, sample_authors, sample_works):
    """An author linked to multiple works should return all of them."""
    author = sample_authors[0]
    ingest_author(neo4j_driver, author)

    for work in sample_works:
        ingest_work(neo4j_driver, work)
        link_author_work(neo4j_driver, author["id"], work["id"])

    with neo4j_driver.session() as session:
        result = session.run(
            """
            MATCH (a:Author {id: $id})-[:AUTHORED]->(w:Work)
            RETURN count(w) AS work_count
            """,
            id=author["id"],
        )
        record = result.single()

    assert record["work_count"] == len(sample_works)


@pytest.mark.integration
@pytest.mark.requires_docker
def test_empty_collaborator_query(neo4j_driver, sample_authors):
    """An author with no co-authors should return an empty collaborator list."""
    author = sample_authors[0]
    ingest_author(neo4j_driver, author)

    with neo4j_driver.session() as session:
        result = session.run(
            """
            MATCH (a:Author {id: $id})-[:AUTHORED]->(w:Work)<-[:AUTHORED]-(collab:Author)
            WHERE a <> collab
            RETURN DISTINCT collab.name AS name
            """,
            id=author["id"],
        )
        collaborators = [record["name"] for record in result]

    assert collaborators == []