"""FastAPI application for Neo4j graph database operations."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from neo4j import GraphDatabase

from app.config import settings
from app.schemas import AuthorNode, AuthorOrgRel, AuthorWorkRel, OrgNode, WorkNode

# --- 1. Setup Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 2. Database Driver Initialization ---
driver = GraphDatabase.driver(
    settings.neo4j_uri,
    auth=(settings.neo4j_user, settings.neo4j_password or ""),
)


# --- 3. Application Lifespan ---
@asynccontextmanager
async def lifespan(_: FastAPI):
    """Handles clean startup and shutdown of resources."""
    logger.info("Graph API starting up...")
    yield
    logger.info("Graph API shutting down: Closing Neo4j Driver...")
    if driver:
        driver.close()


# --- 4. Initialize FastAPI ---
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    lifespan=lifespan,
)

# --- 5. System & Health Endpoints ---


@app.get("/", tags=["System"])
async def root():
    """Root endpoint providing service information."""
    return {"title": settings.api_title, "version": settings.api_version, "status": "online"}


@app.get("/health", tags=["System"])
async def health_check() -> dict[str, str]:
    """Verifies connectivity to Neo4j and logs failures for troubleshooting."""
    try:
        with driver.session() as session:
            session.run("RETURN 1")
        return {"status": "healthy", "neo4j": "connected"}
    except Exception as e:  # pylint: disable=broad-exception-caught
        # Feedback Implementation: Log the specific error for DevOps troubleshooting
        logger.error("Health check failed: Unable to connect to Neo4j. Error: %s", e)
        return {"status": "unhealthy", "error": str(e)}


@app.get("/stats", tags=["System"])
async def get_stats():
    """Returns counts of nodes to help loaders determine if ingestion is needed."""
    try:
        with driver.session() as session:
            result = session.run("MATCH (a:Author) RETURN count(a) as count")
            record = result.single()
            count = record["count"] if record else 0
            return {"author_count": count}
    except Exception as e:
        logger.error("Database error in /stats: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Graph database connection error: {str(e)}"
        ) from e


# --- 6. Ingestion Endpoints ---


@app.post("/authors", tags=["Ingestion"])
async def upsert_author(author: AuthorNode):
    """Upserts an Author node into the graph."""
    query = """
    MERGE (a:Author {id: $id})
    SET a.name = $name, a.h_index = $h_index, a.works_count = $works_count
    RETURN a.id
    """
    with driver.session() as session:
        session.run(query, **author.model_dump())
    return {"status": "success", "id": author.id}


@app.post("/works", tags=["Ingestion"])
async def upsert_work(work: WorkNode):
    """Upserts a Work node into the graph."""
    query = """
    MERGE (w:Work {id: $id})
    SET w.title = $title, w.year = $year, w.citation_count = $citation_count
    RETURN w.id
    """
    with driver.session() as session:
        session.run(query, **work.model_dump())
    return {"status": "success", "id": work.id}


@app.post("/relationships/authored", tags=["Relationships"])
async def link_author_work(rel: AuthorWorkRel):
    """Creates an AUTHORED relationship between an Author and a Work."""
    query = """
    MATCH (a:Author {id: $author_id})
    MATCH (w:Work {id: $work_id})
    MERGE (a)-[:AUTHORED]->(w)
    """
    with driver.session() as session:
        session.run(query, **rel.model_dump())
        session.run(query, **rel.model_dump())
    return {"status": "linked"}


@app.post("/orgs", tags=["Ingestion"])
async def upsert_org(org: OrgNode):
    """Upserts an Organization node into the graph."""
    query = """
    MERGE (o:Organization {id: $id})
    SET o.name = $name, o.type = $type, o.country = $country
    RETURN o.id
    """
    with driver.session() as session:
        session.run(query, **org.model_dump())
    return {"status": "success", "id": org.id}


@app.post("/relationships/affiliated", tags=["Relationships"])
async def link_author_org(rel: AuthorOrgRel):
    """Links an Author to an Organization (Affiliation)."""
    query = """
    MATCH (a:Author {id: $author_id})
    MATCH (o:Organization {id: $org_id})
    MERGE (a)-[:AFFILIATED_WITH {role: $role}]->(o)
    """
    with driver.session() as session:
        session.run(query, **rel.model_dump())
    return {"status": "linked"}


# --- 7. Search & Analysis Endpoints ---


@app.get("/authors/{author_id}/collaborators", tags=["Analysis"])
async def get_collaborators(author_id: str):
    """Finds researchers who have shared works with the given author."""
    query = """
    MATCH (a:Author {id: $id})-[:AUTHORED]->(w:Work)<-[:AUTHORED]-(collab:Author)
    WHERE a <> collab
    RETURN DISTINCT collab.name as name, collab.id as id
    """
    with driver.session() as session:
        result = session.run(query, id=author_id)
        return [dict(record) for record in result]


# --- Adds the Organization to visualization workflow ---
@app.get("/viz/author-network/{author_id}", tags=["Visualization"])
async def get_author_network(author_id: str):
    """Returns a JSON structure (nodes/edges) for frontend graph visualization."""
    query = """
    MATCH (author:Author {id: $node_id})
    OPTIONAL MATCH (author)-[:AUTHORED]->(work:Work)
    OPTIONAL MATCH (work)<-[:AUTHORED]-(coAuthor:Author)
    OPTIONAL MATCH (author)-[:AFFILIATED_WITH]->(org:Organization)
    RETURN author, work, coAuthor, org
    LIMIT 50
    """

    with driver.session() as session:
        result = session.run(query, node_id=author_id)
        nodes, edges, node_ids = [], [], set()

        for record in result:
            author = record["author"]
            work = record["work"]
            coauthor = record["coAuthor"]
            org = record["org"]

            # Add Author
            if author and author["id"] not in node_ids:
                nodes.append(
                    {"id": author["id"], "label": author["name"],
                     "group": "author", "color": "#ff6b6b"}
                )
                node_ids.add(author["id"])

            # Add Work
            if work and work["id"] not in node_ids:
                nodes.append(
                    {
                        "id": work["id"],
                        "label": work["title"][:30] + "...",
                        "group": "work",
                        "color": "#4ecdc4",
                    }
                )
                node_ids.add(work["id"])
                edges.append({"from": author["id"], "to": work["id"], "label": "AUTHORED"})

            # Add Co-Author
            if coauthor and coauthor["id"] not in node_ids:
                nodes.append(
                    {"id": coauthor["id"], "label": coauthor["name"],
                     "group": "author", "color": "#ffadad"}
                )
                node_ids.add(coauthor["id"])
                edges.append({"from": coauthor["id"], "to": work["id"], "label": "AUTHORED"})

            # Add Organization (New)
            if org and org["id"] not in node_ids:
                nodes.append(
                    {"id": org["id"], "label": org["name"],
                     "group": "organization", "color": "#f9ca24"}
                )
                node_ids.add(org["id"])
                edges.append({"from": author["id"], "to": org["id"], "label": "AFFILIATED_WITH"})

        return {"nodes": nodes, "edges": edges}
