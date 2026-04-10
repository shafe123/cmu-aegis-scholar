"""Configuration settings."""

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    # API Configuration
    api_title: str = "Aegis Scholar API"
    api_version: str = "1.0.0"
    api_description: str = "Primary interface for searching research authors, organizations, topics, and works"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Vector DB Service Configuration
    vector_db_url: str = "http://localhost:8002"
    vector_db_timeout: int = 30

    # Database Configuration (to be implemented)
    database_url: str = ""

    # Azure Cosmos DB Configuration (if using)
    cosmos_endpoint: str = ""
    cosmos_key: str = ""
    cosmos_database: str = "aegis"

    # Search Configuration
    default_limit: int = 10
    max_limit: int = 100
    default_offset: int = 0

    # Cache Configuration (to be implemented)
    redis_url: str = ""
    cache_ttl: int = 3600  # 1 hour default

    # Logging Configuration
    log_level: str = "INFO"

    # CORS Configuration
    cors_origins: list[str] = ["*"]  # Configure appropriately for production
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]


settings = Settings()
