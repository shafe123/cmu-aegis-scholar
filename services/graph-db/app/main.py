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

# ... (Health and Ingestion endpoints remain the same) ...

@app.get("/viz/author-network/{node_id}", tags=["Visualization"])
async def get_author_network(node_id: str):
    """
    Fetches the local network for any node (Author or Work).
    Returns nodes with a 'details' object for the Frontend Inspector.
    """
    # This query finds the node, its immediate neighbors (m), 
    # and the neighbors of those neighbors (co)
    query = """
    MATCH (n {id: $node_id})
    OPTIONAL MATCH (n)-[r:AUTHORED]-(m)
    OPTIONAL MATCH (m)-[r2:AUTHORED]-(co)
    RETURN n, r, m, co
    LIMIT 50
    """
    
    with driver.session() as session:
        result = session.run(query, node_id=node_id)
        nodes = []
        edges = []
        node_ids = set()
        edge_keys = set()

        for record in result:
            # Process every node returned in the path (n, m, and co)
            for key in ["n", "m", "co"]:
                node = record[key]
                if node and node["id"] not in node_ids:
                    # Check labels to determine if it's an Author or Work
                    is_author = "Author" in node.labels
                    
                    nodes.append({
                        "id": node["id"],
                        "label": node.get("name") if is_author else (node.get("title", "Untitled")[:30] + "..."),
                        "full_title": node.get("title") if not is_author else None,
                        "group": "author" if is_author else "work",
                        "details": {
                            # Standardized keys used by the Frontend
                            "h_index": node.get("h_index", 0) if is_author else None,
                            "works": node.get("works_count", 0) if is_author else None,
                            "year": node.get("year", "N/A") if not is_author else None,
                            "citations": node.get("citation_count", 0) if not is_author else None,
                        }
                    })
                    node_ids.add(node["id"])

            # Add edges between n->m and m->co for the graph lines
            n_ptr, m_ptr, co_ptr = record["n"], record["m"], record["co"]
            if n_ptr and m_ptr:
                ekey = tuple(sorted([n_ptr["id"], m_ptr["id"]]))
                if ekey not in edge_keys:
                    edges.append({"from": n_ptr["id"], "to": m_ptr["id"], "label": "AUTHORED"})
                    edge_keys.add(ekey)
            if m_ptr and co_ptr:
                ekey2 = tuple(sorted([m_ptr["id"], co_ptr["id"]]))
                if ekey2 not in edge_keys:
                    edges.append({"from": m_ptr["id"], "to": co_ptr["id"], "label": "AUTHORED"})
                    edge_keys.add(ekey2)

        return {"nodes": nodes, "edges": edges}