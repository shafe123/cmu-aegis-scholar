"""
Run Model Evaluation Pipeline

Orchestrates the complete evaluation process:
1. Fetches papers for authors from Azure Blob Storage
2. Creates author embeddings using specified model
3. Uploads embeddings to Milvus
4. Evaluates searches against ground truth
5. Calculates MRR and NDCG metrics
"""

import os
import sys
import argparse
import logging
import json
from pathlib import Path
import pandas as pd

from data_loader import AuthorDataLoader
from evaluate_embeddings import EmbeddingEvaluator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Available models with their configurations
AVAILABLE_MODELS = {
    "sentence-transformers/all-MiniLM-L6-v2": {
        "trust_remote_code": False,
        "description": "Fast and efficient sentence embeddings (384 dimensions)"
    },
    "cointegrated/rubert-tiny2": {
        "trust_remote_code": False,
        "description": "Tiny Russian BERT model for multilingual support"
    },
    "OrcaDB/gte-base-en-v1.5": {
        "trust_remote_code": True,
        "description": "General Text Embeddings base model v1.5"
    },
    "deepvk/USER-bge-m3": {
        "trust_remote_code": False,
        "description": "Multilingual BGE-M3 model from DeepVK"
    },
    "Qwen/Qwen3-Embedding-0.6B": {
        "trust_remote_code": True,
        "description": "Qwen3 embedding model (0.6B parameters)"
    },
    "jinaai/jina-code-embeddings-1.5b": {
        "trust_remote_code": False,
        "description": "Jina AI code embeddings model (1.5B parameters)"
    }
}


def load_ground_truth(csv_path: str):
    """Load and validate ground truth CSV."""
    logger.info(f"Loading ground truth from {csv_path}")
    df = pd.read_csv(csv_path)
    
    # Validate required columns
    required_cols = ['author_id', 'Name']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    
    logger.info(f"Loaded {len(df)} authors from ground truth")
    return df


def fetch_author_papers(
    author_ids,
    connection_string,
    output_file,
    max_blobs=None,
    use_cache=True
):
    """Fetch papers for authors from Azure Blob Storage."""
    logger.info("="*70)
    logger.info("STEP 1: Fetching author papers from Azure Blob Storage")
    logger.info("="*70)
    
    # Initialize data loader
    loader = AuthorDataLoader(
        connection_string=connection_string,
        container_name="dtic-publications",
        blob_prefix="dtic/works/",
        cache_dir="cache"
    )
    
    # Fetch papers
    author_papers = loader.fetch_papers_for_authors(
        author_ids=author_ids,
        max_blobs=max_blobs,
        use_cache=use_cache
    )
    
    # Save to file
    loader.save_author_papers(author_papers, output_file)
    
    return author_papers


