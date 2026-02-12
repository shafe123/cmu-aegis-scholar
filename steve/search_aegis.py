import faiss
import pickle
import numpy as np
from sentence_transformers import SentenceTransformer
import time
import os

INDEX_FILE = "aegis.index"
METADATA_FILE = "aegis_metadata.pkl"
MODEL_NAME = 'all-mpnet-base-v2'

def load_system():
    print("Loading Aegis Scholar System...")
    start_time = time.time()
    
    if not os.path.exists(INDEX_FILE) or not os.path.exists(METADATA_FILE):
        print(f"Error: Could not find {INDEX_FILE} or {METADATA_FILE}.")
        print("   Did you run 'build_vector_store.py'?")
        return None, None, None

    # Load the Model
    model = SentenceTransformer(MODEL_NAME)
    
    #Load the Index
    index = faiss.read_index(INDEX_FILE)
    
    #Load the Metadata
    with open(METADATA_FILE, "rb") as f:
        metadata = pickle.load(f)
        
    print(f"System Ready! ({time.time() - start_time:.2f}s)")
    return model, index, metadata

def search(query, model, index, metadata, k=5):
    """
    Searches the vector database for the top k most similar papers.
    """
    #Vectorize the Query
    query_vector = model.encode([query])
    
    #Search FAISS
    # D = Distances (how similar?), I = Indices (which paper ID?)
    D, I = index.search(np.array(query_vector).astype("float32"), k)
    
    results = []
    for i, idx in enumerate(I[0]):
        if idx != -1: # FAISS returns -1 if it doesn't find enough neighbors
            item = metadata[idx]
            score = D[0][i]
            results.append((item, score))
            
    return results

def main():
    # Load everything once at the start
    model, index, metadata = load_system()
    
    if not model:
        return # Stop if loading failed
    
    print("\n" + "="*60)
    print("WELCOME TO AEGIS SCHOLAR (LOCAL PILOT)")
    print("Type 'exit' to quit.")
    print("="*60)
    
    while True:
        try:
            query = input("\n🔎 Enter your research question: ")
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        
        if query.lower() in ['exit', 'quit']:
            print("Goodbye!")
            break
            
        if not query.strip():
            continue
            
        print(f"   Searching for: '{query}'...")
        results = search(query, model, index, metadata)
        
        print(f"\n   --- TOP {len(results)} RESULTS ---")
        for i, (paper, score) in enumerate(results):
            # Print Title
            print(f"\n   {i+1}. [Dist: {score:.2f}] {paper.get('title', 'Unknown Title')}")
            
            # Print Stats
            pub_year = paper.get('publication_year', 'N/A')
            citations = paper.get('cited_by_count', 0)
            print(f"      Published: {pub_year} | Citations: {citations}")
            
            abstract_text = paper.get('abstract')
            if abstract_text:
                # Limit to 200 chars
                print(f"      Abstract: {abstract_text[:200]}...") 
            else:
                print(f"      Abstract: [No abstract available]")
            
            raw_id = paper.get('id', '')
            if raw_id.startswith("https://openalex.org/"):
                print(f"      Link: {raw_id}")
            else:
                print(f"      Link: https://openalex.org/{raw_id}")

if __name__ == "__main__":
    main()