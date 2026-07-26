from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    app_name: str = "ClearLens"
    debug: bool = False
    port: int = 8000
    host: str = "0.0.0.0"

    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None

    database_path: str = "data/clearlens.db"
    cache_ttl_seconds: int = 86400
    chroma_persist_dir: str = "data/chroma"

    rate_limit_per_hour: int = 50
    max_analysis_per_day: int = 20

    youtube_transcript_proxy: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
