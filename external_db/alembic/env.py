"""
Alembic environment for external data database migrations.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Import the external database configuration
from external_db.config import get_external_db_settings
from external_db.database import Base

# Import all models to register them with Base.metadata
from external_db.models import (
    User,
    Account,
    AIPreference,
    CalendarEvent,
    Email,
    Contact,
    Task,
    JiraBoard,
    JiraIssue,
    OnlineMeeting,
)

# this is the Alembic Config object
config = context.config

# Get database settings
settings = get_external_db_settings()

# Set the database URL from settings
config.set_main_option("sqlalchemy.url", settings.local_sync_database_url)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
