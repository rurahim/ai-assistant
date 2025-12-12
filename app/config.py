"""
Application configuration using Pydantic Settings.
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://ai_assistant:ai_assistant_secret@localhost:5432/ai_assistant_db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # OpenAI
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    chat_model: str = "gpt-4o-mini"
    chat_model_advanced: str = "gpt-4o"

    # External Data Service
    external_api_base: Optional[str] = None
    external_api_key: Optional[str] = None

    # Data Source Mode
    # False = Use internal DB embeddings (mock/seed data)
    # True = Fetch from external APIs, store, and create embeddings
    external_data_enabled: bool = False

    # Sync Settings
    gmail_sync_days: int = 30
    document_sync_months: int = 6
    calendar_sync_days: int = 30
    jira_sync_months: int = 3

    # Performance Settings
    max_context_items: int = 10
    max_context_tokens: int = 4000
    embedding_batch_size: int = 100
    cache_ttl_seconds: int = 3600
    embedding_dimensions: int = 1536

    # App Settings
    debug: bool = False
    log_level: str = "INFO"

    @property
    def sync_database_url(self) -> str:
        """Return synchronous database URL for Alembic."""
        return self.database_url.replace(
            "postgresql+asyncpg://", "postgresql://"
        )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