def evaluate_model(
    model_name,
    trust_remote_code,
    ground_truth_csv,
    author_papers_file,
    collection_name,
    milvus_host,
    milvus_port,
    output_file,
    skip_upload=False
):
    """Evaluate a single model."""
    logger.info("="*70)
    logger.info(f"STEP 2: Evaluating model: {model_name}")
    logger.info("="*70)
    
    # Initialize evaluator
    evaluator = EmbeddingEvaluator(
        model_name=model_name,
        milvus_host=milvus_host,
        milvus_port=milvus_port,
        trust_remote_code=trust_remote_code
    )
    
    if not skip_upload:
        # Load author papers
        logger.info(f"Loading author papers from {author_papers_file}")
        with open(author_papers_file, 'r', encoding='utf-8') as f:
            author_papers = json.load(f)
        
        # Load ground truth to get author names
        df = pd.read_csv(ground_truth_csv)
        author_names = dict(zip(df['author_id'], df['Name']))
        
        # Create embeddings
        author_embeddings = evaluator.create_author_embeddings(author_papers, author_names)
        
        # Calculate paper counts
        author_paper_counts = {aid: len(papers) for aid, papers in author_papers.items()}
        
        # Create collection and upload
        evaluator.create_collection(collection_name, drop_existing=True)
        evaluator.upload_to_milvus(author_embeddings, author_names, author_paper_counts)
    else:
        # Load existing collection
        evaluator.load_collection(collection_name)
    
    # Evaluate
    results = evaluator.evaluate_queries(ground_truth_csv, output_file)
    
    # Cleanup
    evaluator.cleanup()
    
    return results


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Run complete model evaluation pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Evaluate a single model
  python run_evaluation.py --model sentence-transformers/all-MiniLM-L6-v2 \\
      --ground-truth "Author Ratings - Overall.csv" \\
      --connection-string "$AZURE_STORAGE_CONNECTION_STRING"
  
  # Evaluate all models
  python run_evaluation.py --all-models \\
      --ground-truth "Author Ratings - Overall.csv" \\
      --connection-string "$AZURE_STORAGE_CONNECTION_STRING"
  
  # Use cached papers and skip data fetching
  python run_evaluation.py --model sentence-transformers/all-MiniLM-L6-v2 \\
      --ground-truth "Author Ratings - Overall.csv" \\
      --skip-fetch
        """
    )
    
    # Model selection
    model_group = parser.add_mutually_exclusive_group(required=True)
    model_group.add_argument(
        "--model",
        type=str,
        choices=list(AVAILABLE_MODELS.keys()),
        help="Name of the embedding model to evaluate"
    )
    model_group.add_argument(
        "--all-models",
        action="store_true",
        help="Evaluate all available models"
    )
    
    # Required arguments
    parser.add_argument(
        "--ground-truth",
        type=str,
        required=True,
        help="Path to ground truth CSV file"
    )
    
    # Optional arguments
    parser.add_argument(
        "--connection-string",
        type=str,
        help="Azure Storage connection string (or use AZURE_STORAGE_CONNECTION_STRING env var)"
    )
    parser.add_argument(
        "--milvus-host",
        type=str,
        default="localhost",
        help="Milvus server host (default: localhost)"
    )
    parser.add_argument(
        "--milvus-port",
        type=int,
        default=19530,
        help="Milvus server port (default: 19530)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="results",
        help="Directory to save results (default: results)"
    )
    parser.add_argument(
        "--max-blobs",
        type=int,
        help="Maximum number of blob files to process (for testing)"
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Skip fetching papers (use existing author_papers.json)"
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Don't use cached blob data"
    )
    
    args = parser.parse_args()
    
    try:
        # Get connection string
        connection_string = args.connection_string or os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        
        if not args.skip_fetch and not connection_string:
            raise ValueError(
                "Azure Storage connection string required. Provide via --connection-string "
                "or set AZURE_STORAGE_CONNECTION_STRING environment variable."
            )
        
        # Create output directory
        output_dir = Path(args.output_dir)
        output_dir.mkdir(exist_ok=True)
        
        # Load ground truth
        df = load_ground_truth(args.ground_truth)
        author_ids = df['author_id'].tolist()
        
        # Step 1: Fetch author papers (if not skipped)
        author_papers_file = output_dir / "author_papers.json"
        
        if not args.skip_fetch:
            author_papers = fetch_author_papers(
                author_ids=author_ids,
                connection_string=connection_string,
                output_file=str(author_papers_file),
                max_blobs=args.max_blobs,
                use_cache=not args.no_cache
            )
        else:
            logger.info("Skipping data fetch (using existing author_papers.json)")
            if not author_papers_file.exists():
                raise FileNotFoundError(f"No existing author papers file found at {author_papers_file}")
        
        # Step 2: Evaluate model(s)
        models_to_evaluate = []
        if args.all_models:
            models_to_evaluate = list(AVAILABLE_MODELS.keys())
        else:
            models_to_evaluate = [args.model]
        
        logger.info(f"\nEvaluating {len(models_to_evaluate)} model(s)")
        
        all_results = {}
        for model_name in models_to_evaluate:
            logger.info(f"\n{'='*70}")
            logger.info(f"Evaluating: {model_name}")
            logger.info(f"Description: {AVAILABLE_MODELS[model_name]['description']}")
            logger.info(f"{'='*70}")
            
            # Generate output filename
            model_safe_name = model_name.replace("/", "_").replace(":", "_")
            output_file = output_dir / f"{model_safe_name}_results.json"
            collection_name = f"eval_{model_safe_name}"
            
            # Evaluate
            results = evaluate_model(
                model_name=model_name,
                trust_remote_code=AVAILABLE_MODELS[model_name]["trust_remote_code"],
                ground_truth_csv=args.ground_truth,
                author_papers_file=str(author_papers_file),
                collection_name=collection_name,
                milvus_host=args.milvus_host,
                milvus_port=args.milvus_port,
                output_file=str(output_file)
            )
            
            all_results[model_name] = results
        
        # Generate summary report
        logger.info("\n" + "="*70)
        logger.info("FINAL SUMMARY")
        logger.info("="*70)
        
        summary_data = []
        for model_name, results in all_results.items():
            avg_mrr = sum(r["mrr"] for r in results.values()) / len(results)
            avg_ndcg = sum(r["ndcg"] for r in results.values()) / len(results)
            
            summary_data.append({
                "model": model_name,
                "avg_mrr": avg_mrr,
                "avg_ndcg": avg_ndcg,
                "queries_evaluated": len(results)
            })
            
            logger.info(f"\n{model_name}:")
            logger.info(f"  Average MRR:  {avg_mrr:.4f}")
            logger.info(f"  Average NDCG: {avg_ndcg:.4f}")
            logger.info(f"  Queries:      {len(results)}")
        
        # Save summary
        summary_file = output_dir / "summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, indent=2)
        
        logger.info(f"\nSummary saved to {summary_file}")
        logger.info("="*70)
        logger.info("Evaluation pipeline complete!")
        logger.info("="*70)
        
    except Exception as e:
        logger.error(f"Error during evaluation: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
