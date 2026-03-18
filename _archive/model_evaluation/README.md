# Embedding Model Evaluation Pipeline

A reproducible evaluation pipeline for testing embedding models on author search/ranking tasks using ground truth data from DTIC.

## Overview

This pipeline evaluates embedding models by:
1. Fetching papers for specified authors from Azure Blob Storage (DTIC data)
2. Creating averaged embeddings for each author based on their paper abstracts
3. Uploading author embeddings to a Milvus vector database
4. Performing searches based on query terms
5. Evaluating results using Mean Reciprocal Rank (MRR) and Normalized Discounted Cumulative Gain (NDCG)

## Components

### Core Scripts

- **`copy_evaluation_works.py`**: Copies authors and their works from the clean container to the subsets/evaluation folder for testing
- **`data_loader.py`**: Fetches DTIC papers for specified authors from Azure Blob Storage
- **`evaluate_embeddings.py`**: Creates embeddings, uploads to Milvus, and evaluates search performance
- **`run_evaluation.py`**: Orchestrates the complete evaluation pipeline

### Configuration

- **`docker-compose.yml`**: Spins up Milvus vector database with dependencies (etcd, MinIO)
- **`requirements.txt`**: Python dependencies
- **`Author Ratings - Overall.csv`**: Ground truth rankings for queries and authors

## Supported Models

The pipeline supports the following embedding models:

1. **sentence-transformers/all-MiniLM-L6-v2** (384 dimensions)
   - Fast and efficient sentence embeddings
   
2. **cointegrated/rubert-tiny2**
   - Tiny Russian BERT model for multilingual support
   
3. **OrcaDB/gte-base-en-v1.5**
   - General Text Embeddings base model v1.5
   
4. **deepvk/USER-bge-m3**
   - Multilingual BGE-M3 model from DeepVK
   
5. **Qwen/Qwen3-Embedding-0.6B**
   - Qwen3 embedding model (0.6B parameters)
   
6. **jinaai/jina-code-embeddings-1.5b**
   - Jina AI code embeddings model (1.5B parameters)

## Prerequisites

1. **Python 3.10+**
2. **Docker & Docker Compose**
3. **Azure Storage Connection String** with access to DTIC publications

## Setup

### 1. Clone the Repository

```bash
cd cmu-aegis-scholar/model_evaluation
```

### 2. Install Python Dependencies

```powershell
# Create a virtual environment (recommended)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt
```

### 3. Start Milvus Vector Database

```powershell
# Start Milvus and its dependencies
docker-compose up -d

# Verify it's running
docker-compose ps

# Wait for health checks to pass (about 60-90 seconds)
```

### 4. Set Azure Storage Connection String

```powershell
# Windows PowerShell
$env:AZURE_STORAGE_CONNECTION_STRING = "your-connection-string-here"

# Or add to .env file
echo "AZURE_STORAGE_CONNECTION_STRING=your-connection-string" > .env
```

## Data Preparation

### Copy Evaluation Data

Before running evaluations, you may want to copy the author and work data to a dedicated evaluation subset:

```powershell
# Preview what will be copied (dry-run)
python copy_evaluation_works.py --dry-run

# Copy both authors and their works to subsets/evaluation/
python copy_evaluation_works.py

# Copy only author files
python copy_evaluation_works.py --authors-only

# Copy only works
python copy_evaluation_works.py --works-only
```

This script:
- Reads author IDs from `Author Ratings - Overall.csv`
- Copies author files from `clean/dtic/authors/` to `subsets/evaluation/authors/` (unless `--works-only`)
- Copies all works by those authors from `clean/dtic/works/` to `subsets/evaluation/works/` (unless `--authors-only`)
- Provides statistics on files copied and works per author

## Usage

### Evaluate a Single Model

```powershell
python run_evaluation.py `
    --model sentence-transformers/all-MiniLM-L6-v2 `
    --ground-truth "Author Ratings - Overall.csv"
```

### Evaluate All Models

