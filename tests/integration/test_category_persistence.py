from pathlib import Path

from app.database.connection import connect_database
from app.database.repositories.category_repository import CategoryRepository
from app.portability.category_portable_store import CategoryPortableStore
from app.services.category_service import CategoryService
from tests.phase3_helpers import isolated_category_service, path_config


def test_created_category_survives_service_and_database_restart(tmp_path: Path) -> None:
    config = path_config(tmp_path)
    service, connection, _ = isolated_category_service(config)
    created = service.create("Portfolio Work", "P")
    connection.close()

    reopened_connection = connect_database(config.database_path)
    reopened_store = CategoryPortableStore(
        config.portable_root / "categories.csv",
        backup_directory=config.runtime_root / "category_backups",
    )
    reopened = CategoryService(
        CategoryRepository(reopened_connection),
        reopened_store,
        recovery_marker_path=config.runtime_root / "category_recovery_required.txt",
    )
    try:
        reopened.initialize()
        persisted = reopened.repository.get_by_id(created.category_id)
        assert persisted == created
        assert persisted in reopened_store.load()
    finally:
        reopened_connection.close()


def test_rename_archive_and_restore_survive_restart(tmp_path: Path) -> None:
    config = path_config(tmp_path)
    service, connection, _ = isolated_category_service(config)
    created = service.create("Portfolio Work")
    renamed = service.rename(created.category_id, "Portfolio Projects")
    service.archive(created.category_id)
    connection.close()

    reopened, reopened_connection, _ = isolated_category_service(config)
    try:
        archived = reopened.repository.get_by_id(created.category_id)
        assert archived.category_name == renamed.category_name
        assert not archived.is_active
        reopened.restore(created.category_id)
    finally:
        reopened_connection.close()

    final, final_connection, _ = isolated_category_service(config)
    try:
        assert final.repository.get_by_id(created.category_id).is_active
    finally:
        final_connection.close()
