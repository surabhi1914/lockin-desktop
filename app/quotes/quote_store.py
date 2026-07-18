"""Validated atomic CRUD for the exact portable quotes CSV contract."""

from __future__ import annotations

import csv
import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from unicodedata import category as unicode_category

from app.core.ids import new_uuid4
from app.portability.atomic_csv_writer import AtomicCsvWriter, read_csv_rows
from app.portability.csv_validation import validate_csv


@dataclass(frozen=True, slots=True)
class QuoteRecord:
    quote_id: str
    text: str
    author: str = ""
    category: str = "custom"
    is_active: bool = True
    is_favorite: bool = False


class QuoteStore:
    def __init__(self, path: Path, backup_root: Path) -> None:
        self.path = path
        self._writer = AtomicCsvWriter(backup_root)

    def list_all(self) -> tuple[QuoteRecord, ...]:
        return tuple(self._from_row(row) for row in read_csv_rows(self.path, "quotes"))

    def add(self, text: str, author: str = "", category: str = "custom") -> QuoteRecord:
        record = QuoteRecord(f"custom-{new_uuid4()}", text, author, category)
        records = (*self.list_all(), self._validated(record))
        self._save(records)
        return records[-1]

    def update(
        self,
        quote_id: str,
        *,
        text: str | None = None,
        author: str | None = None,
        category: str | None = None,
        is_active: bool | None = None,
        is_favorite: bool | None = None,
    ) -> QuoteRecord:
        records = list(self.list_all())
        for index, record in enumerate(records):
            if record.quote_id == quote_id:
                updated = self._validated(
                    replace(
                        record,
                        text=record.text if text is None else text,
                        author=record.author if author is None else author,
                        category=record.category if category is None else category,
                        is_active=record.is_active if is_active is None else is_active,
                        is_favorite=(record.is_favorite if is_favorite is None else is_favorite),
                    )
                )
                records[index] = updated
                self._save(records)
                return updated
        raise LookupError(f"quote not found: {quote_id}")

    def set_active(self, quote_id: str, active: bool) -> QuoteRecord:
        return self.update(quote_id, is_active=active)

    def set_favorite(self, quote_id: str, favorite: bool) -> QuoteRecord:
        return self.update(quote_id, is_favorite=favorite)

    def import_validated(self, source: Path) -> int:
        issues = validate_csv(source, "quotes")
        if issues:
            raise ValueError("invalid quote CSV: " + "; ".join(item.message for item in issues[:3]))
        with source.open(encoding="utf-8", newline="") as handle:
            records = tuple(self._validated(self._from_row(row)) for row in csv.DictReader(handle))
        self._ensure_unique(records)
        self._save(records)
        return len(records)

    def export_copy(self, destination: Path) -> None:
        if destination.resolve() == self.path.resolve():
            raise ValueError("export destination must differ from the managed quote CSV")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.tmp")
        try:
            shutil.copy2(self.path, temporary)
            if validate_csv(temporary, "quotes"):
                raise ValueError("managed quote CSV failed validation")
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)

    def _save(self, records: tuple[QuoteRecord, ...] | list[QuoteRecord]) -> None:
        self._ensure_unique(records)
        self._writer.replace(
            self.path,
            "quotes",
            (self._to_row(self._validated(record)) for record in records),
        )

    @staticmethod
    def _validated(record: QuoteRecord) -> QuoteRecord:
        text = QuoteStore._text(record.text, "quote", 500, required=True)
        author = QuoteStore._text(record.author, "author", 120)
        category = QuoteStore._text(record.category, "category", 60)
        if not record.quote_id.strip() or any(
            unicode_category(char) == "Cc" for char in record.quote_id
        ):
            raise ValueError("quote ID is invalid")
        if not isinstance(record.is_active, bool) or not isinstance(record.is_favorite, bool):
            raise ValueError("quote flags must be Boolean")
        return replace(record, text=text, author=author, category=category)

    @staticmethod
    def _text(value: str, label: str, maximum: int, *, required: bool = False) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{label} must be text")
        normalized = " ".join(value.strip().split())
        if required and not normalized:
            raise ValueError(f"{label} cannot be empty")
        if len(normalized) > maximum:
            raise ValueError(f"{label} cannot exceed {maximum} characters")
        if any(unicode_category(char) == "Cc" for char in normalized):
            raise ValueError(f"{label} cannot contain control characters")
        return normalized

    @staticmethod
    def _ensure_unique(records: tuple[QuoteRecord, ...] | list[QuoteRecord]) -> None:
        ids = [record.quote_id for record in records]
        if len(ids) != len(set(ids)):
            raise ValueError("quote IDs must be unique")

    @staticmethod
    def _from_row(row: dict[str, str]) -> QuoteRecord:
        return QuoteRecord(
            row["quote_id"],
            row["quote_text"],
            row["author"],
            row["category"],
            row["is_active"] == "true",
            row["is_favorite"] == "true",
        )

    @staticmethod
    def _to_row(record: QuoteRecord) -> dict[str, str]:
        return {
            "quote_id": record.quote_id,
            "quote_text": record.text,
            "author": record.author,
            "category": record.category,
            "is_active": str(record.is_active).lower(),
            "is_favorite": str(record.is_favorite).lower(),
        }
