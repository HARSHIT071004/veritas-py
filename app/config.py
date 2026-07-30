from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    app_name: str = "ClearLens"
    debug: bool = False
    port: int = 8000
    host: str = "0.0.0.0"

    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    groq_stt_model: str = "whisper-large-v3-turbo"

    openrouter_api_key: Optional[str] = None
    openrouter_model: str = "google/gemma-4-26b-a4b-it:free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    paddle_ocr_enabled: bool = True
    easy_ocr_enabled: bool = True
    opencv_frames_enabled: bool = True
    opencv_frame_interval: int = 30

    database_path: str = "data/clearlens.db"
    cache_ttl_seconds: int = 86400
    rag_persist_dir: str = "data/rag"

    jwt_secret: str = "clearlens-dev-secret-change-in-production"
    jwt_expiry_seconds: int = 86400

    internal_api_key: str = ""

    redis_url: Optional[str] = None
    redis_enabled: bool = False

    rate_limit_per_hour: int = 50
    max_analysis_per_day: int = 20

    log_level: str = "INFO"
    log_file: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
