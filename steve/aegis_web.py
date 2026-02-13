import streamlit as st
import faiss
import pickle
import numpy as np
from sentence_transformers import SentenceTransformer
import os

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Aegis Scholar", page_icon="🛡️", layout="centered")

# --- PATHS ---
INDEX_FILE = "aegis.index"
METADATA_FILE = "aegis_metadata.pkl"
MODEL_NAME = 'all-mpnet-base-v2'

# --- CACHED LOADING FUNCTION ---
@st.cache_resource
def load_data():
    """
    Loads the model and data once, then keeps it in memory.
    """
    if not os.path.exists(INDEX_FILE) or not os.path.exists(METADATA_FILE):
        st.error(f"Files not found! Make sure {INDEX_FILE} and {METADATA_FILE} exist.")
        return None, None, None

    model = SentenceTransformer(MODEL_NAME)
    index = faiss.read_index(INDEX_FILE)
    with open(METADATA_FILE, "rb") as f:
        metadata = pickle.load(f)
        
    return model, index, metadata

# --- SEARCH FUNCTION ---
def search(query, model, index, metadata, k=5):
    query_vector = model.encode([query])
    D, I = index.search(np.array(query_vector).astype("float32"), k)
    
    results = []
    for i, idx in enumerate(I[0]):
        if idx != -1:
            item = metadata[idx]
            score = D[0][i]
            results.append((item, score))
    return results

# --- MAIN APP UI ---
def main():
    st.title("Aegis Scholar")
    st.caption("AI-Powered Semantic Search")

    # Load data (cached)
    with st.spinner("Loading AI Brain..."):
        model, index, metadata = load_data()

    if not model:
        return

    # Search Bar
    query = st.text_input("Enter a research question:", placeholder="e.g., 'How to detect deepfakes' or 'Lying to computers'")

    if query:
        results = search(query, model, index, metadata)
        
        st.markdown("---")
        st.subheader(f"Top {len(results)} Results")
        
        for i, (paper, score) in enumerate(results):
            # Clean up the ID/Link
            raw_id = paper.get('id', '')
            clean_link = raw_id if raw_id.startswith("http") else f"https://openalex.org/{raw_id}"
            
            # Create a clickable card for each result
            with st.container():
                st.markdown(f"### {i+1}. [{paper.get('title', 'Untitled')}]({clean_link})")
                
                col1, col2 = st.columns([1, 4])
                with col1:
                    st.caption(f"**{paper.get('publication_year', 'N/A')}**")
                    st.caption(f"**Citations:** {paper.get('cited_by_count', 0)}")
                    st.caption(f"**Dist:** {score:.2f}")
                
                with col2:
                    abstract = paper.get('abstract')
                    if abstract:
                        # Use an expander so long abstracts don't clutter the page
                        with st.expander("Read Abstract"):
                            st.write(abstract)
                    else:
                        st.info("No abstract available.")
                
                st.markdown("---")

if __name__ == "__main__":
    main()