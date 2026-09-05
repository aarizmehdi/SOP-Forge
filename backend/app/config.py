"""
SOP Forge — Configuration module.
Loads all settings from environment variables via pydantic-settings.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from .env file and environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──
    mongo_uri: str = "mongodb://localhost:27017/sopforge"

    # ── Redis ──
    redis_url: str = "redis://localhost:6379/0"

    # ── LLM ──
    deepseek_api_key: str = "your-deepseek-api-key-here"
    openai_api_key: str = ""
    assemblyai_api_key: str = ""

    # ── Auth ──
    jwt_secret: str = "sopforge-secure-org-demo-secret-key-2026"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 480

    # ── SOP Engine Config ──
    confidence_threshold: float = 0.85
    sla_default_hours: int = 2

    # ── Embedding ──
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    @property
    def is_llm_configured(self) -> bool:
        """Check if a real LLM API key is configured."""
        return (
            self.deepseek_api_key != "your-deepseek-api-key-here"
            and len(self.deepseek_api_key) > 10
        )


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
