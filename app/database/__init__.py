"""SQLite schema and initialization support."""

from app.database.migrations import initialize_database

__all__ = ["initialize_database"]
