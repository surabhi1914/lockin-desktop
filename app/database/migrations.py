"""Transactional and idempotent SQLite schema migrations."""

import sqlite3
from importlib.resources import files
from pathlib import Path

from app.core.constants import DATABASE_SCHEMA_VERSION
from app.core.errors import DatabaseVersionError
from app.core.time_utils import format_utc, utc_now
from app.database.connection import connect_database


def _schema_table_exists(connection: sqlite3.Connection) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
    ).fetchone()
    return row is not None


def current_schema_version(connection: sqlite3.Connection) -> int:
    if not _schema_table_exists(connection):
        return 0
    row = connection.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()
    return int(row[0])


def _apply_migration(connection: sqlite3.Connection, version: int) -> None:
    schema_path = files("app.database").joinpath(f"schema_v{version}.sql")
    schema_sql = schema_path.read_text(encoding="utf-8")
    applied_at = format_utc(utc_now())
    rebuilds_referenced_table = version == 5
    if rebuilds_referenced_table:
        connection.execute("PRAGMA foreign_keys = OFF")
    try:
        connection.executescript("BEGIN IMMEDIATE;\n" + schema_sql)
        if rebuilds_referenced_table:
            violations = connection.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise sqlite3.IntegrityError(
                    f"schema v5 migration left foreign-key violations: {violations[:3]}"
                )
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at_utc) VALUES (?, ?)",
            (version, applied_at),
        )
        connection.commit()
    except sqlite3.Error:
        if connection.in_transaction:
            connection.rollback()
        raise
    finally:
        if rebuilds_referenced_table:
            connection.execute("PRAGMA foreign_keys = ON")


def initialize_database(database_path: Path) -> sqlite3.Connection:
    """Create or upgrade a database transactionally and return its open connection."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = connect_database(database_path)
    version = current_schema_version(connection)
    if version > DATABASE_SCHEMA_VERSION:
        connection.close()
        raise DatabaseVersionError(
            f"Database schema version {version} is newer than supported version "
            f"{DATABASE_SCHEMA_VERSION}"
        )
    try:
        for migration_version in range(version + 1, DATABASE_SCHEMA_VERSION + 1):
            _apply_migration(connection, migration_version)
    except sqlite3.Error:
        if connection.in_transaction:
            connection.rollback()
        connection.close()
        raise
    return connection
