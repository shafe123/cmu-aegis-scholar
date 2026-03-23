from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Neo4j Configuration
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    neo4j_database: str = "neo4j"

    # API Configuration
    api_title: str = "Aegis Scholar Graph API"
    api_version: str = "0.1.0"
    api_description: str = "FastAPI service for Neo4j graph operations"
    api_port: int = 8003

settings = Settings()