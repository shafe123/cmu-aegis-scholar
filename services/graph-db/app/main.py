import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Body, HTTPException
from neo4j import GraphDatabase

from app.config import settings
from app.schemas import AuthorNode, WorkNode, AuthorWorkRel

# --- 1. Setup Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 2. Database Driver Initialization ---
# The driver is initialized globally but closed cleanly in lifespan
driver = GraphDatabase.driver(
    settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
)


# --- 3. Application Lifespan (Startup/Shutdown) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
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


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint that verifies Neo4j connectivity."""
    try:
        with driver.session() as session:
            session.run("RETURN 1")
        return {"status": "healthy", "neo4j": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@app.post("/orgs", tags=["Ingestion"])
async def create_org(payload: dict = Body(...)):
    """Upserts an Organization node into Neo4j."""
    query = "MERGE (o:Org {id: $id}) SET o.name = $name"
    with driver.session() as session:
        session.run(query, id=payload["id"], name=payload.get("name", "Unknown Org"))
    return {"status": "success"}


@app.post("/topics", tags=["Ingestion"])
async def create_topic(payload: dict = Body(...)):
    """Upserts a Topic node into Neo4j."""
    query = "MERGE (t:Topic {id: $id}) SET t.name = $name"
    with driver.session() as session:
        session.run(query, id=payload["id"], name=payload.get("name", "Unknown Topic"))
    return {"status": "success"}


@app.post("/relationships/{rel_type}", tags=["Ingestion"])
async def create_relationship(rel_type: str, payload: dict = Body(...)):
    """Creates edges (lines) between nodes in Neo4j, guaranteeing they exist first."""
    with driver.session() as session:
        if rel_type == "authored":
            # Using MERGE instead of MATCH prevents silent failures!
            query = """
            MERGE (a:Author {id: $author_id})
            MERGE (w:Work {id: $work_id})
            MERGE (a)-[:AUTHORED]->(w)
            """
            session.run(
                query, author_id=payload["author_id"], work_id=payload["work_id"]
            )

        elif rel_type == "affiliated":
            query = """
            MERGE (a:Author {id: $author_id})
            MERGE (o:Org {id: $org_id})
            MERGE (a)-[:AFFILIATED_WITH]->(o)
            """
            session.run(query, author_id=payload["author_id"], org_id=payload["org_id"])

        elif rel_type == "covers":
            query = """
            MERGE (w:Work {id: $work_id})
            MERGE (t:Topic {id: $topic_id})
            MERGE (w)-[:COVERS]->(t)
            """
            session.run(query, work_id=payload["work_id"], topic_id=payload["topic_id"])

    return {"status": "success"}


# --- 6. Root Endpoint ---


@app.get("/", tags=["System"])
async def root():
    """Root endpoint providing service information."""
    return {
        "title": settings.api_title,
        "version": settings.api_version,
        "status": "online",
    }


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
        logger.error(f"Database error in /stats: {e}")
        raise HTTPException(
            status_code=500, detail=f"Graph database connection error: {str(e)}"
        )


# --- 7. Ingestion Endpoints ---


@app.post("/authors", tags=["Ingestion"])
async def upsert_author(author: AuthorNode):
    """Upserts an Author node into the graph."""
    query = """
    MERGE (a:Author {id: $id})
    SET a.name = $name, a.h_index = $h_index, a.works_count = $works_count
    RETURN a.id
    """
    with driver.session() as session:
        # model_dump() replaces the deprecated dict() method
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
    return {"status": "linked"}


# --- 8. Search & Analysis Endpoints ---


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


@app.get("/viz/author-network/{author_id}", tags=["Visualization"])
async def get_author_network(author_id: str):
    """Returns a JSON structure (nodes/edges) for frontend graph visualization."""
    query = """
    MATCH (n {id: $node_id})
    OPTIONAL MATCH (n)-[r:AUTHORED]-(m)
    OPTIONAL MATCH (m)-[r2:AUTHORED]-(co)
    RETURN n, r, m, co
    LIMIT 50
    """

    with driver.session() as session:
        result = session.run(query, node_id=author_id)
        nodes = []
        edges = []
        node_ids = set()

        for record in result:
            author = record["n"]
            work = record["m"]
            co_author = record["co"]

            # Add Main Author
            if author and author["id"] not in node_ids:
                nodes.append(
                    {
                        "id": author["id"],
                        "label": author["name"],
                        "group": "author",
                        "color": "#ff6b6b",
                    }
                )
                node_ids.add(author["id"])

            # Add Work Node and Edge
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
            if author and work:
                edges.append(
                    {"from": author["id"], "to": work["id"], "label": "AUTHORED"}
                )

            # Add Co-Author Node and Edge (if exists)
            if co_author and co_author["id"] not in node_ids:
                nodes.append(
                    {
                        "id": co_author["id"],
                        "label": co_author["name"],
                        "group": "author",
                        "color": "#ffadad",
                    }
                )
                node_ids.add(co_author["id"])
            if co_author and work:
                edges.append(
                    {"from": co_author["id"], "to": work["id"], "label": "AUTHORED"}
                )

        return {"nodes": nodes, "edges": edges}
