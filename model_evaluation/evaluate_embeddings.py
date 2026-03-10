"""
Embedding Model Evaluation Script

Evaluates embedding models on author search/ranking tasks using ground truth CSV.
Calculates Mean Reciprocal Rank (MRR) and Normalized Discounted Cumulative Gain (NDCG).
"""

import os
# Suppress transformers warnings and progress bars
os.environ['TRANSFORMERS_VERBOSITY'] = 'error'
os.environ['TRANSFORMERS_NO_ADVISORY_WARNINGS'] = '1'
os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'
os.environ['TQDM_DISABLE'] = '1'

import json
import argparse
import logging
import uuid
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from pymilvus import connections, Collection, utility, DataType, FieldSchema, CollectionSchema
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Reduce ML library logging verbosity
logging.getLogger('sentence_transformers').setLevel(logging.WARNING)
logging.getLogger('transformers').setLevel(logging.WARNING)
logging.getLogger('torch').setLevel(logging.WARNING)
logging.getLogger('pymilvus').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('huggingface_hub').setLevel(logging.WARNING)


def convert_researcher_id_to_author_guid(researcher_id: str) -> str:
    """
    Convert DTIC researcher ID to author GUID.
    
    Args:
        researcher_id: DTIC researcher ID (e.g., ur.012313314741.93)
        
    Returns:
        Author GUID (e.g., author_a5db27b5-1f1e-5378-90d1-a3af003ebbe0)
    """
    namespace = uuid.UUID('00000000-0000-0000-0000-000000000002')
    author_uuid = uuid.uuid5(namespace, researcher_id)
    return f"author_{author_uuid}"


