"""Canonical SHA-256 record checksums."""

import hashlib
import json
from collections.abc import Mapping

from app.core.errors import ValidationError

type ChecksumValue = str | int | bool | None


def canonical_record_json(record: Mapping[str, object]) -> str:
    """Serialize a flat record mapping deterministically."""
    normalized: dict[str, ChecksumValue] = {}
    for key, value in record.items():
        if not isinstance(key, str):
            raise ValidationError("Checksum record keys must be strings")
        if value is not None and not isinstance(value, (str, int, bool)):
            raise ValidationError(f"Unsupported checksum value for {key!r}: {type(value).__name__}")
        normalized[key] = value
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def record_checksum(record: Mapping[str, object]) -> str:
    """Return the lowercase SHA-256 hex digest for a canonical record."""
    payload = canonical_record_json(record).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
