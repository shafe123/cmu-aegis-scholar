import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Body, HTTPException
from neo4j import GraphDatabase


from app.config import settings
from app.schemas import AuthorNode, AuthorWorkRel, WorkNode

# --- 1. Setup Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 2. Database Driver Initialization ---
driver = GraphDatabase.driver(
    settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
)


# --- 3. Application Lifespan (Startup/Shutdown) ---
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
        logger.error("Database error in /stats: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Graph database connection error: {str(e)}"
        )


# --- 7. Ingestion Endpoints ---


@app.post("/authors", tags=["Ingestion"])
async def upsert_author(author: AuthorNode):
    """Upserts an Author node into the graph."""
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
    
    # 1. Safely extract the 4-digit year from the publication_date string
    calculated_year = "N/A"
    if work.year:
        calculated_year = str(work.year)
    elif work.publication_date and len(work.publication_date) >= 4:
        calculated_year = str(work.publication_date)[:4]

    # 2. Provide a fallback if abstract is missing
    safe_abstract = work.abstract if work.abstract else "No abstract available."

    query = """
    MERGE (w:Work {id: $id})
    SET w.title = $title, 
        w.year = $year, 
        w.abstract = $abstract,
        w.citation_count = $citation_count
    RETURN w.id
    """
    with driver.session() as session:
        session.run(
            query, 
            id=work.id,
            title=work.title,
            year=calculated_year,
            abstract=safe_abstract,
            citation_count=work.citation_count or 0
        )
    return {"status": "success", "id": work.id}


@app.post("/relationships/authored", tags=["Relationships"])
async def link_author_work(rel: AuthorWorkRel):
    """Creates an AUTHORED relationship between an Author and a Work."""
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


# --- 8. Search & Analysis Endpoints ---


@app.get("/authors/{author_id}/collaborators", tags=["Analysis"])
@app.get("/authors/{author_id}/collaborators", tags=["Analysis"])
async def get_collaborators(author_id: str):
    """Finds researchers who have shared works with the given author."""
    """Finds researchers who have shared works with the given author."""
    query = """
    MATCH (a:Author {id: $id})-[:AUTHORED]->(w:Work)<-[:AUTHORED]-(collab:Author)
    MATCH (a:Author {id: $id})-[:AUTHORED]->(w:Work)<-[:AUTHORED]-(collab:Author)
    WHERE a <> collab
    RETURN DISTINCT collab.name as name, collab.id as id
    """
    with driver.session() as session:
        result = session.run(query, id=author_id)
        result = session.run(query, id=author_id)
        return [dict(record) for record in result]

@app.get("/authors/{author_id}", tags=["Analysis"])
async def get_author_profile(author_id: str):
    """Fetches full author profile including their organizations and total works."""
    query = """
    MATCH (a:Author {id: $id})
    OPTIONAL MATCH (a)-[:AFFILIATED_WITH]->(o:Org)
    OPTIONAL MATCH (a)-[:AUTHORED]->(w:Work)
    RETURN a, collect(DISTINCT o) as orgs, count(DISTINCT w) as total_works
    """
    with driver.session() as session:
        result = session.run(query, id=author_id)
        record = result.single()
        
        if not record or not record["a"]:
            raise HTTPException(status_code=404, detail="Author not found in Graph DB")
            
        author_node = record["a"]
        
        # Clean up the organizations list (ignore empty ones)
        organizations = [
            {"id": org["id"], "name": org.get("name", "Unknown")} 
            for org in record["orgs"] if org
        ]
        
        return {
            "id": author_node["id"],
            "name": author_node.get("name", "Unknown Name"),
            "h_index": author_node.get("h_index", 0),
            "works_count": record["total_works"],
            "organizations": organizations
        }

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

    def generate_mock_email(name):
        if not name or name == "Unknown":
            return "No contact info"
        # Turns "John Doe" into "john.doe@aegis-research.mil > will be @university.edu after next reload"
        clean_name = name.lower().replace(".", "").replace("-", "").split()
        if len(clean_name) >= 2:
            return f"{clean_name[0]}.{clean_name[-1]}@university.edu"
        return f"{clean_name[0]}@university.edu"

    with driver.session() as session:
        result = session.run(query, node_id=author_id)
        nodes, edges, node_ids = [], [], set()
        
        # Track works per author to dynamically generate the 'Total Works' count
        author_works_count = {}

        for record in result:
            author, work, co_author = record["n"], record["m"], record["co"]

            # Count works dynamically for the main author and co-authors
            if author and work:
                author_works_count[author["id"]] = author_works_count.get(author["id"], 0) + 1
            if co_author and work:
                author_works_count[co_author["id"]] = author_works_count.get(co_author["id"], 0) + 1

            if author and author["id"] not in node_ids:
                author_name = author.get("name", "Unknown")
                nodes.append({
                    "id": author["id"],
                    "label": author_name,
                    "full_title": author_name,
                    "group": "author",
                    "color": "#ff6b6b",
                    "details": {
                        "works": author.get("works_count") or author.get("num_works") or 0,
                        "email": author.get("email") or generate_mock_email(author_name)
                    }
                })
                node_ids.add(author["id"])

            if work and work["id"] not in node_ids:
                # Safely pull year and abstract checking multiple common dataset keys
                work_year = work.get("year") or work.get("published_year") or work.get("publication_date", "N/A")
                if isinstance(work_year, str) and len(work_year) > 4:
                    work_year = work_year[:4] # Extract just the year if it's a full date string

                work_abstract = work.get("abstract") or work.get("summary") or "No abstract available in dataset."

                nodes.append({
                    "id": work["id"],
                    "label": work.get("title", "Untitled")[:30] + "...",
                    "full_title": work.get("title", "Untitled"),
                    "group": "work",
                    "color": "#4ecdc4",
                    "details": {
                        "year": work_year,
                        "abstract": work_abstract
                    }
                })
                node_ids.add(work["id"])
                
            if author and work:
                edges.append({"from": author["id"], "to": work["id"], "label": "AUTHORED"})

            if co_author and co_author["id"] not in node_ids:
                co_name = co_author.get("name", "Unknown")
                nodes.append({
                    "id": co_author["id"],
                    "label": co_name,
                    "full_title": co_name,
                    "group": "author",
                    "color": "#ffadad",
                    "details": {
                        "works": co_author.get("works_count") or co_author.get("num_works") or 0,
                        "email": co_author.get("email") or generate_mock_email(co_name)
                    }
                })
                node_ids.add(co_author["id"])
                
            if co_author and work:
                edges.append({"from": co_author["id"], "to": work["id"], "label": "AUTHORED"})

        # Second pass: Update the works count dynamically based on the relationships we found
        for node in nodes:
            if node["group"] == "author" and node["details"]["works"] == 0:
                node["details"]["works"] = author_works_count.get(node["id"], 1)

        return {"nodes": nodes, "edges": edges}