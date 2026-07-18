"""Configured SQLite connections for LockIn runtime data."""

import sqlite3
from pathlib import Path


def connect_database(database_path: Path, *, read_only: bool = False) -> sqlite3.Connection:
    """Open a SQLite connection with Phase 0 safety settings."""
    target: str | Path = database_path
    if read_only:
        target = f"file:{database_path.resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(target, timeout=5.0, uri=read_only)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    if not read_only:
        connection.execute("PRAGMA journal_mode = WAL")
    return connection
