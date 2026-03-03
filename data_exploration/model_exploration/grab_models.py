"""
Script to find sentence-transformer models with max_seq_length > 643
"""

from huggingface_hub import HfApi, hf_hub_download
import json
import os
from typing import List, Dict
import requests


def get_model_config(model_id: str) -> tuple[int | None, int | None]:
    """
    Get the max_seq_length and embedding dimension for a given model.
    
    Args:
        model_id: The Hugging Face model ID
        
    Returns:
        Tuple of (max_seq_length, embedding_dim)
    """
    max_seq_length = None
    embedding_dim = None
    
    try:
        # Try to get the sentence_bert_config.json first (sentence-transformers specific)
        config_url = f"https://huggingface.co/{model_id}/resolve/main/sentence_bert_config.json"
        response = requests.get(config_url, timeout=10)
        
        if response.status_code == 200:
            config = response.json()
            max_seq_length = config.get('max_seq_length')
        
        # Try the main config.json for both max_seq_length and embedding dimension
        config_url = f"https://huggingface.co/{model_id}/resolve/main/config.json"
        response = requests.get(config_url, timeout=10)
        
        if response.status_code == 200:
            config = response.json()
            
            # Get max_seq_length if not already found
            if max_seq_length is None:
                max_seq_length = config.get('max_position_embeddings') or config.get('n_positions') or config.get('max_seq_length')
            
            # Get embedding dimension (various possible keys)
            embedding_dim = (
                config.get('hidden_size') or 
                config.get('d_model') or 
                config.get('embedding_size') or
                config.get('embed_dim')
            )
                
    except Exception as e:
        print(f"Error fetching config for {model_id}: {e}")
    
    return max_seq_length, embedding_dim


def get_model_description(model) -> str:
    """
    Extract a brief description from the model's card data or README.
    
    Args:
        model: The model object from HfApi
        
    Returns:
        A brief description string, or empty string if not available
    """
    try:
        # Try to get description from cardData
        card_data = getattr(model, 'cardData', None)
        if card_data:
            # Check for common description fields
            description = (
                getattr(card_data, 'model_description', None) or
                getattr(card_data, 'description', None) or
                getattr(card_data, 'base_model_description', None)
            )
            if description:
                return description
        
        # Try model_index for pipeline tag or task
        if hasattr(model, 'pipeline_tag') and model.pipeline_tag:
            return f"Pipeline: {model.pipeline_tag}"
        
    except Exception as e:
        pass
    
    return ""


def get_model_size(model_id: str, api: HfApi) -> tuple[float, str]:
    """
    Get the model size in GB.
    
    Args:
        model_id: The Hugging Face model ID
        api: HfApi instance
        
    Returns:
        Tuple of (size in GB, formatted size string)
    """
    try:
        # Get model files info
        model_info = api.model_info(model_id, files_metadata=True)
        
        # Sum up all file sizes
        total_bytes = 0
        if hasattr(model_info, 'siblings') and model_info.siblings:
            for file in model_info.siblings:
                if hasattr(file, 'size') and file.size:
                    total_bytes += file.size
        
        # Convert to GB
        size_gb = total_bytes / (1024 ** 3)
        
        # Format size string
        if size_gb < 0.01:
            size_str = f"{total_bytes / (1024 ** 2):.1f} MB"
        elif size_gb < 1:
            size_str = f"{total_bytes / (1024 ** 2):.0f} MB"
        else:
            size_str = f"{size_gb:.2f} GB"
        
        return size_gb, size_str
        
    except Exception as e:
        return 0, "Unknown"


def find_models_with_large_context(min_seq_length: int = 643, limit: int = 100) -> List[Dict]:
    """
    Find sentence-transformer models with max_seq_length > min_seq_length.
    
    Args:
        min_seq_length: Minimum sequence length threshold
        limit: Maximum number of models to check
        
    Returns:
        List of dictionaries with model info
    """
    api = HfApi()
    results = []
    
    print(f"Searching for sentence-transformer models with max_seq_length > {min_seq_length}...")
    print(f"Checking up to {limit} models from Hugging Face...\n")
    
    # Search for sentence-transformers models
    models = api.list_models(
        filter="sentence-transformers",
        sort="downloads",
        direction=-1,
        limit=limit,
        cardData=True  # Request card data
    )
    
    checked = 0
    for model in models:
        checked += 1
        model_id = model.id
        
        if checked % 10 == 0:
            print(f"Checked {checked} models, found {len(results)} matching...")
        
        max_seq_length, embedding_dim = get_model_config(model_id)
        
        if max_seq_length is not None and max_seq_length > min_seq_length:
            description = get_model_description(model)
            size_gb, size_str = get_model_size(model_id, api)
            
            model_info = {
                'model_id': model_id,
                'max_seq_length': max_seq_length,
                'embedding_dim': embedding_dim,
                'size_gb': size_gb,
                'size_str': size_str,
                'downloads': getattr(model, 'downloads', 0),
                'likes': getattr(model, 'likes', 0),
                'description': description,
                'pipeline_tag': getattr(model, 'pipeline_tag', ''),
                'tags': getattr(model, 'tags', [])
            }
            results.append(model_info)
            dim_str = f", dim: {embedding_dim}" if embedding_dim else ""
            print(f"✓ Found: {model_id} (max_seq_length: {max_seq_length}{dim_str}, size: {size_str})")
    
    print(f"\nTotal checked: {checked}")
    print(f"Total found with max_seq_length > {min_seq_length}: {len(results)}")
    
    # Sort by max_seq_length descending
    results.sort(key=lambda x: x['max_seq_length'], reverse=True)
    
    return results


def save_results(results: List[Dict], filename: str = "models_large_context.json"):
    """Save results to a JSON file."""
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {filename}")


def main():
    """Main function to run the search."""
    # Find models with max_seq_length > 643
    results = find_models_with_large_context(min_seq_length=643, limit=200)
    
    # Display top results
    print("\n" + "="*80)
    print("TOP MODELS WITH LARGE CONTEXT (max_seq_length > 643):")
    print("="*80)
    
    for i, model in enumerate(results[:20], 1):
        print(f"\n{i}. {model['model_id']}")
        print(f"   Max Sequence Length: {model['max_seq_length']}")
        if model.get('embedding_dim'):
            print(f"   Embedding Dimension: {model['embedding_dim']}")
        print(f"   Model Size: {model['size_str']}")
        print(f"   Downloads: {model['downloads']:,}")
        print(f"   Likes: {model['likes']}")
        if model.get('pipeline_tag'):
            print(f"   Pipeline: {model['pipeline_tag']}")
        if model.get('description'):
            print(f"   Description: {model['description'][:100]}{'...' if len(model.get('description', '')) > 100 else ''}")
    
    # Save to file
    save_results(results)
    
    return results


if __name__ == "__main__":
    results = main()
