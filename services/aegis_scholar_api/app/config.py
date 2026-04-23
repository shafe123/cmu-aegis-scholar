"""Configuration settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # API Configuration
    api_title: str = "Aegis Scholar API"
    api_version: str = "1.0.0"
    api_description: str = "Primary interface for searching research authors, organizations, topics, and works"
    api_host: str = "0.0.0.0"  # nosec B104 — intentional: container must bind all interfaces
    api_port: int = 8000

    # Vector DB Service Configuration
    vector_db_url: str = "http://localhost:8002"
    vector_db_timeout: int = 30

    # Graph DB Service Configuration
    graph_db_url: str = "http://localhost:8003"
    graph_db_timeout: int = 30

    # Identity Service Configuration
    identity_api_url: str = "http://localhost:8005"
    identity_api_timeout: int = 30

    # Search Configuration
    default_limit: int = 10
    max_limit: int = 100
    default_offset: int = 0

    # Logging Configuration
    log_level: str = "INFO"

    # CORS Configuration
    cors_origins: list[str] = ["*"]  # Configure appropriately for production
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["*"]
    cors_allow_headers: list[str] = ["*"]


settings = Settings()
