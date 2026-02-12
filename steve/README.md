# Aegis Scholar (Proof of Concept)

A local AI-powered search engine for academic papers, specifically focused on **Artificial Intelligence**, **Deception**, and **Defense Technology**.

This project demonstrates a complete **Retrieval Augmented Generation (RAG)** pipeline, moving from raw data ingestion to vector embeddings and semantic search.

## How It Works

1. **Ingestion (create_golden_dataset.py)**
   - Connects to OpenAlex (a massive open database of 250M+ works).
   - Streams compressed .gz files from Azure Blob Storage.
   - Filters specifically for papers on "Deception," "AI," "Disinformation," and "Cyber Warfare."
   - Reconstructs abstract text from inverted indexes.

2. **Indexing (build_vector_store.py)**
   - Loads the cleaned JSON dataset.
   - Uses sentence-transformers (Model: all-mpnet-base-v2) to generate 768-dimensional vector embeddings for every paper.
   - Stores vectors in a FAISS index for millisecond-speed similarity search.

3. **Search Interface (search_aegis.py)**
   - Accepts natural language queries (e.g., "How to trick neural networks").
   - Converts the query into a vector on the fly.
   - Retrieves the top 5 most semantically similar papers, even if they don't share exact keywords.

---

## Installation

### 1. Clone the Repository
   git clone https://github.com/shafe123/cmu-aegis-scholar.git  
   cd aegis-scholar/steve

### 2. Create a Virtual Environment
   # Windows
   
   `python -m venv venv`  
   `.\venv\Scripts\activate`

   # Mac/Linux
   python3 -m venv venv  
   source venv/bin/activate

### 3. Install Dependencies
   pip install -r requirements.txt
   
   (Note: If you encounter errors with PyTorch or FAISS on Windows, you may need to install the Microsoft Visual C++ Redistributable.)

---

## Usage

You must build the database locally first.

### Step 1: Download & Filter Data
Run the ingestion script to fetch real academic papers (keywords can be adjusted):  
   python create_golden_dataset.py
   
   *Output: aegis_ai_deception_data.json*

### Step 2: Build the Vector Index
Turn those papers into a searchable AI database:  
   python build_vector_store.py
   
   *Output: aegis.index and aegis_metadata.pkl*

### Step 3: Run the Search Engine
Launch the interactive search tool:  
   python search_aegis.py

**Example Queries to Try:**
- "Lying to computers"
- "How to detect deepfakes"
- "Autonomous drone swarms"

---

## Project Structure

- create_golden_dataset.py: ETL pipeline for OpenAlex data.
- build_vector_store.py: Generates embeddings and builds the FAISS index.
- search_aegis.py: The CLI search interface.
- requirements.txt: Python dependencies.
- .gitignore: What is not committed to Git.
