from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Graph API settings
    graph_api_url: str = "http://graph-db:8003"
    graph_api_timeout: int = 300 
    
    # Data source settings (matches vector-loader)
    data_dir: str = "/data/dtic_compressed"
    
    # Processing settings
    batch_size: int = 100
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()