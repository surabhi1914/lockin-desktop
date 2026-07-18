"""Typed loading, validation, and atomic persistence for the portable manifest."""

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.core.constants import (
    APPLICATION_NAME,
    DATA_SCHEMA_VERSION,
    DEFAULT_PART_NUMBER_WIDTH,
    DEFAULT_PARTITION_SIZE_BYTES,
    DEFAULT_TIMEZONE,
    MANIFEST_SCHEMA_VERSION,
)
from app.core.errors import ValidationError
from app.core.time_utils import format_utc, get_timezone, parse_utc, utc_now


@dataclass(frozen=True)
class PartitioningConfig:
    strategy: str
    max_file_size_bytes: int
    part_number_width: int


@dataclass(frozen=True)
class PortableManifest:
    application: str
    manifest_schema_version: int
    data_schema_version: int
    created_at_utc: str
    updated_at_utc: str
    last_successful_sync_at_utc: str | None
    primary_timezone: str
    csv_encoding: str
    duration_unit: str
    boolean_encoding: str
    partitioning: PartitioningConfig
    entities: dict[str, dict[str, object]]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


EXPECTED_ENTITIES: dict[str, dict[str, object]] = {
    "devices": {"partitioned": False, "path": "devices.csv"},
    "categories": {"partitioned": False, "path": "categories.csv"},
    "quotes": {"partitioned": False, "path": "quotes.csv"},
    "daily_goals": {"partitioned": False, "path": "daily_goals.csv"},
    "sessions": {"partitioned": True, "directory": "sessions"},
    "segments": {"partitioned": True, "directory": "segments"},
    "distractions": {"partitioned": True, "directory": "distractions"},
}


def new_manifest() -> PortableManifest:
    timestamp = format_utc(utc_now())
    return PortableManifest(
        application=APPLICATION_NAME,
        manifest_schema_version=MANIFEST_SCHEMA_VERSION,
        data_schema_version=DATA_SCHEMA_VERSION,
        created_at_utc=timestamp,
        updated_at_utc=timestamp,
        last_successful_sync_at_utc=None,
        primary_timezone=DEFAULT_TIMEZONE,
        csv_encoding="utf-8",
        duration_unit="seconds",
        boolean_encoding="true_false_lowercase",
        partitioning=PartitioningConfig(
            strategy="monthly_then_size",
            max_file_size_bytes=DEFAULT_PARTITION_SIZE_BYTES,
            part_number_width=DEFAULT_PART_NUMBER_WIDTH,
        ),
        entities={key: dict(value) for key, value in EXPECTED_ENTITIES.items()},
    )


def _require(data: dict[str, Any], key: str, expected_type: type[Any]) -> Any:
    if key not in data:
        raise ValidationError(f"Manifest is missing required field: {key}")
    value = data[key]
    if not isinstance(value, expected_type):
        raise ValidationError(f"Manifest field {key!r} has the wrong type")
    return value


def manifest_from_dict(data: dict[str, Any]) -> PortableManifest:
    application = _require(data, "application", str)
    manifest_version = _require(data, "manifest_schema_version", int)
    data_version = _require(data, "data_schema_version", int)
    created = _require(data, "created_at_utc", str)
    updated = _require(data, "updated_at_utc", str)
    sync = data.get("last_successful_sync_at_utc")
    timezone = _require(data, "primary_timezone", str)
    encoding = _require(data, "csv_encoding", str)
    duration = _require(data, "duration_unit", str)
    boolean = _require(data, "boolean_encoding", str)
    raw_partitioning = _require(data, "partitioning", dict)
    entities = _require(data, "entities", dict)

    if application != APPLICATION_NAME:
        raise ValidationError(f"Manifest application must be {APPLICATION_NAME!r}")
    if manifest_version != MANIFEST_SCHEMA_VERSION:
        raise ValidationError(f"Unsupported manifest schema version: {manifest_version}")
    if data_version != DATA_SCHEMA_VERSION:
        raise ValidationError(f"Unsupported data schema version: {data_version}")
    parse_utc(created)
    parse_utc(updated)
    if sync is not None:
        if not isinstance(sync, str):
            raise ValidationError("last_successful_sync_at_utc must be null or a UTC timestamp")
        parse_utc(sync)
    get_timezone(timezone)
    if encoding != "utf-8" or duration != "seconds" or boolean != "true_false_lowercase":
        raise ValidationError("Manifest encoding or unit conventions are invalid")

    strategy = _require(raw_partitioning, "strategy", str)
    threshold = _require(raw_partitioning, "max_file_size_bytes", int)
    width = _require(raw_partitioning, "part_number_width", int)
    if strategy != "monthly_then_size":
        raise ValidationError("Unsupported partitioning strategy")
    if threshold <= 0:
        raise ValidationError("Partition max_file_size_bytes must be positive")
    if width < 3:
        raise ValidationError("Partition part_number_width must be at least 3")
    if entities != EXPECTED_ENTITIES:
        raise ValidationError("Manifest entity definitions do not match the Phase 0 contract")

    return PortableManifest(
        application=application,
        manifest_schema_version=manifest_version,
        data_schema_version=data_version,
        created_at_utc=created,
        updated_at_utc=updated,
        last_successful_sync_at_utc=sync,
        primary_timezone=timezone,
        csv_encoding=encoding,
        duration_unit=duration,
        boolean_encoding=boolean,
        partitioning=PartitioningConfig(strategy, threshold, width),
        entities={str(key): dict(value) for key, value in entities.items()},
    )


def load_manifest(path: Path) -> PortableManifest:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"Invalid manifest JSON at {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValidationError("Manifest root must be a JSON object")
    return manifest_from_dict(raw)


def save_manifest_atomic(path: Path, manifest: PortableManifest) -> None:
    """Validate and atomically replace a manifest using its destination directory."""
    validated = manifest_from_dict(manifest.to_dict())
    if path.exists():
        load_manifest(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(validated.to_dict(), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def create_manifest_if_absent(path: Path) -> tuple[PortableManifest, bool]:
    """Load an existing valid manifest or safely create a new one."""
    if path.exists():
        return load_manifest(path), False
    manifest = new_manifest()
    save_manifest_atomic(path, manifest)
    return manifest, True
