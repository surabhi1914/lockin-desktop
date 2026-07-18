from pathlib import Path

import pytest

from app.models.errors import (
    CategoryNotFoundError,
    CategoryPersistenceError,
    DuplicateCategoryError,
    ProtectedCategoryError,
)
from app.services.category_service import OTHER_CATEGORY_ID
from tests.phase3_helpers import isolated_category_service, path_config


def test_initialize_imports_phase0_starters_without_changing_ids(tmp_path: Path) -> None:
    service, connection, store = isolated_category_service(path_config(tmp_path))
    try:
        assert len(service.list_active()) == 9
        assert service.repository.count() == 9
        assert service.repository.get_by_id(OTHER_CATEGORY_ID).category_name == "Other"
        assert {item.category_id for item in service.repository.list_all()} == {
            item.category_id for item in store.load()
        }
    finally:
        connection.close()


def test_create_rename_archive_restore_sync_and_notify_once(tmp_path: Path) -> None:
    service, connection, store = isolated_category_service(path_config(tmp_path))
    changes: list[str] = []
    service.subscribe(lambda: changes.append("changed"))
    try:
        created = service.create(" Portfolio   Work ", "\U0001f4bc")
        assert changes == ["changed"]
        assert created.category_id in {item.category_id for item in store.load()}
        renamed = service.rename(created.category_id, "Portfolio Projects")
        assert renamed.category_id == created.category_id
        archived = service.archive(created.category_id)
        assert not archived.is_active
        assert created.category_id not in {item.category_id for item in service.list_active()}
        restored = service.restore(created.category_id)
        assert restored.is_active
        assert changes == ["changed"] * 4
        assert service.check_consistency()
        assert service.repository.count() == 10
    finally:
        connection.close()


def test_duplicates_and_other_mutation_are_blocked(tmp_path: Path) -> None:
    service, connection, _ = isolated_category_service(path_config(tmp_path))
    try:
        with pytest.raises(DuplicateCategoryError):
            service.create(" machine   LEARNING ")
        with pytest.raises(ProtectedCategoryError):
            service.rename(OTHER_CATEGORY_ID, "Fallback")
        with pytest.raises(ProtectedCategoryError):
            service.archive(OTHER_CATEGORY_ID)
        assert service.repository.count() == 9
    finally:
        connection.close()


def test_archived_resolution_listener_unsubscribe_and_recovery_marker(tmp_path: Path) -> None:
    service, connection, _ = isolated_category_service(path_config(tmp_path))
    recovery_marker = tmp_path / "runtime" / "category_recovery_required.txt"
    changes: list[str] = []
    unsubscribe = service.subscribe(lambda: changes.append("changed"))
    try:
        created = service.create("Deep Work")
        archived = service.archive(created.category_id)
        assert service.list_archived() == (archived,)
        with pytest.raises(CategoryNotFoundError):
            service.resolve_selected_category(created.category_id)
        unsubscribe()
        service.restore(created.category_id)
        assert changes == ["changed", "changed"]

        recovery_marker.write_text("repair required", encoding="utf-8")
        with pytest.raises(CategoryPersistenceError, match="recovery marker"):
            service.initialize()
        service.clear_recovery_marker_if_consistent()
        assert not recovery_marker.exists()
    finally:
        connection.close()


def test_portable_replace_failure_rolls_back_sqlite_and_removes_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, connection, store = isolated_category_service(path_config(tmp_path))
    recovery_marker = tmp_path / "runtime" / "category_recovery_required.txt"
    initial = service.repository.count()

    def fail_replace(staged: Path) -> None:
        raise OSError(f"cannot replace {staged.name}")

    monkeypatch.setattr(store, "replace_staged", fail_replace)
    try:
        with pytest.raises(CategoryPersistenceError, match="was not applied"):
            service.create("Will Roll Back")
        assert service.repository.count() == initial
        assert not list(store.path.parent.glob("*.tmp"))
        assert not recovery_marker.exists()
    finally:
        connection.close()
