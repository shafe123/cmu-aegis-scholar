import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DOCKER_SECRETS_PATH = "/run/secrets"
SECRETS_DIR = DOCKER_SECRETS_PATH if os.path.exists(DOCKER_SECRETS_PATH) else None


class Settings(BaseSettings):
    """Configuration settings for the Graph API."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", secrets_dir=SECRETS_DIR, extra="ignore"
    )
    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str | None = Field(default=None)
    api_title: str = "Aegis Scholar Graph API"
    api_version: str = "1.0.0"  # removed duplicate line
    api_description: str = "FastAPI service for Neo4j graph operations"
    api_port: int = 8003


settings = Settings()
