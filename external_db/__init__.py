"""
External Data Database Package.
This is a completely separate database setup that mirrors the gmail_outlook_db.
Can be used as a replacement for the main app database in the future.
"""

from external_db.database import (
    Base,
    get_external_db,
    get_local_db,
    get_external_db_context,
    get_local_db_context,
    init_local_db,
    close_all_connections,
)
from external_db.config import get_external_db_settings

__all__ = [
    "Base",
    "get_external_db",
    "get_local_db",
    "get_external_db_context",
    "get_local_db_context",
    "init_local_db",
    "close_all_connections",
    "get_external_db_settings",
]