class EmbeddingEvaluator:
    """
    Evaluates embedding models on author retrieval tasks.
    """
    
    def __init__(
        self,
        model_name: str,
        milvus_host: str = "localhost",
        milvus_port: int = 19530,
        trust_remote_code: bool = False
    ):
        """
        Initialize the evaluator.
        
        Args:
            model_name: Name of the embedding model to use
            milvus_host: Milvus server host
            milvus_port: Milvus server port
            trust_remote_code: Whether to trust remote code when loading model
        """
        self.model_name = model_name
        self.milvus_host = milvus_host
        self.milvus_port = milvus_port
        self.trust_remote_code = trust_remote_code
        
        # Detect device
        if torch.cuda.is_available():
            self.device = 'cuda'
            logger.info(f"GPU detected: {torch.cuda.get_device_name(0)}")
        else:
            self.device = 'cpu'
            logger.info("No GPU detected, using CPU")
        
        # Load embedding model
        logger.info(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name, trust_remote_code=trust_remote_code, device=self.device)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        logger.info(f"Model loaded. Embedding dimension: {self.embedding_dim}")
        
        # Connect to Milvus
        logger.info(f"Connecting to Milvus at {milvus_host}:{milvus_port}")
        connections.connect(host=milvus_host, port=milvus_port)
        logger.info("Connected to Milvus")
        
        self.collection = None
    
    def create_collection(self, collection_name: str, drop_existing: bool = True):
        """
        Create a Milvus collection for author embeddings.
        
        Args:
            collection_name: Name of the collection
            drop_existing: Whether to drop existing collection
        """
        # Drop existing collection if requested
        if drop_existing and utility.has_collection(collection_name):
            logger.info(f"Dropping existing collection: {collection_name}")
            utility.drop_collection(collection_name)
        
        # Define schema
        fields = [
            FieldSchema(name="author_id", dtype=DataType.VARCHAR, is_primary=True, max_length=100),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.embedding_dim),
            FieldSchema(name="paper_count", dtype=DataType.INT64),
            FieldSchema(name="author_name", dtype=DataType.VARCHAR, max_length=200)
        ]
        
        schema = CollectionSchema(fields=fields, description="Author embeddings")
        
        # Create collection
        logger.info(f"Creating collection: {collection_name}")
        self.collection = Collection(name=collection_name, schema=schema)
        
        # Create index
        index_params = {
            "metric_type": "L2",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128}
        }
        
        logger.info("Creating index on embedding field...")
        self.collection.create_index(field_name="embedding", index_params=index_params)
        logger.info("Collection created successfully")
    
    def load_collection(self, collection_name: str):
        """
        Load an existing Milvus collection.
        
        Args:
            collection_name: Name of the collection
        """
        if not utility.has_collection(collection_name):
            raise ValueError(f"Collection '{collection_name}' does not exist")
        
        logger.info(f"Loading collection: {collection_name}")
        self.collection = Collection(name=collection_name)
        self.collection.load()
        logger.info("Collection loaded successfully")
    
    def create_author_embeddings(
        self,
        author_papers: Dict[str, List[Dict]],
        author_names: Dict[str, str]
    ) -> Dict[str, np.ndarray]:
        """
        Create averaged embeddings for each author based on their papers.
        
        Args:
            author_papers: Dictionary mapping author_id to list of papers
            author_names: Dictionary mapping author_id to author name
            
        Returns:
            Dictionary mapping author_id to averaged embedding vector
        """
        author_embeddings = {}
        
        logger.info(f"Creating embeddings for {len(author_papers)} authors...")
        
        for author_id, papers in author_papers.items():
            if not papers:
                logger.warning(f"No papers found for author {author_id}")
                continue
            
            # Extract abstracts
            abstracts = []
            for paper in papers:
                abstract = paper.get('abstract', '')
                
                if abstract and isinstance(abstract, str) and len(abstract.strip()) > 0:
                    # Combine title and abstract
                    title = paper.get('title', '')
                    text = f"{title}. {abstract}".strip()
                    abstracts.append(text)
            
            if not abstracts:
                logger.warning(f"No valid abstracts found for author {author_id}")
                continue
            
            # Create embeddings - encode each paper individually to avoid batching issues
            logger.info(f"  {author_id} ({author_names.get(author_id, 'Unknown')}): {len(abstracts)} papers")
            paper_embeddings = []
            for abstract_text in abstracts:
                embedding = self.model.encode(abstract_text, show_progress_bar=False)
                paper_embeddings.append(embedding)
            
            # Average embeddings
            avg_embedding = np.mean(paper_embeddings, axis=0)
            author_embeddings[author_id] = avg_embedding
        
        logger.info(f"Created embeddings for {len(author_embeddings)} authors")
        return author_embeddings
    
    def upload_to_milvus(
        self,
        author_embeddings: Dict[str, np.ndarray],
        author_names: Dict[str, str],
        author_paper_counts: Dict[str, int]
    ):
        """
        Upload author embeddings to Milvus.
        
        Args:
            author_embeddings: Dictionary mapping author_id to embedding
            author_names: Dictionary mapping author_id to name
            author_paper_counts: Dictionary mapping author_id to paper count
        """
        if self.collection is None:
            raise ValueError("No collection loaded. Call create_collection() or load_collection() first.")
        
        # Prepare data for insertion
        author_ids = []
        embeddings = []
        paper_counts = []
        names = []
        
        for author_id, embedding in author_embeddings.items():
            author_ids.append(author_id)
            embeddings.append(embedding.tolist())
            paper_counts.append(author_paper_counts.get(author_id, 0))
            names.append(author_names.get(author_id, "Unknown"))
        
        # Insert data
        logger.info(f"Uploading {len(author_ids)} author embeddings to Milvus...")
        data = [author_ids, embeddings, paper_counts, names]
        self.collection.insert(data)
        self.collection.flush()
        
        # Load collection for searching
        self.collection.load()
        logger.info("Upload complete")
    
    def search(self, query: str, top_k: int = 100) -> List[Tuple[str, float]]:
        """
        Search for authors matching a query.
        
        Args:
            query: Search query text
            top_k: Number of results to return
            
        Returns:
            List of (author_id, distance) tuples
        """
        if self.collection is None:
            raise ValueError("No collection loaded")
        
        # Create query embedding
        query_embedding = self.model.encode(query)
        
        # Search
        search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
        results = self.collection.search(
            data=[query_embedding.tolist()],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            output_fields=["author_id", "author_name"]
        )
        
        # Extract results
        matches = []
        for hit in results[0]:
            matches.append((hit.entity.get("author_id"), hit.distance))
        
        return matches
    
    def evaluate_queries(
        self,
        ground_truth_csv: str,
        output_file: Optional[str] = None
    ) -> Dict[str, Dict[str, float]]:
        """
        Evaluate the model on all queries in the ground truth CSV.
        
        Args:
            ground_truth_csv: Path to ground truth CSV file
            output_file: Optional path to save detailed results
            
        Returns:
            Dictionary with evaluation metrics per query
        """
        # Load ground truth
        logger.info(f"Loading ground truth from {ground_truth_csv}")
        df = pd.read_csv(ground_truth_csv)
        
        # Extract metadata columns
        metadata_cols = ['ID', 'Category', 'Author with search', 'Author only', 'author_id', 'Name']
        query_cols = [col for col in df.columns if col not in metadata_cols]
        
        logger.info(f"Found {len(query_cols)} query columns")
        
        # Results storage
        results = {}
        detailed_results = []
        
        # Evaluate each query
        for query_col in query_cols:
            logger.info(f"\nEvaluating query: {query_col}")
            
            # Get ground truth rankings (lower is better, NaN means not relevant)
            # Convert researcher IDs to author GUIDs to match Milvus storage
            ground_truth = {}
            for _, row in df.iterrows():
                researcher_id = row['author_id']
                author_guid = convert_researcher_id_to_author_guid(researcher_id)
                rank = row[query_col]
                if pd.notna(rank) and rank >= 3:  # Relevant (rating >= 3 on 1-5 scale)
                    ground_truth[author_guid] = float(rank)
            
            if not ground_truth:
                logger.warning(f"  No ground truth data for query: {query_col}")
                continue
            
            # Perform search
            search_results = self.search(query_col, top_k=len(ground_truth))
            
            # Calculate metrics
            mrr = self._calculate_mrr(search_results, ground_truth)
            ndcg = self._calculate_ndcg(search_results, ground_truth)
            
            logger.info(f"  MRR: {mrr:.4f}, NDCG: {ndcg:.4f}")
            
            results[query_col] = {
                "mrr": mrr,
                "ndcg": ndcg,
                "relevant_authors": len(ground_truth)
            }
            
            # Store detailed results
            detailed_results.append({
                "query": query_col,
                "mrr": mrr,
                "ndcg": ndcg,
                "relevant_authors": len(ground_truth),
                "top_results": search_results[:10]
            })
        
        # Calculate average metrics
        avg_mrr = np.mean([r["mrr"] for r in results.values()])
        avg_ndcg = np.mean([r["ndcg"] for r in results.values()])
        
        logger.info("\n" + "="*70)
        logger.info("EVALUATION SUMMARY")
        logger.info("="*70)
        logger.info(f"Model: {self.model_name}")
        logger.info(f"Queries evaluated: {len(results)}")
        logger.info(f"Average MRR: {avg_mrr:.4f}")
        logger.info(f"Average NDCG: {avg_ndcg:.4f}")
        logger.info("="*70)
        
        # Save detailed results if requested
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "model": self.model_name,
                    "embedding_dim": self.embedding_dim,
                    "avg_mrr": avg_mrr,
                    "avg_ndcg": avg_ndcg,
                    "queries": detailed_results
                }, f, indent=2)
            
            logger.info(f"Detailed results saved to {output_file}")
        
        return results
    
    def _calculate_mrr(
        self,
        search_results: List[Tuple[str, float]],
        ground_truth: Dict[str, float]
    ) -> float:
        """
        Calculate Mean Reciprocal Rank.
        
        Args:
            search_results: List of (author_id, distance) tuples
            ground_truth: Dictionary mapping author_id to ground truth rank
            
        Returns:
            MRR score
        """
        for rank, (author_id, _) in enumerate(search_results, 1):
            if author_id in ground_truth:
                return 1.0 / rank
        return 0.0
    
    def _calculate_ndcg(
        self,
        search_results: List[Tuple[str, float]],
        ground_truth: Dict[str, float],
        k: Optional[int] = None
    ) -> float:
        """
        Calculate Normalized Discounted Cumulative Gain.
        
        Args:
            search_results: List of (author_id, distance) tuples
            ground_truth: Dictionary mapping author_id to ground truth rank
            k: Cutoff for NDCG@k (None for all results)
            
        Returns:
            NDCG score
        """
        if k is not None:
            search_results = search_results[:k]
        
        # Calculate DCG
        dcg = 0.0
        for rank, (author_id, _) in enumerate(search_results, 1):
            if author_id in ground_truth:
                # Relevance is inverse of ground truth rank (lower rank = higher relevance)
                relevance = 1.0 / ground_truth[author_id]
                dcg += relevance / np.log2(rank + 1)
        
        # Calculate IDCG (ideal DCG with perfect ranking)
        ideal_ranks = sorted(ground_truth.values())
        idcg = 0.0
        for rank, gt_rank in enumerate(ideal_ranks, 1):
            relevance = 1.0 / gt_rank
            idcg += relevance / np.log2(rank + 1)
        
        # Return NDCG
        return dcg / idcg if idcg > 0 else 0.0
    
    def cleanup(self):
        """Disconnect from Milvus."""
        connections.disconnect("default")
        logger.info("Disconnected from Milvus")


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Evaluate embedding models on author search tasks")
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="Name of the embedding model to evaluate"
    )
    parser.add_argument(
        "--ground-truth",
        type=str,
        required=True,
        help="Path to ground truth CSV file"
    )
    parser.add_argument(
        "--author-papers",
        type=str,
        required=True,
        help="Path to JSON file with author papers"
    )
    parser.add_argument(
        "--collection-name",
        type=str,
        default="author_embeddings",
        help="Name of the Milvus collection"
    )
    parser.add_argument(
        "--milvus-host",
        type=str,
        default="localhost",
        help="Milvus server host"
    )
    parser.add_argument(
        "--milvus-port",
        type=int,
        default=19530,
        help="Milvus server port"
    )
    parser.add_argument(
        "--trust-remote-code",
        action="store_true",
        help="Trust remote code when loading model"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Path to save detailed evaluation results"
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Skip uploading embeddings (use existing collection)"
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize evaluator
        evaluator = EmbeddingEvaluator(
            model_name=args.model,
            milvus_host=args.milvus_host,
            milvus_port=args.milvus_port,
            trust_remote_code=args.trust_remote_code
        )
        
        if not args.skip_upload:
            # Load author papers
            logger.info(f"Loading author papers from {args.author_papers}")
            with open(args.author_papers, 'r', encoding='utf-8') as f:
                author_papers = json.load(f)
            
            # Load ground truth to get author names
            df = pd.read_csv(args.ground_truth)
            author_names = dict(zip(df['author_id'], df['Name']))
            
            # Create embeddings
            author_embeddings = evaluator.create_author_embeddings(author_papers, author_names)
            
            # Calculate paper counts
            author_paper_counts = {aid: len(papers) for aid, papers in author_papers.items()}
            
            # Create collection and upload
            evaluator.create_collection(args.collection_name, drop_existing=True)
            evaluator.upload_to_milvus(author_embeddings, author_names, author_paper_counts)
        else:
            # Load existing collection
            evaluator.load_collection(args.collection_name)
        
        # Evaluate
        results = evaluator.evaluate_queries(args.ground_truth, args.output)
        
        # Cleanup
        evaluator.cleanup()
        
        logger.info("\nEvaluation complete!")
        
    except Exception as e:
        logger.error(f"Error during evaluation: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
