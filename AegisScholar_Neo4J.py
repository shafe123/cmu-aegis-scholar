import io
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from azure.storage.blob import BlobServiceClient
from neo4j import GraphDatabase
from openai import OpenAI
from sklearn.manifold import TSNE

# We'll have to run pip install neo4j pandas matplotlib seaborn azure-storage-blob openai scikit-learn numpy

# --- CONFIGURATION ---
ACCOUNT_URL = "https://aegisscholardata.blob.core.windows.net/"
SAS_TOKEN = "sv=2024-11-04&ss=bfqt&srt=sco&sp=rwdlacupiytfx&se=2026-05-30T08:31:15Z&st=2026-02-12T01:16:15Z&spr=https&sig=pU5C5a%2B%2BxE1zvMMv3vjUqjlJXC9dMgpsVyM0V%2FfuEIo%3D" 
CONTAINER_NAME = "lowercase blob storage name" 
BLOB_NAME = "filename .csv or .json"

AURA_URI = "neo4j+s://28dcf768.databases.neo4j.io"
AURA_USER = "neo4j"
AURA_PASSWORD = "jlpBpd2h6b2UTkNchU6jZ71Zp01a6sqIIWTCVOi5CHY"

# We may want to use a different LLM here which would change the 1536 dimensions used later on - OpenAI and Google have low costs, HuggingFace is free(best for DTIC data)
OPENAI_API_KEY = "your-openai-api-key"
client = OpenAI(api_key=OPENAI_API_KEY)

# --- VECTOR UTILITIES ---
def get_embedding(text):
    '''Fucntion takes a string and send it to LLM. LLM returns a list that represents the semantic fingerprint'''
    if not text or not isinstance(text, str): return None
    try:
        return client.embeddings.create(input=[text], model="text-embedding-3-small").data[0].embedding
    except Exception as e:
        print(f"Embedding error: {e}")
        return None

# --- SEARCH FUNCTION ---
def semantic_search(driver, user_query, top_k=5):
    """Finds papers semantically related to a search string and create a Vector Index."""
    query_vector = get_embedding(user_query)
    if not query_vector: return
    
    # Cypher for Vector Similarity Search
    vector_search_query = """
    CALL db.index.vector.queryNodes('paper_embeddings', $k, $vector)
    YIELD node, score
    RETURN node.title AS title, score
    ORDER BY score DESC
    """
    
    with driver.session() as session:
        results = session.run(vector_search_query, vector=query_vector, k=top_k)
        print(f"\n--- Semantic Search Results for: '{user_query}' ---")
        for record in results:
            print(f"Score: {record['score']:.4f} | Title: {record['title']}")

# --- INGESTION & VISUALIZATION ---
def ingest_data(driver, df):
    '''This acts as a smart create, if the author or paper exists, it does nothing, otherwise it creates them. Prevents duplicates.'''
    index_setup = """
    CREATE VECTOR INDEX paper_embeddings IF NOT EXISTS
    FOR (p:Paper) ON (p.embedding)
    OPTIONS {indexConfig: {
      `vector.dimensions`: 1536,
      `vector.similarity_function`: 'cosine'
    }}
    """
    ingest_query = """
    UNWIND $rows AS row
    MERGE (p:Paper {id: row.paper_id})
    SET p.title = row.title, p.embedding = row.embedding
    MERGE (a:Author {name: row.author_name})
    MERGE (o:Organization {name: row.org_name})
    MERGE (c:Country {name: row.country_name})
    MERGE (a)-[:AUTHORED]->(p)
    MERGE (a)-[:AFFILIATED_WITH]->(o)
    MERGE (o)-[:BASED_IN]->(c)
    """
    print("Vectorizing titles...")
    df['embedding'] = df['title'].apply(get_embedding)
    records = df.to_dict('records')

    with driver.session() as session:
        '''To prevent connection from crashing, we run it with chunks of 100'''
        session.run(index_setup)
        for i in range(0, len(records), 100):
            session.run(ingest_query, rows=records[i:i+100])
        print("Ingestion complete.")

def run_visualizations(driver, df):
    '''Run Cypher query and return that back to a Pandas DF to create vector graphics.'''
    #Standard Chart: Authors by Organization
    query_org = "MATCH (a:Author)-[:AFFILIATED_WITH]->(o:Organization) RETURN o.name AS Organization, count(a) AS Count ORDER BY Count DESC LIMIT 10"
    res_org, _, _ = driver.execute_query(query_org)
    df_plot = pd.DataFrame([dict(r) for r in res_org])
    
    if not df_plot.empty:
        plt.figure(figsize=(10, 6))
        sns.barplot(data=df_plot, x='Count', y='Organization', palette='viridis')
        plt.title("Top Organizations")
        plt.savefig("authors_by_org.svg", format="svg")
        plt.show()

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    try:
        # Azure Extract
        blob_service_client = BlobServiceClient(account_url=ACCOUNT_URL, credential=SAS_TOKEN)
        blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=BLOB_NAME)
        data = blob_client.download_blob().readall()
        df = pd.read_csv(io.BytesIO(data)) if BLOB_NAME.endswith('.csv') else pd.read_json(io.BytesIO(data))

        # Neo4j Load
        driver = GraphDatabase.driver(AURA_URI, auth=(AURA_USER, AURA_PASSWORD))
        ingest_data(driver, df)
        
        # Visualize
        run_visualizations(driver, df)

        # Example Search - They query turns into a vector and ask Neo4j what nodes ahve the closest mathematical vector.
        semantic_search(driver, "Innovative defense technologies and logistics")

        driver.close()
    except Exception as e:
        print(f"Error: {e}")