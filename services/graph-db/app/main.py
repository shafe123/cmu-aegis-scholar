from fastapi import FastAPI, HTTPException
from neo4j import GraphDatabase
from app.config import settings
from app.schemas import AuthorNode, WorkNode, OrgNode, TopicNode, AuthorWorkRel, AuthorOrgRel
import logging

app = FastAPI(title=settings.api_title)
driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))

@app.on_event("shutdown")
def close_driver():
    driver.close()

# --- UPSERT ENDPOINTS ---

@app.post("/authors", tags=["Ingestion"])
async def upsert_author(author: AuthorNode):
    query = """
    MERGE (a:Author {id: $id})
    SET a.name = $name, a.h_index = $h_index, a.works_count = $works_count
    RETURN a.id
    """
    with driver.session() as session:
        session.run(query, **author.dict())
    return {"status": "success", "id": author.id}

@app.post("/works", tags=["Ingestion"])
async def upsert_work(work: WorkNode):
    query = """
    MERGE (w:Work {id: $id})
    SET w.title = $title, w.year = $year, w.citation_count = $citation_count
    RETURN w.id
    """
    with driver.session() as session:
        session.run(query, **work.dict())
    return {"status": "success", "id": work.id}

# --- RELATIONSHIP ENDPOINTS ---

@app.post("/relationships/authored", tags=["Relationships"])
async def link_author_work(rel: AuthorWorkRel):
    query = """
    MATCH (a:Author {id: $author_id})
    MATCH (w:Work {id: $work_id})
    MERGE (a)-[:AUTHORED]->(w)
    """
    with driver.session() as session:
        session.run(query, author_id=rel.author_id, work_id=rel.work_id)
    return {"status": "linked"}

# --- SEARCH ENDPOINTS (For aegis-scholar-api) ---

@app.get("/authors/{author_id}/collaborators")
async def get_collaborators(author_id: str):
    """The 'Collaborators of my Collaborators' query from your document."""
    query = """
    MATCH (a:Author {id: $author_id})-[:AUTHORED]->(w:Work)<-[:AUTHORED]-(collab:Author)
    WHERE a <> collab
    RETURN DISTINCT collab.name as name, collab.id as id
    """
    with driver.session() as session:
        result = session.run(query, author_id=author_id)
        return [dict(record) for record in result]