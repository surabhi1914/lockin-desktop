from pathlib import Path

import pytest

from app.core.errors import PathContractError, ValidationError
from app.portability.csv_contracts import header_for
from app.portability.partition_manager import initialize_partition, select_partition


def test_correct_monthly_year_and_base_path(tmp_path: Path) -> None:
    selected = select_partition(tmp_path, "sessions", "2026-07-16")
    assert selected == tmp_path / "sessions" / "2026" / "sessions_2026-07.csv"
    assert selected.resolve().is_relative_to(tmp_path.resolve())


def test_part_002_and_003_with_tiny_threshold(tmp_path: Path) -> None:
    base = select_partition(tmp_path, "segments", "2026-07-16", max_file_size_bytes=1)
    assert initialize_partition(base, "segments", create_parents=True)
    part_two = select_partition(tmp_path, "segments", "2026-07-16", max_file_size_bytes=1)
    assert part_two.name == "segments_2026-07_part002.csv"
    assert initialize_partition(part_two, "segments")
    part_three = select_partition(tmp_path, "segments", "2026-07-16", max_file_size_bytes=1)
    assert part_three.name == "segments_2026-07_part003.csv"


def test_header_initialization_and_no_overwrite(tmp_path: Path) -> None:
    path = select_partition(tmp_path, "distractions", "2026-01-01")
    assert initialize_partition(path, "distractions", create_parents=True)
    original = path.read_bytes()
    assert not initialize_partition(path, "distractions")
    assert path.read_bytes() == original
    assert tuple(path.read_text(encoding="utf-8").strip().split(",")) == header_for("distractions")


def test_invalid_existing_header_rejected(tmp_path: Path) -> None:
    path = tmp_path / "sessions" / "2026" / "sessions_2026-01.csv"
    path.parent.mkdir(parents=True)
    path.write_text("bad,header\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="invalid header"):
        initialize_partition(path, "sessions")


def test_parent_creation_is_explicit(tmp_path: Path) -> None:
    path = tmp_path / "sessions" / "2026" / "sessions_2026-01.csv"
    with pytest.raises(PathContractError, match="parent"):
        initialize_partition(path, "sessions")


@pytest.mark.parametrize("entity", ["devices", "intentions", "../sessions"])
def test_invalid_entity_rejected(tmp_path: Path, entity: str) -> None:
    with pytest.raises(ValidationError, match="entity"):
        select_partition(tmp_path, entity, "2026-01-01")


def test_invalid_date_and_configuration_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        select_partition(tmp_path, "sessions", "not-a-date")
    with pytest.raises(ValidationError, match="positive"):
        select_partition(tmp_path, "sessions", "2026-01-01", max_file_size_bytes=0)
    with pytest.raises(ValidationError, match="width"):
        select_partition(tmp_path, "sessions", "2026-01-01", part_number_width=2)


def test_existing_partition_below_threshold_is_reused(tmp_path: Path) -> None:
    base = select_partition(tmp_path, "sessions", "2026-01-01")
    initialize_partition(base, "sessions", create_parents=True)
    assert select_partition(tmp_path, "sessions", "2026-01-01") == base


def test_existing_partition_directory_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "sessions" / "2026" / "sessions_2026-01.csv"
    path.mkdir(parents=True)
    with pytest.raises(PathContractError, match="not a file"):
        initialize_partition(path, "sessions")