```powershell
python run_evaluation.py `
    --all-models `
    --ground-truth "Author Ratings - Overall.csv"
```

### Advanced Options

```powershell
python run_evaluation.py `
    --model sentence-transformers/all-MiniLM-L6-v2 `
    --ground-truth "Author Ratings - Overall.csv" `
    --connection-string "$env:AZURE_STORAGE_CONNECTION_STRING" `
    --milvus-host localhost `
    --milvus-port 19530 `
    --output-dir results `
    --max-blobs 100  # For testing with limited data
```

### Skip Data Fetching (Use Cached Data)

If you've already fetched the author papers:

```powershell
python run_evaluation.py `
    --model sentence-transformers/all-MiniLM-L6-v2 `
    --ground-truth "Author Ratings - Overall.csv" `
    --skip-fetch
```

### Clear Cache

To force re-download of papers:

```powershell
# Delete cache directory
Remove-Item -Recurse -Force cache

# Run with --no-cache flag
python run_evaluation.py `
    --model sentence-transformers/all-MiniLM-L6-v2 `
    --ground-truth "Author Ratings - Overall.csv" `
    --no-cache
```

## Ground Truth CSV Format

The ground truth CSV should have the following structure:

| Column | Description |
|--------|-------------|
| `ID` | Row identifier |
| `Category` | Author category (AI, MilDec, etc.) |
| `Author with search` | Link to author with search query |
| `Author only` | Link to author profile |
| `author_id` | DTIC researcher ID (e.g., `ur.012313314741.93`) |
| `Name` | Author name |
| `Query 1`, `Query 2`, ... | Ground truth rankings (1-5 scale, lower is better) |

Query columns (e.g., "Military deception strategy", "Machine learning of deceptive strategies") contain relevance scores where:
- Lower numbers = more relevant
- 1.0 = highly relevant
- 5.0 = not relevant
- NaN/empty = not evaluated

## Output

### Results Directory Structure

```
results/
├── author_papers.json                          # Cached author papers
├── sentence-transformers_all-MiniLM-L6-v2_results.json
├── OrcaDB_gte-base-en-v1.5_results.json
├── ...
└── summary.json                                # Overall summary
```

### Result File Format

Each result file contains:

```json
{
  "model": "sentence-transformers/all-MiniLM-L6-v2",
  "embedding_dim": 384,
  "avg_mrr": 0.4523,
  "avg_ndcg": 0.6234,
  "queries": [
    {
      "query": "Military deception strategy",
      "mrr": 0.5,
      "ndcg": 0.72,
      "relevant_authors": 10,
      "top_results": [...]
    }
  ]
}
```

### Summary File Format

```json
[
  {
    "model": "sentence-transformers/all-MiniLM-L6-v2",
    "avg_mrr": 0.4523,
    "avg_ndcg": 0.6234,
    "queries_evaluated": 12
  }
]
```

## Evaluation Metrics

### Mean Reciprocal Rank (MRR)

MRR measures how quickly the first relevant result appears:
- MRR = 1.0: First result is relevant
- MRR = 0.5: Second result is relevant
- MRR = 0.25: Fourth result is relevant

Formula: `MRR = 1 / rank_of_first_relevant_result`

### Normalized Discounted Cumulative Gain (NDCG)

NDCG measures the quality of ranking considering relevance scores:
- NDCG = 1.0: Perfect ranking
- NDCG = 0.0: Worst possible ranking

NDCG accounts for:
- Position of relevant results (earlier is better)
- Degree of relevance (highly relevant vs. somewhat relevant)

## Architecture

### Data Flow

```
Azure Blob Storage (DTIC Papers)
    ↓
AuthorDataLoader (data_loader.py)
    ↓
Author Papers JSON (cached)
    ↓
EmbeddingEvaluator (evaluate_embeddings.py)
    ↓
Author Embeddings → Milvus Vector Database
    ↓
Query Evaluation → Metrics (MRR, NDCG)
    ↓
