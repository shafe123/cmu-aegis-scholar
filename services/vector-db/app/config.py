"""Configuration settings for the Vector DB API service."""

from typing import Dict

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


# Available embedding models and their configurations
# Using FastEmbed (ONNX-based) for smaller image size
AVAILABLE_MODELS: Dict[str, Dict[str, any]] = {
    "sentence-transformers/all-MiniLM-L6-v2": {
        "dimension": 384,
        "description": "Fast and efficient sentence embeddings (384 dimensions)",
        "fastembed_name": "sentence-transformers/all-MiniLM-L6-v2",
    }
}


class Settings(BaseSettings):
    """Application settings."""

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Milvus Configuration
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_user: str = ""
    milvus_password: str = ""

    # Collection Configuration
    default_collection: str = "aegis_vectors"
    embedding_dim: int = 768

    # Pagination Configuration
    default_limit: int = 10
    max_limit: int = 100

    # Embedding Model Configuration
    default_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # API Configuration
    api_title: str = "Aegis Scholar Vector DB API"
    api_version: str = "0.1.0"
    api_description: str = "FastAPI service for vector search operations"


settings = Settings()
