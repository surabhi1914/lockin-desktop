from dataclasses import replace
from pathlib import Path

import pytest

from app.core.errors import ValidationError
from app.portability.manifest import (
    PartitioningConfig,
    create_manifest_if_absent,
    load_manifest,
    manifest_from_dict,
    new_manifest,
    save_manifest_atomic,
)


def test_valid_manifest_load_and_atomic_save(tmp_path: Path) -> None:
    path = tmp_path / "portable space" / "manifest.json"
    manifest = new_manifest()
    save_manifest_atomic(path, manifest)
    loaded = load_manifest(path)
    assert loaded == manifest
    assert list(path.parent.glob("*.tmp")) == []
    assert path.read_bytes().endswith(b"\n")


def test_missing_field_detection() -> None:
    data = new_manifest().to_dict()
    del data["application"]
    with pytest.raises(ValidationError, match="missing"):
        manifest_from_dict(data)


def test_invalid_schema_and_partition_threshold() -> None:
    data = new_manifest().to_dict()
    data["manifest_schema_version"] = 2
    with pytest.raises(ValidationError, match="schema"):
        manifest_from_dict(data)
    data = new_manifest().to_dict()
    partitioning = dict(data["partitioning"])  # type: ignore[arg-type]
    partitioning["max_file_size_bytes"] = 0
    data["partitioning"] = partitioning
    with pytest.raises(ValidationError, match="positive"):
        manifest_from_dict(data)


def test_invalid_existing_manifest_not_overwritten(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    original = b'{"invalid": true}\n'
    path.write_bytes(original)
    with pytest.raises(ValidationError):
        create_manifest_if_absent(path)
    assert path.read_bytes() == original
    with pytest.raises(ValidationError):
        save_manifest_atomic(path, new_manifest())
    assert path.read_bytes() == original


def test_invalid_json_reported(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(ValidationError, match="Invalid manifest JSON"):
        load_manifest(path)


def test_creation_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    first, first_created = create_manifest_if_absent(path)
    original = path.read_bytes()
    second, second_created = create_manifest_if_absent(path)
    assert first_created is True
    assert second_created is False
    assert second == first
    assert path.read_bytes() == original


def test_manifest_rejects_convention_and_entity_changes() -> None:
    data = new_manifest().to_dict()
    data["csv_encoding"] = "utf-16"
    with pytest.raises(ValidationError, match="conventions"):
        manifest_from_dict(data)
    data = new_manifest().to_dict()
    data["entities"] = {}
    with pytest.raises(ValidationError, match="entity"):
        manifest_from_dict(data)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("application", "Other", "application"),
        ("data_schema_version", 2, "data schema"),
        ("primary_timezone", "Mars/Olympus", "timezone"),
        ("last_successful_sync_at_utc", 7, "last_successful"),
    ],
)
def test_manifest_rejects_invalid_top_level_values(field: str, value: object, message: str) -> None:
    data = new_manifest().to_dict()
    data[field] = value
    with pytest.raises(ValidationError, match=message):
        manifest_from_dict(data)


def test_manifest_rejects_partition_strategy_and_width() -> None:
    data = new_manifest().to_dict()
    partitioning = dict(data["partitioning"])  # type: ignore[arg-type]
    partitioning["strategy"] = "daily"
    data["partitioning"] = partitioning
    with pytest.raises(ValidationError, match="strategy"):
        manifest_from_dict(data)
    partitioning["strategy"] = "monthly_then_size"
    partitioning["part_number_width"] = 2
    with pytest.raises(ValidationError, match="width"):
        manifest_from_dict(data)


def test_save_revalidates_manifest(tmp_path: Path) -> None:
    invalid = replace(
        new_manifest(),
        partitioning=PartitioningConfig("monthly_then_size", -1, 3),
    )
    with pytest.raises(ValidationError):
        save_manifest_atomic(tmp_path / "manifest.json", invalid)
    assert not (tmp_path / "manifest.json").exists()
