import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import pickle

INPUT_FILE = "aegis_ai_deception_data.json"
INDEX_FILE = "aegis.index"
METADATA_FILE = "aegis_metadata.pkl"
MODEL_NAME = 'all-mpnet-base-v2'

def build_index():
    print("Loading data...")
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            papers = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find {INPUT_FILE}. Did you run the downloader?")
        return

    print(f"Found {len(papers)} papers. Preparing text...")

    #Prepare Text Data
    documents = []
    for p in papers:
        # Handle cases where abstract might be None
        abstract = p.get('abstract') or "" 
        text = f"{p['title']}. {abstract}"
        documents.append(text)

    #Load the AI Model
    print(f"Loading AI Model ({MODEL_NAME})... this might take a minute...")
    model = SentenceTransformer(MODEL_NAME)

    #Generate Embeddings (The "Thinking" Part)
    print("Converting text to vectors (Embeddings)...")
    embeddings = model.encode(documents, show_progress_bar=True)

    #Convert to float32 (FAISS requires this specific format)
    embeddings = np.array(embeddings).astype("float32")
    
    #Create FAISS Index
    print("Building FAISS Index...")
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension) # "Flat" means exact search (perfect for small datasets)
    index.add(embeddings)

    #Save Everything
    print("Saving artifacts to disk...")
    
    #Save the Vector Index
    faiss.write_index(index, INDEX_FILE)
    
    #Save the Metadata (Original text/IDs)
    with open(METADATA_FILE, "wb") as f:
        pickle.dump(papers, f)

    print("\n" + "="*50)
    print(f"SUCCESS! Index built with {index.ntotal} vectors.")
    print(f"   - Vectors saved to: {INDEX_FILE}")
    print(f"   - Metadata saved to: {METADATA_FILE}")
    print("="*50)

if __name__ == "__main__":
    build_index()
    