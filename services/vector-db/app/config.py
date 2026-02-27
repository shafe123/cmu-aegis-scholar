from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
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
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    
    # API Configuration
    api_title: str = "AEGIS Scholar Vector DB Service"
    api_version: str = "0.1.0"
    api_description: str = "FastAPI service for Milvus vector search operations"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
