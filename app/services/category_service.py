"""Coordinated permanent category management across SQLite and portable CSV."""

import sqlite3
from collections.abc import Callable, Sequence
from pathlib import Path

from app.core.ids import new_uuid4, starter_category_uuid
from app.core.time_utils import format_utc, utc_now
from app.database.repositories.category_repository import CategoryRepository
from app.models.category import Category, category_uniqueness_key, normalize_category_name
from app.models.errors import (
    CategoryNotFoundError,
    CategoryPersistenceError,
    DuplicateCategoryError,
    ProtectedCategoryError,
)
from app.portability.category_portable_store import CategoryPortableStore

CategoryChangeListener = Callable[[], None]
OTHER_CATEGORY_ID = starter_category_uuid("Other")


class CategoryService:
    """Validate, coordinate, and announce permanent category changes."""

    def __init__(
        self,
        repository: CategoryRepository,
        portable_store: CategoryPortableStore,
        *,
        recovery_marker_path: Path,
        uuid_provider: Callable[[], str] = new_uuid4,
        timestamp_provider: Callable[[], str] | None = None,
    ) -> None:
        self._repository = repository
        self._store = portable_store
        self._recovery_marker_path = recovery_marker_path
        self._uuid_provider = uuid_provider
        self._timestamp_provider = timestamp_provider or (lambda: format_utc(utc_now()))
        self._listeners: list[CategoryChangeListener] = []
        self._consistency_error: str | None = None

    @property
    def repository(self) -> CategoryRepository:
        return self._repository

    @property
    def consistency_error(self) -> str | None:
        return self._consistency_error

    def initialize(self) -> None:
        """Import Phase 0 categories once, then require exact DB/CSV consistency."""
        if self._recovery_marker_path.exists():
            message = (
                "category recovery marker exists; resolve category consistency before mutation: "
                f"{self._recovery_marker_path}"
            )
            self._consistency_error = message
            raise CategoryPersistenceError(message)
        portable = self._store.load()
        database = self._repository.list_all()
        if not database and portable:
            try:
                self._repository.connection.execute("BEGIN IMMEDIATE")
                for category in portable:
                    self._repository.create(category)
                self._repository.connection.commit()
            except (sqlite3.Error, DuplicateCategoryError) as exc:
                self._repository.connection.rollback()
                raise CategoryPersistenceError(
                    f"could not initialize SQLite categories from Phase 0 portable data: {exc}"
                ) from exc
            database = self._repository.list_all()
        self._assert_same(database, portable, allow_database_only=True)
        self._consistency_error = None

    def list_active(self) -> tuple[Category, ...]:
        return self._repository.list_active()

    def list_archived(self) -> tuple[Category, ...]:
        return tuple(category for category in self._repository.list_all() if not category.is_active)

    def create(self, category_name: str, category_icon: str | None = None) -> Category:
        self._ensure_mutation_allowed()
        normalized_name = normalize_category_name(category_name)
        duplicate = self._repository.find_by_normalized_name(normalized_name)
        if duplicate is not None:
            raise DuplicateCategoryError(
                f"A category named {duplicate.category_name!r} already exists."
            )
        timestamp = self._timestamp_provider()
        category = Category(
            category_id=self._uuid_provider(),
            category_name=normalized_name,
            category_icon=category_icon,
            is_active=True,
            created_at_utc=timestamp,
            updated_at_utc=timestamp,
        )
        current = self._repository.list_all()
        self._coordinate((*current, category), lambda: self._repository.create(category), current)
        self._notify()
        return category

    def rename(self, category_id: str, category_name: str) -> Category:
        self._ensure_mutation_allowed()
        self._protect_other(category_id, "renamed")
        normalized_name = normalize_category_name(category_name)
        current = self._repository.list_all()
        existing = self._get_from(current, category_id)
        duplicate = self._repository.find_by_normalized_name(normalized_name)
        if duplicate is not None and duplicate.category_id != category_id:
            raise DuplicateCategoryError(
                f"A category named {duplicate.category_name!r} already exists."
            )
        timestamp = self._timestamp_provider()
        renamed = Category(
            existing.category_id,
            normalized_name,
            existing.category_icon,
            existing.is_active,
            existing.created_at_utc,
            timestamp,
        )
        intended = tuple(renamed if item.category_id == category_id else item for item in current)
        self._coordinate(
            intended,
            lambda: self._repository.rename(category_id, normalized_name, timestamp),
            current,
        )
        self._notify()
        return renamed

    def archive(self, category_id: str) -> Category:
        self._ensure_mutation_allowed()
        self._protect_other(category_id, "archived")
        return self._set_active(category_id, False)

    def restore(self, category_id: str) -> Category:
        self._ensure_mutation_allowed()
        return self._set_active(category_id, True)

    def resolve_selected_category(self, category_id: str) -> Category:
        category = self._repository.get_by_id(category_id)
        if not category.is_active:
            raise CategoryNotFoundError(
                f"Selected category {category.category_name!r} is archived. "
                "Choose an active category."
            )
        return category

    def subscribe(self, listener: CategoryChangeListener) -> Callable[[], None]:
        if listener not in self._listeners:
            self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def check_consistency(self) -> bool:
        try:
            self._assert_same(
                self._repository.list_all(), self._store.load(), allow_database_only=True
            )
        except CategoryPersistenceError as exc:
            self._consistency_error = str(exc)
            return False
        self._consistency_error = None
        return True

    def clear_recovery_marker_if_consistent(self) -> None:
        if not self.check_consistency():
            raise CategoryPersistenceError(self._consistency_error or "categories are inconsistent")
        self._recovery_marker_path.unlink(missing_ok=True)

    def _set_active(self, category_id: str, is_active: bool) -> Category:
        current = self._repository.list_all()
        existing = self._get_from(current, category_id)
        timestamp = self._timestamp_provider()
        updated = Category(
            existing.category_id,
            existing.category_name,
            existing.category_icon,
            is_active,
            existing.created_at_utc,
            timestamp,
        )
        intended = tuple(updated if item.category_id == category_id else item for item in current)

        def database_action() -> Category:
            if is_active:
                return self._repository.restore(category_id, timestamp)
            return self._repository.archive(category_id, timestamp)

        self._coordinate(intended, database_action, current)
        self._notify()
        return updated

    def _coordinate(
        self,
        intended: Sequence[Category],
        database_action: Callable[[], Category],
        original: Sequence[Category],
    ) -> None:
        staged = self._store.stage(intended)
        replaced = False
        try:
            self._repository.connection.execute("BEGIN IMMEDIATE")
            database_action()
            self._store.replace_staged(staged)
            replaced = True
            self._repository.connection.commit()
        except Exception as exc:
            if self._repository.connection.in_transaction:
                self._repository.connection.rollback()
            restoration_error: Exception | None = None
            if replaced:
                try:
                    self._store.restore(original)
                except Exception as restore_exc:
                    restoration_error = restore_exc
            if restoration_error is not None:
                self._write_recovery_marker(exc, restoration_error)
                message = (
                    "category update failed and automatic restoration also failed; "
                    f"recovery marker created at {self._recovery_marker_path}"
                )
            else:
                message = f"category update was not applied: {exc}"
            self._consistency_error = message
            raise CategoryPersistenceError(message) from exc
        finally:
            staged.unlink(missing_ok=True)
        self._assert_same(self._repository.list_all(), self._store.load())
        self._consistency_error = None

    def _ensure_mutation_allowed(self) -> None:
        if self._consistency_error is not None:
            raise CategoryPersistenceError(self._consistency_error)
        if self._recovery_marker_path.exists() or not self.check_consistency():
            raise CategoryPersistenceError(
                self._consistency_error
                or "category mutation is blocked until SQLite and categories.csv are reconciled"
            )

    def _protect_other(self, category_id: str, operation: str) -> None:
        if category_id == OTHER_CATEGORY_ID:
            raise ProtectedCategoryError(
                f"Other is the protected fallback category and cannot be {operation}."
            )

    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            listener()

    def _write_recovery_marker(self, error: Exception, restoration_error: Exception) -> None:
        self._recovery_marker_path.parent.mkdir(parents=True, exist_ok=True)
        self._recovery_marker_path.write_text(
            "Category consistency recovery required.\n"
            f"Original error: {error}\n"
            f"Restoration error: {restoration_error}\n",
            encoding="utf-8",
        )

    @staticmethod
    def _get_from(categories: Sequence[Category], category_id: str) -> Category:
        try:
            return next(item for item in categories if item.category_id == category_id)
        except StopIteration as exc:
            raise CategoryNotFoundError(f"category not found: {category_id}") from exc

    @staticmethod
    def _assert_same(
        database: Sequence[Category],
        portable: Sequence[Category],
        *,
        allow_database_only: bool = False,
    ) -> None:
        database_by_id = {item.category_id: item for item in database}
        portable_by_id = {item.category_id: item for item in portable}
        if len(database_by_id) != len(database) or len(portable_by_id) != len(portable):
            raise CategoryPersistenceError("duplicate category IDs detected")
        database_names = {category_uniqueness_key(item.category_name) for item in database}
        portable_names = {category_uniqueness_key(item.category_name) for item in portable}
        if len(database_names) != len(database) or len(portable_names) != len(portable):
            raise CategoryPersistenceError("duplicate normalized category names detected")
        missing_db = portable_by_id.keys() - database_by_id.keys()
        missing_csv = database_by_id.keys() - portable_by_id.keys()
        if missing_db or (missing_csv and not allow_database_only):
            raise CategoryPersistenceError(
                "SQLite/categories.csv category IDs differ; "
                f"missing from SQLite={sorted(missing_db)}, "
                f"missing from CSV={sorted(missing_csv)}"
            )
        conflicts = [
            category_id
            for category_id, database_item in database_by_id.items()
            if database_item != portable_by_id[category_id]
        ]
        if conflicts:
            raise CategoryPersistenceError(
                f"SQLite/categories.csv category fields conflict for IDs: {sorted(conflicts)}"
            )