Results JSON Files
```

### Milvus Collection Schema

```python
{
  "author_id": VARCHAR(100),      # Primary key
  "embedding": FLOAT_VECTOR,      # Author's averaged embedding
  "paper_count": INT64,           # Number of papers
  "author_name": VARCHAR(200)     # Author's name
}
```

## How It Works

### 1. Data Fetching

The `AuthorDataLoader` class:
- Connects to Azure Blob Storage
- Lists all DTIC publication files
- Downloads and parses JSON files
- Extracts papers for specified authors using their `researcher_id`
- Caches results locally for faster subsequent runs

### 2. Embedding Creation

For each author:
- Extract all their papers
- Combine title + abstract for each paper
- Create embeddings using the specified model
- Average all paper embeddings to create an author embedding

### 3. Vector Database Upload

- Create a Milvus collection with appropriate schema
- Upload author embeddings with metadata
- Build index for fast similarity search

### 4. Query Evaluation

For each query column in the ground truth CSV:
- Create embedding for the query text
- Search Milvus for top-k similar authors
- Compare results against ground truth rankings
- Calculate MRR and NDCG metrics

## Troubleshooting

### Milvus Connection Issues

```powershell
# Check if Milvus is running
docker-compose ps

# View Milvus logs
docker-compose logs milvus

# Restart Milvus
docker-compose restart milvus
```

### Out of Memory Errors

For large models, you may need to:
1. Reduce batch size in embedding creation
2. Increase Docker memory limits
3. Use a smaller model for testing

### Azure Connection Errors

```powershell
# Verify connection string
echo $env:AZURE_STORAGE_CONNECTION_STRING

# Test Azure connection
az storage container list --connection-string "$env:AZURE_STORAGE_CONNECTION_STRING"
```

### Missing Papers

If authors have no papers:
- Verify the author_id format matches DTIC's `researcher_id`
- Check that papers exist in the blob storage container
- Increase `--max-blobs` limit or remove it entirely

## Performance Optimization

### Use Cached Data

After the first run, use `--skip-fetch` to avoid re-downloading papers:

```powershell
python run_evaluation.py --model MODEL_NAME --ground-truth CSV_PATH --skip-fetch
```

### Limit Data for Testing

Use `--max-blobs` to process only a subset of papers:

```powershell
python run_evaluation.py --model MODEL_NAME --ground-truth CSV_PATH --max-blobs 100
```

### Parallel Evaluation

Run multiple models in parallel using separate terminals:

```powershell
# Terminal 1
python run_evaluation.py --model sentence-transformers/all-MiniLM-L6-v2 --ground-truth CSV_PATH --skip-fetch

# Terminal 2
python run_evaluation.py --model OrcaDB/gte-base-en-v1.5 --ground-truth CSV_PATH --skip-fetch
```

Note: Each model will create its own collection in Milvus.

## Cleanup

### Stop Milvus

```powershell
docker-compose down
```

### Remove Data Volumes

```powershell
docker-compose down -v
```

### Clear Cache

```powershell
Remove-Item -Recurse -Force cache, results
```

## Development

### Adding New Models

Edit `run_evaluation.py` and add to `AVAILABLE_MODELS`:

```python
AVAILABLE_MODELS = {
    "your-model-name": {
        "trust_remote_code": False,
        "description": "Your model description"
    }
}
```

### Custom Evaluation Metrics

Extend the `EmbeddingEvaluator` class in `evaluate_embeddings.py`:

```python
def _calculate_custom_metric(self, search_results, ground_truth):
    # Your metric implementation
    pass
```

## Citation

If you use this evaluation pipeline in your research, please cite:

```
CMU AEGIS Scholar - Embedding Model Evaluation Pipeline
Carnegie Mellon University, 2026
```

## License

See the main repository LICENSE file.

## Support

For questions or issues:
1. Check the troubleshooting section above
2. Review Docker and Milvus logs
3. Open an issue in the repository
