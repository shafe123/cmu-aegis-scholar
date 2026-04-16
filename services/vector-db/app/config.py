"""Configuration settings for the Vector DB API service."""
from typing import Any, Dict
from pydantic_settings import BaseSettings, SettingsConfigDict

AVAILABLE_MODELS: Dict[str, Dict[str, Any]] = {  # Any capitalized
    "sentence-transformers/all-MiniLM-L6-v2": {
        "dimension": 384,
        "description": "Fast and efficient sentence embeddings (384 dimensions)",
        "fastembed_name": "sentence-transformers/all-MiniLM-L6-v2",
    }
}

class Settings(BaseSettings):  # pylint: disable=too-few-public-methods
    """Application settings."""
    model_config = SettingsConfigDict(  # SettingsConfigDict, not ConfigDict
        env_file=".env", env_file_encoding="utf-8"
    )
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_user: str = ""
    milvus_password: str = ""
    default_collection: str = "aegis_vectors"
    embedding_dim: int = 768
    default_limit: int = 10
    max_limit: int = 100
    default_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    api_title: str = "Aegis Scholar Vector DB API"
    api_version: str = "0.1.0"
    api_description: str = "FastAPI service for vector search operations"

settings = Settings()