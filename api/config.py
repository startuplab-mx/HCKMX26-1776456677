from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # LLM
    anthropic_api_key: str = ""
    nvidia_api_key: str = ""
    groq_api_key: str = ""
    google_api_key: str = ""
    cerebras_api_key: str = ""
    together_api_key: str = ""
    llm_provider: str = "groq"  # legacy — pool handles routing now

    # Celery / Redis
    redis_url: str = "redis://localhost:6379/0"
    celery_broker: str = "redis://localhost:6379/0"
    celery_backend: str = "redis://localhost:6379/1"

    # DB
    database_url: str = "sqlite:///./guardiannode.db"

    # API
    api_key_secret: str = "change-me-in-production"
    cors_origins: list[str] = ["*"]

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
