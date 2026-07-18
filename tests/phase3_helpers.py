"""Shared isolated Phase 3 category-service test construction."""

import sqlite3
from importlib.resources import files
from pathlib import Path

from app.bootstrap import run_phase0_bootstrap
from app.core.paths import PathConfig
from app.database.connection import connect_database
from app.database.repositories.category_repository import CategoryRepository
from app.portability.category_portable_store import CategoryPortableStore
from app.services.category_service import CategoryService


def memory_category_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(files("app.database").joinpath("schema_v1.sql").read_text("utf-8"))
    return connection


def isolated_category_service(
    config: PathConfig,
    *,
    timestamp: str = "2026-07-16T20:00:00Z",
    uuid_value: str = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
) -> tuple[CategoryService, sqlite3.Connection, CategoryPortableStore]:
    result = run_phase0_bootstrap(config=config)
    assert result.success, result.errors
    connection = connect_database(config.database_path)
    store = CategoryPortableStore(
        config.portable_root / "categories.csv",
        backup_directory=config.runtime_root / "category_backups",
        timestamp_provider=lambda: timestamp,
    )
    service = CategoryService(
        CategoryRepository(connection),
        store,
        recovery_marker_path=config.runtime_root / "category_recovery_required.txt",
        timestamp_provider=lambda: timestamp,
        uuid_provider=lambda: uuid_value,
    )
    service.initialize()
    return service, connection, store


def path_config(tmp_path: Path) -> PathConfig:
    return PathConfig(tmp_path, tmp_path / "runtime", tmp_path / "portable")
