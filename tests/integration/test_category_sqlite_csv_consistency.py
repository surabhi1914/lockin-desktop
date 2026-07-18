import hashlib
from pathlib import Path

import pytest

from app.database.connection import connect_database
from app.database.repositories.category_repository import CategoryRepository
from app.models.errors import CategoryPersistenceError
from app.portability.category_portable_store import CategoryPortableStore
from app.services.category_service import CategoryService
from tests.phase3_helpers import isolated_category_service, path_config


def _hashes(root: Path) -> dict[Path, str]:
    return {
        path.relative_to(root): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_each_mutation_keeps_sqlite_and_csv_exactly_equal(tmp_path: Path) -> None:
    service, connection, store = isolated_category_service(path_config(tmp_path))
    try:
        created = service.create("Portfolio Work")
        service.rename(created.category_id, "Portfolio Projects")
        service.archive(created.category_id)
        service.restore(created.category_id)
        assert service.repository.list_all() == store.load()
        assert service.check_consistency()
    finally:
        connection.close()


def test_category_is_only_portable_file_changed_by_explicit_mutation(tmp_path: Path) -> None:
    config = path_config(tmp_path)
    service, connection, _ = isolated_category_service(config)
    before = _hashes(config.portable_root)
    try:
        service.create("Portfolio Work")
        after = _hashes(config.portable_root)
        changed = {path for path in before if before[path] != after[path]}
        assert changed == {Path("categories.csv")}
        assert before.keys() == after.keys()
    finally:
        connection.close()


def test_startup_detects_conflicting_csv_and_blocks_mutation(tmp_path: Path) -> None:
    config = path_config(tmp_path)
    service, connection, _ = isolated_category_service(config)
    connection.close()
    categories = config.portable_root / "categories.csv"
    text = categories.read_text(encoding="utf-8")
    categories.write_text(
        text.replace("Machine Learning", "Machine Learning Changed"), encoding="utf-8"
    )
    reopened_connection = connect_database(config.database_path)
    store = CategoryPortableStore(
        categories,
        backup_directory=config.runtime_root / "category_backups",
    )
    reopened = CategoryService(
        CategoryRepository(reopened_connection),
        store,
        recovery_marker_path=config.runtime_root / "category_recovery_required.txt",
    )
    try:
        with pytest.raises(CategoryPersistenceError, match="conflict"):
            reopened.initialize()
        with pytest.raises(CategoryPersistenceError):
            reopened.create("Blocked")
    finally:
        reopened_connection.close()
    del service


def test_invalid_existing_csv_is_not_overwritten_by_service(tmp_path: Path) -> None:
    config = path_config(tmp_path)
    service, connection, _ = isolated_category_service(config)
    categories = config.portable_root / "categories.csv"
    categories.write_text("bad,header\npersonal,data\n", encoding="utf-8")
    original = categories.read_bytes()
    try:
        with pytest.raises(CategoryPersistenceError):
            service.create("Must Not Appear")
        assert categories.read_bytes() == original
    finally:
        connection.close()
