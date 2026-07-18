"""Validated, read-only Phase 1 previews of portable categories and quotes."""

import csv
from dataclasses import dataclass
from pathlib import Path

from app.portability.csv_validation import validate_csv


class PreviewDataError(RuntimeError):
    """Raised when portable preview data fails the Phase 0 contract."""


@dataclass(frozen=True)
class CategoryPreview:
    category_id: str
    name: str
    icon: str
    is_active: bool


@dataclass(frozen=True)
class QuotePreview:
    quote_id: str
    text: str
    author: str
    category: str
    is_favorite: bool = False
    is_active: bool = True


class PortablePreviewService:
    def __init__(self, portable_root: Path) -> None:
        self._portable_root = portable_root

    def categories(self) -> tuple[CategoryPreview, ...]:
        path = self._portable_root / "categories.csv"
        self._validate(path, "categories")
        with path.open("r", encoding="utf-8", newline="") as handle:
            return tuple(
                CategoryPreview(
                    category_id=row["category_id"],
                    name=row["category_name"],
                    icon=row["category_icon"],
                    is_active=row["is_active"] == "true",
                )
                for row in csv.DictReader(handle)
            )

    def active_quotes(self, *, limit: int = 5) -> tuple[QuotePreview, ...]:
        if limit < 0:
            raise ValueError("Quote preview limit cannot be negative")
        path = self._portable_root / "quotes.csv"
        self._validate(path, "quotes")
        with path.open("r", encoding="utf-8", newline="") as handle:
            active = (
                QuotePreview(
                    quote_id=row["quote_id"],
                    text=row["quote_text"],
                    author=row["author"],
                    category=row["category"],
                    is_favorite=row["is_favorite"] == "true",
                    is_active=True,
                )
                for row in csv.DictReader(handle)
                if row["is_active"] == "true"
            )
            return tuple(quote for _, quote in zip(range(limit), active, strict=False))

    def active_quote_count(self) -> int:
        path = self._portable_root / "quotes.csv"
        self._validate(path, "quotes")
        with path.open("r", encoding="utf-8", newline="") as handle:
            return sum(1 for row in csv.DictReader(handle) if row["is_active"] == "true")

    @staticmethod
    def _validate(path: Path, entity: str) -> None:
        issues = validate_csv(path, entity)
        if issues:
            summary = "; ".join(
                f"{issue.error_code} at row {issue.row_number or 'header'}: {issue.message}"
                for issue in issues
            )
            raise PreviewDataError(f"Cannot preview {entity}: {summary}")
