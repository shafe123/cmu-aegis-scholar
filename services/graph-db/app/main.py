"""Main FastAPI application for the Aegis Scholar Graph DB service."""

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, List

from fastapi import FastAPI, HTTPException
from neo4j import GraphDatabase

from app.config import settings
from app.schemas import (
    AuthorNode,
    AuthorOrgRel,
    AuthorWorkRel,
    CollaboratorResponse,
    OrgNode,
    StatusResponse,
    StatsResponse,
    TopicNode,
    VizResponse,
    WorkNode,
    WorkTopicRel,
)

# --- 1. Setup Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 2. Database Driver Initialization ---
driver = None


def get_driver():
    """Create the Neo4j driver lazily so tests and imports stay clean."""
    global driver
    if driver is None:
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password or ""),
        )
    return driver


# --- 3. Application Lifespan ---
@asynccontextmanager
async def lifespan(_: FastAPI):
    """Handles clean startup and shutdown of resources."""
    global driver
    logger.info("Graph API starting up...")
    get_driver()
    yield
    logger.info("Graph API shutting down: Closing Neo4j Driver...")
    if driver is not None:
        driver.close()
        driver = None


# --- 4. Initialize FastAPI ---
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    lifespan=lifespan,
)

# --- 5. System & Health Endpoints ---


@app.get("/", tags=["System"])
async def root() -> dict[str, str]:
    """Root endpoint providing service information."""
    return {"title": settings.api_title, "version": settings.api_version, "status": "online"}


@app.get("/health", tags=["System"])
async def health_check() -> dict[str, str]:
    """Verifies connectivity to Neo4j and logs failures for troubleshooting."""
    try:
        with get_driver().session() as session:
            session.run("RETURN 1")
        return {"status": "healthy", "neo4j": "connected"}
    except Exception as e:  # pylint: disable=broad-exception-caught
        # Feedback Implementation: Log the specific error for DevOps troubleshooting
        logger.error("Health check failed: Unable to connect to Neo4j. Error: %s", e)
        return {"status": "unhealthy", "error": str(e)}


@app.get("/stats", tags=["System"], response_model=StatusResponse)
async def get_stats() -> dict[str, Any]:
    """Returns counts of nodes to help loaders determine if ingestion is needed."""
    try:
        with get_driver().session() as session:
            result = session.run("MATCH (a:Author) RETURN count(a) as count")
            record = result.single()
            count = record["count"] if record else 0
            return {"author_count": count}
    except Exception as e:
        logger.error("Database error in /stats: %s", e)
        raise HTTPException(status_code=500, detail=f"Graph database connection error: {str(e)}") from e


# --- 6. Ingestion Endpoints ---


@app.post("/topics", tags=["Ingestion"], response_model=StatusResponse)
async def upsert_topic(topic: TopicNode) -> dict[str, str]:
    """Upserts a Topic node into the graph."""
    query = """
    MERGE (t:Topic {id: $id})
    SET t.name = $name, t.field = $field, t.domain = $domain
    RETURN t.id
    """
    with get_driver().session() as session:
        session.run(query, **topic.model_dump())
    return {"status": "success", "id": topic.id}


@app.post("/authors", tags=["Ingestion"], response_model=StatusResponse)
async def upsert_author(author: AuthorNode) -> dict[str, str]:
    """Upserts an Author node into the graph."""
    query = """
    MERGE (a:Author {id: $id})
    SET a.name = $name, a.h_index = $h_index, a.works_count = $works_count
    RETURN a.id
    """
    with get_driver().session() as session:
        session.run(query, **author.model_dump())
    return {"status": "success", "id": author.id}


@app.post("/works", tags=["Ingestion"], response_model=StatusResponse)
async def upsert_work(work: WorkNode) -> dict[str, str]:
    """Upserts a Work node into the graph."""
    query = """
    MERGE (w:Work {id: $id})
    SET w.title = $title, w.year = $year, w.citation_count = $citation_count
    RETURN w.id
    """
    with get_driver().session() as session:
        session.run(query, **work.model_dump())
    return {"status": "success", "id": work.id}


@app.post("/relationships/authored", tags=["Relationships"])
async def link_author_work(rel: AuthorWorkRel) -> dict[str, str]:
    """Creates an AUTHORED relationship between an Author and a Work."""
    query = """
    MATCH (a:Author {id: $author_id})
    MATCH (w:Work {id: $work_id})
    MERGE (a)-[:AUTHORED]->(w)
    """
    with get_driver().session() as session:
        session.run(query, **rel.model_dump())
    return {"status": "linked"}


@app.post("/orgs", tags=["Ingestion"], response_model=StatusResponse)
async def upsert_org(org: OrgNode) -> dict[str, str]:
    """Upserts an Organization node into the graph."""
    query = """
    MERGE (o:Organization {id: $id})
    SET o.name = $name, o.type = $type, o.country = $country
    RETURN o.id
    """
    with get_driver().session() as session:
        session.run(query, **org.model_dump())
    return {"status": "success", "id": org.id}


