"""
Configuration for external data database.
This is a completely separate database that mirrors the gmail_outlook_db.
"""

import os
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


def _is_docker_environment() -> bool:
    """Check if we're running inside Docker."""
    db_url = os.environ.get("DATABASE_URL", "")
    return "@postgres:" in db_url


class ExternalDBSettings(BaseSettings):
    """External database settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # External Database Connection (remote source - read only)
    external_db_host: str = "ai-employee-agent.ibhc.ai"
    external_db_port: int = 5432
    external_db_name: str = "gmail_outlook_db"
    external_db_user: str = "postgres"
    external_db_password: str = "tiquaequoSie3Ied"

    # Local Database (for storing synced data)
    local_db_name: str = "external_data_db"
    local_db_user: str = "ai_assistant"
    local_db_password: str = "ai_assistant_secret"

    # Sync Settings
    sync_batch_size: int = 100
    sync_interval_minutes: int = 15

    # Debug
    debug: bool = False

    @property
    def external_database_url(self) -> str:
        """Async database URL for the remote external database."""
        return (
            f"postgresql+asyncpg://{self.external_db_user}:{self.external_db_password}"
            f"@{self.external_db_host}:{self.external_db_port}/{self.external_db_name}"
        )

    @property
    def local_database_url(self) -> str:
        """Async database URL for the local database.

        Auto-detects Docker environment and uses appropriate host/port.
        """
        # Check environment at runtime, not at object creation
        if _is_docker_environment():
            host = "postgres"
            port = 5432
        else:
            host = "localhost"
            port = 5433

        return (
            f"postgresql+asyncpg://{self.local_db_user}:{self.local_db_password}"
            f"@{host}:{port}/{self.local_db_name}"
        )

    @property
    def local_sync_database_url(self) -> str:
        """Synchronous database URL for Alembic migrations."""
        # For alembic, always use localhost since it runs outside Docker
        return (
            f"postgresql://{self.local_db_user}:{self.local_db_password}"
            f"@localhost:5433/{self.local_db_name}"
        )


@lru_cache
def get_external_db_settings() -> ExternalDBSettings:
    """Get cached external database settings instance."""
    return ExternalDBSettings()
