"""Configuration for vector loader job."""
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Vector DB API settings
    vector_db_url: str = "http://vector-db:8002"
    vector_db_timeout: int = 300  # 5 minutes for bulk operations

    # Data source settings
    data_dir: str = "/data/dtic_compressed"
    entity_types: list[str] = ["authors", "works", "orgs", "topics"]

    # Collection settings
    collection_name: str = "aegis_vectors"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Processing settings
    batch_size: int = 100  # Number of records to process in a batch
    max_records: int | None = None  # Limit total records processed (None = all)
    skip_if_loaded: bool = True  # Skip loading if collection already has data
    min_entities_threshold: int = 100  # Minimum entities to consider collection "loaded"

    # Logging
    log_level: str = "INFO"


settings = Settings()
