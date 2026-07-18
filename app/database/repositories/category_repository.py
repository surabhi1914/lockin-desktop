"""Parameterized SQLite persistence for permanent categories."""

import sqlite3

from app.models.category import Category, category_uniqueness_key, normalize_category_name
from app.models.errors import CategoryNotFoundError, DuplicateCategoryError

_CATEGORY_COLUMNS = (
    "category_id, category_name, category_icon, is_active, created_at_utc, updated_at_utc"
)


class CategoryRepository:
    """Connection-injected category operations; callers own transaction boundaries."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def list_all(self) -> tuple[Category, ...]:
        rows = self.connection.execute(
            f"SELECT {_CATEGORY_COLUMNS} FROM categories "
            "ORDER BY is_active DESC, category_name COLLATE NOCASE, category_id"
        ).fetchall()
        return tuple(_row_to_category(row) for row in rows)

    def list_active(self) -> tuple[Category, ...]:
        rows = self.connection.execute(
            f"SELECT {_CATEGORY_COLUMNS} FROM categories WHERE is_active = ? "
            "ORDER BY category_name COLLATE NOCASE, category_id",
            (1,),
        ).fetchall()
        return tuple(_row_to_category(row) for row in rows)

    def get_by_id(self, category_id: str) -> Category:
        row = self.connection.execute(
            f"SELECT {_CATEGORY_COLUMNS} FROM categories WHERE category_id = ?",
            (category_id,),
        ).fetchone()
        if row is None:
            raise CategoryNotFoundError(f"category not found: {category_id}")
        return _row_to_category(row)

    def find_by_normalized_name(self, category_name: str) -> Category | None:
        key = category_uniqueness_key(category_name)
        return next((item for item in self.list_all() if item.normalized_name == key), None)

    def create(self, category: Category) -> Category:
        duplicate = self.find_by_normalized_name(category.category_name)
        if duplicate is not None:
            raise DuplicateCategoryError(f"category name already exists: {duplicate.category_name}")
        try:
            self.connection.execute(
                "INSERT INTO categories("
                "category_id, category_name, category_icon, is_active, "
                "created_at_utc, updated_at_utc"
                ") VALUES (?, ?, ?, ?, ?, ?)",
                (
                    category.category_id,
                    category.category_name,
                    category.category_icon,
                    int(category.is_active),
                    category.created_at_utc,
                    category.updated_at_utc,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateCategoryError("category ID or name already exists") from exc
        return category

    def rename(self, category_id: str, category_name: str, updated_at_utc: str) -> Category:
        existing = self.get_by_id(category_id)
        normalized_name = normalize_category_name(category_name)
        duplicate = self.find_by_normalized_name(normalized_name)
        if duplicate is not None and duplicate.category_id != category_id:
            raise DuplicateCategoryError(f"category name already exists: {duplicate.category_name}")
        renamed = Category(
            category_id=existing.category_id,
            category_name=normalized_name,
            category_icon=existing.category_icon,
            is_active=existing.is_active,
            created_at_utc=existing.created_at_utc,
            updated_at_utc=updated_at_utc,
        )
        self.connection.execute(
            "UPDATE categories SET category_name = ?, updated_at_utc = ? WHERE category_id = ?",
            (renamed.category_name, renamed.updated_at_utc, category_id),
        )
        return renamed

    def archive(self, category_id: str, updated_at_utc: str) -> Category:
        return self._set_active(category_id, False, updated_at_utc)

    def restore(self, category_id: str, updated_at_utc: str) -> Category:
        existing = self.get_by_id(category_id)
        duplicate = self.find_by_normalized_name(existing.category_name)
        if duplicate is not None and duplicate.category_id != category_id:
            raise DuplicateCategoryError(
                f"cannot restore because the name is used by {duplicate.category_name}"
            )
        return self._set_active(category_id, True, updated_at_utc)

    def count(self) -> int:
        row = self.connection.execute("SELECT COUNT(*) FROM categories").fetchone()
        return int(row[0])

    def _set_active(self, category_id: str, is_active: bool, updated_at_utc: str) -> Category:
        existing = self.get_by_id(category_id)
        updated = Category(
            category_id=existing.category_id,
            category_name=existing.category_name,
            category_icon=existing.category_icon,
            is_active=is_active,
            created_at_utc=existing.created_at_utc,
            updated_at_utc=updated_at_utc,
        )
        self.connection.execute(
            "UPDATE categories SET is_active = ?, updated_at_utc = ? WHERE category_id = ?",
            (int(is_active), updated_at_utc, category_id),
        )
        return updated


def _row_to_category(row: sqlite3.Row | tuple[object, ...]) -> Category:
    return Category(
        category_id=str(row[0]),
        category_name=str(row[1]),
        category_icon=None if row[2] is None else str(row[2]),
        is_active=bool(row[3]),
        created_at_utc=str(row[4]),
        updated_at_utc=str(row[5]),
    )
