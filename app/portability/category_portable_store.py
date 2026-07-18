"""Validated atomic storage for the permanent portable category set."""

import csv
import os
import shutil
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path

from app.core.constants import DATA_SCHEMA_VERSION
from app.core.time_utils import format_utc, utc_now
from app.models.category import Category
from app.models.errors import CategoryPersistenceError, DuplicateCategoryError
from app.portability.csv_contracts import header_for
from app.portability.csv_validation import validate_csv


class CategoryPortableStore:
    """Read and atomically replace only ``categories.csv``."""

    def __init__(
        self,
        categories_path: Path,
        *,
        backup_directory: Path,
        timestamp_provider: Callable[[], str] | None = None,
    ) -> None:
        self.path = categories_path
        self.backup_directory = backup_directory
        self._timestamp_provider = timestamp_provider or (lambda: format_utc(utc_now()))

    def load(self) -> tuple[Category, ...]:
        self._validate_file(self.path)
        try:
            with self.path.open("r", encoding="utf-8", newline="") as handle:
                categories = tuple(
                    Category(
                        category_id=row["category_id"],
                        category_name=row["category_name"],
                        category_icon=row["category_icon"] or None,
                        is_active=row["is_active"] == "true",
                        created_at_utc=row["created_at_utc"],
                        updated_at_utc=row["updated_at_utc"],
                    )
                    for row in csv.DictReader(handle)
                )
        except (OSError, KeyError, ValueError) as exc:
            raise CategoryPersistenceError(f"cannot read categories.csv: {exc}") from exc
        self._validate_set(categories)
        return categories

    def stage(self, categories: Sequence[Category]) -> Path:
        """Write and validate a temporary complete category file beside the target."""
        self._validate_set(categories)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, raw_path = tempfile.mkstemp(
            prefix=".categories-", suffix=".tmp", dir=self.path.parent
        )
        os.close(descriptor)
        staged = Path(raw_path)
        try:
            with staged.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle, lineterminator="\n")
                writer.writerow(header_for("categories"))
                for category in self._sorted(categories):
                    writer.writerow(
                        (
                            str(DATA_SCHEMA_VERSION),
                            category.category_id,
                            category.category_name,
                            category.category_icon or "",
                            "true" if category.is_active else "false",
                            category.created_at_utc,
                            category.updated_at_utc,
                        )
                    )
            self._validate_file(staged)
            return staged
        except Exception:
            staged.unlink(missing_ok=True)
            raise

    def replace_staged(self, staged: Path) -> Path | None:
        """Back up a populated target, then atomically install a validated stage."""
        self._validate_file(staged)
        if self.path.exists():
            self._validate_file(self.path)
        backup = self._backup_populated_file()
        try:
            os.replace(staged, self.path)
        except OSError as exc:
            raise CategoryPersistenceError(
                f"could not atomically replace categories.csv: {exc}"
            ) from exc
        return backup

    def write(self, categories: Sequence[Category]) -> Path | None:
        staged = self.stage(categories)
        try:
            return self.replace_staged(staged)
        finally:
            staged.unlink(missing_ok=True)

    def restore(self, categories: Sequence[Category]) -> None:
        """Restore a known prior complete set without creating another backup."""
        staged = self.stage(categories)
        try:
            os.replace(staged, self.path)
        except OSError as exc:
            raise CategoryPersistenceError(f"could not restore categories.csv: {exc}") from exc
        finally:
            staged.unlink(missing_ok=True)

    def _backup_populated_file(self) -> Path | None:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return None
        with self.path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            next(reader, None)
            if next(reader, None) is None:
                return None
        self.backup_directory.mkdir(parents=True, exist_ok=True)
        timestamp = "".join(
            character for character in self._timestamp_provider() if character.isalnum()
        )
        destination = self.backup_directory / f"categories_{timestamp}.backup.csv"
        counter = 2
        while destination.exists():
            destination = self.backup_directory / (f"categories_{timestamp}_{counter}.backup.csv")
            counter += 1
        try:
            shutil.copy2(self.path, destination)
        except OSError as exc:
            raise CategoryPersistenceError(f"could not back up categories.csv: {exc}") from exc
        return destination

    @staticmethod
    def _sorted(categories: Sequence[Category]) -> tuple[Category, ...]:
        return tuple(
            sorted(
                categories,
                key=lambda item: (
                    not item.is_active,
                    item.normalized_name,
                    item.category_id,
                ),
            )
        )

    @staticmethod
    def _validate_set(categories: Sequence[Category]) -> None:
        ids: set[str] = set()
        names: set[str] = set()
        for category in categories:
            if category.category_id in ids:
                raise DuplicateCategoryError(f"duplicate category ID: {category.category_id}")
            if category.normalized_name in names:
                raise DuplicateCategoryError(
                    f"duplicate normalized category name: {category.category_name}"
                )
            ids.add(category.category_id)
            names.add(category.normalized_name)

    @staticmethod
    def _validate_file(path: Path) -> None:
        if not path.is_file():
            raise CategoryPersistenceError(f"categories file is missing: {path}")
        issues = validate_csv(path, "categories")
        if issues:
            details = "; ".join(
                f"{issue.error_code} row {issue.row_number or 'header'}: {issue.message}"
                for issue in issues
            )
            raise CategoryPersistenceError(
                f"categories file failed validation and was not overwritten: {details}"
            )
