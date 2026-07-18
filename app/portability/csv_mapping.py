"""Shared canonical encoding for pure portable CSV mappers."""

from collections.abc import Mapping

from app.core.checksums import record_checksum


def csv_bool(value: bool) -> str:
    return "true" if value else "false"


def csv_optional(value: object | None) -> str:
    return "" if value is None else str(value)


def ordered_row(header: tuple[str, ...], values: Mapping[str, object]) -> dict[str, str]:
    return {column: csv_optional(values.get(column)) for column in header}


def portable_row_checksum(values: Mapping[str, str]) -> str:
    canonical = {
        key: value
        for key, value in values.items()
        if key not in {"exported_at_utc", "record_checksum"}
    }
    return record_checksum(canonical)
