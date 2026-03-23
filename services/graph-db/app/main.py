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

@app.get("/viz/author-network/{author_id}", tags=["Visualization"])
async def get_author_network(author_id: str):
    """
    Returns a JSON structure specifically for frontend graph libraries.
    Matches: (Author)-[:AUTHORED]->(Work)<-[:AUTHORED]-(CoAuthor)
    """
    query = """
    MATCH (a:Author {id: $author_id})-[:AUTHORED]->(w:Work)
    OPTIONAL MATCH (w)<-[:AUTHORED]-(co:Author)
    WHERE co.id <> $author_id
    RETURN a, w, co
    LIMIT 50
    """
    with driver.session() as session:
        result = session.run(query, author_id=author_id)
        nodes = []
        edges = []
        node_ids = set()

        for record in result:
            author = record["a"]
            work = record["w"]
            co_author = record["co"]

            # Add Main Author
            if author["id"] not in node_ids:
                nodes.append({"id": author["id"], "label": author["name"], "group": "author", "color": "#ff6b6b"})
                node_ids.add(author["id"])

            # Add Work Node and Edge
            if work["id"] not in node_ids:
                nodes.append({"id": work["id"], "label": work["title"][:30] + "...", "group": "work", "color": "#4ecdc4"})
                node_ids.add(work["id"])
            edges.append({"from": author["id"], "to": work["id"], "label": "AUTHORED"})

            # Add Co-Author Node and Edge
            if co_author and co_author["id"] not in node_ids:
                nodes.append({"id": co_author["id"], "label": co_author["name"], "group": "author", "color": "#ffadad"})
                node_ids.add(co_author["id"])
            if co_author:
                edges.append({"from": co_author["id"], "to": work["id"], "label": "AUTHORED"})

        return {"nodes": nodes, "edges": edges}