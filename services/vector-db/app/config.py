from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Dict


# Available embedding models and their configurations
# Currently restricted to all-MiniLM-L6-v2 only
AVAILABLE_MODELS: Dict[str, Dict[str, any]] = {
    "sentence-transformers/all-MiniLM-L6-v2": {
        "dimension": 384,
        "description": "Fast and efficient sentence embeddings (384 dimensions)",
        "trust_remote_code": False
    }
}


class Settings(BaseSettings):
    """Application settings."""
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8"
    )
    
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
    api_title: str = "AEGIS Scholar Vector DB Service"
    api_version: str = "0.1.0"
    api_description: str = "FastAPI service for Milvus vector search operations"


settings = Settings()
