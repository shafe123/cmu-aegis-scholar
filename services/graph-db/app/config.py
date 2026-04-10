import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Only set secrets_dir if the directory actually exists
DOCKER_SECRETS_PATH = "/run/secrets"
SECRETS_DIR = DOCKER_SECRETS_PATH if os.path.exists(DOCKER_SECRETS_PATH) else None


class Settings(BaseSettings):
    """Configuration settings for the Graph API."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", secrets_dir=SECRETS_DIR, extra="ignore"
    )

    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"

    # Pydantic matches this field to a file named 'neo4j_password' in secrets_dir
    neo4j_password: str | None = Field(default=None)

    api_title: str = "Aegis Scholar Graph API"
    api_version: str = "1.0.0"
    api_version: str = "1.0.0"
    api_description: str = "FastAPI service for Neo4j graph operations"
    api_port: int = 8003


# Initialize settings
try:
    settings = Settings()
except Exception:  # pylint: disable=broad-exception-caught
    # Fallback for environment-less scanning phases
    settings = Settings(_env_file=None)