@app.post("/relationships/affiliated", tags=["Relationships"])
async def link_author_org(rel: AuthorOrgRel) -> dict[str, str]:
    """Links an Author to an Organization (Affiliation)."""
    query = """
    MATCH (a:Author {id: $author_id})
    MATCH (o:Organization {id: $org_id})
    MERGE (a)-[:AFFILIATED_WITH {role: $role}]->(o)
    """
    with get_driver().session() as session:
        session.run(query, **rel.model_dump())
    return {"status": "linked"}


@app.post("/relationships/covers", tags=["Relationships"])
async def link_work_topic(rel: WorkTopicRel) -> dict[str, str]:
    """Links a Work to a Topic (Covers)."""
    query = """
    MATCH (w:Work {id: $work_id})
    MATCH (t:Topic {id: $topic_id})
    MERGE (w)-[:COVERS_TOPIC {score: $score}]->(t)
    """
    with get_driver().session() as session:
        session.run(query, **rel.model_dump())
    return {"status": "linked"}


# --- 7. Search & Analysis Endpoints ---


@app.get("/authors/{author_id}/collaborators", tags=["Analysis"], response_model=List[CollaboratorResponse])
async def get_collaborators(author_id: str) -> List[dict]:
    """Finds researchers who have shared works with the given author."""
    query = """
    MATCH (a:Author {id: $id})-[:AUTHORED]->(w:Work)<-[:AUTHORED]-(collab:Author)
    WHERE a <> collab
    RETURN DISTINCT collab.name as name, collab.id as id
    """
    with get_driver().session() as session:
        result = session.run(query, id=author_id)
        return [dict(record) for record in result]


# --- Adds the Organization to visualization workflow ---
@app.get("/viz/author-network/{author_id}", tags=["Visualization"], response_model=VizResponse)
async def get_author_network(author_id: str) -> dict:
    """Returns a JSON structure (nodes/edges) for frontend graph visualization."""
    query = """
    MATCH (author:Author {id: $node_id})
    OPTIONAL MATCH (author)-[:AUTHORED]->(work:Work)
    OPTIONAL MATCH (work)<-[:AUTHORED]-(coAuthor:Author)
    OPTIONAL MATCH (author)-[:AFFILIATED_WITH]->(org:Organization)
    RETURN author, work, coAuthor, org
    LIMIT 100
    """

    with get_driver().session() as session:
        result = session.run(query, node_id=author_id)
        nodes, edges, node_ids = [], [], set()

        for record in result:
            author, work, coauthor, org = (
                record["author"],
                record["work"],
                record["coAuthor"],
                record["org"],
            )

            # Add Author
            if author and author["id"] not in node_ids:
                author_name = author.get("name", "Unknown")
                mock_email = f"{author_name.replace(' ', '.').lower()}@dod.mil"
                nodes.append(
                    {
                        "id": author["id"],
                        "label": author_name,
                        "group": "author",
                        "color": "#ff6b6b",
                        "email": author.get("email") or mock_email,
                        "works_count": author.get("works_count") or author.get("works", 0),
                    }
                )
                node_ids.add(author["id"])

            # Add Work
            if work and work["id"] not in node_ids:
                full_title = work.get("title", "Unknown Title")
                short_label = full_title[:30] + "..." if len(full_title) > 30 else full_title

                # Extract year from publication_date (e.g., "2023-05-12" -> "2023")
                raw_date = work.get("publication_date")
                formatted_year = str(raw_date)[:4] if raw_date else "N/A"

                nodes.append(
                    {
                        "id": work["id"],
                        "label": short_label,
                        "full_title": full_title,
                        "group": "work",
                        "color": "#4ecdc4",
                        "year": formatted_year if formatted_year != "N/A" else (work.get("year") or "N/A"),
                        "citations": work.get("citation_count", 0),
                        "abstract": work.get("abstract"),
                    }
                )
                node_ids.add(work["id"])
                edges.append({"from": author["id"], "to": work["id"], "label": "AUTHORED"})

            # Add Co-Author
            if coauthor and coauthor["id"] not in node_ids:
                coauthor_name = coauthor.get("name", "Unknown")
                mock_email = f"{coauthor_name.replace(' ', '.').lower()}@dod.mil"
                nodes.append(
                    {
                        "id": coauthor["id"],
                        "label": coauthor_name,
                        "group": "author",
                        "color": "#ffadad",
                        "email": coauthor.get("email") or mock_email,
                        "works_count": coauthor.get("works_count") or coauthor.get("works", 0),
                    }
                )
                node_ids.add(coauthor["id"])
                edges.append({"from": coauthor["id"], "to": work["id"], "label": "AUTHORED"})

            # Add Organization (New)
            if org and org["id"] not in node_ids:
                nodes.append(
                    {
                        "id": org["id"],
                        "label": org["name"],
                        "group": "organization",
                        "color": "#f9ca24",
                        "org_id": org["id"],
                    }
                )
                node_ids.add(org["id"])
                edges.append({"from": author["id"], "to": org["id"], "label": "AFFILIATED_WITH"})

        return {"nodes": nodes, "edges": edges}
