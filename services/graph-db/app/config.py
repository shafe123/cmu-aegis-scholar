import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# We only set the secrets_dir if it actually exists to avoid Pydantic's UserWarning
DOCKER_SECRETS_PATH = "/run/secrets"
VALID_SECRETS_DIR = DOCKER_SECRETS_PATH if os.path.exists(DOCKER_SECRETS_PATH) else None

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        secrets_dir=VALID_SECRETS_DIR,
        extra="ignore"
    )

    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    
    # Pydantic matches this field to a file named 'neo4j_password' in secrets_dir
    neo4j_password: Optional[str] = Field(default=None)

    api_title: str = "Aegis Scholar Graph API"
    api_version: str = "1.0.0"
    api_description: str = "FastAPI service for Neo4j graph operations"
    api_port: int = 8003

# Initialize settings
try:
    settings = Settings()
except Exception:
    # Provides a default settings object for testing/scanning 
    # if the .env file is missing
    settings = Settings(_env_file=None)