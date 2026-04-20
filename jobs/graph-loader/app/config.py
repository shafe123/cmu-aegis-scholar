from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Graph API settings
    graph_api_url: str = "http://graph-db:8003"
    graph_api_timeout: int = 300

    # Data source settings
    data_dir: str = "/data/dtic_compressed"

    # Loading Logic
    skip_if_loaded: bool = True
    min_entities_threshold: int = 100

    # Processing settings
    batch_size: int = 1000
    log_level: str = "INFO"


settings = Settings()
