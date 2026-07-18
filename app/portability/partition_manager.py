"""Safe monthly and size-based portable partition selection."""

import csv
import io
import re
from pathlib import Path

from app.core.constants import DEFAULT_PART_NUMBER_WIDTH, DEFAULT_PARTITION_SIZE_BYTES
from app.core.errors import PathContractError, ValidationError
from app.core.paths import safe_child
from app.core.time_utils import validate_date
from app.portability.csv_contracts import header_for

PARTITIONED_ENTITIES = frozenset({"sessions", "segments", "distractions"})


def _validate_entity(entity: str) -> None:
    if entity not in PARTITIONED_ENTITIES:
        raise ValidationError(f"Invalid partitioned entity: {entity!r}")


def select_partition(
    portable_root: Path,
    entity: str,
    local_date: str,
    *,
    max_file_size_bytes: int = DEFAULT_PARTITION_SIZE_BYTES,
    part_number_width: int = DEFAULT_PART_NUMBER_WIDTH,
    row: dict[str, str] | None = None,
) -> Path:
    """Select an existing writable partition or the next safe partition name."""
    _validate_entity(entity)
    parsed_date = validate_date(local_date)
    if max_file_size_bytes <= 0:
        raise ValidationError("Partition size threshold must be positive")
    if part_number_width < 3:
        raise ValidationError("Partition part-number width must be at least 3")

    year = f"{parsed_date.year:04d}"
    month = f"{parsed_date.year:04d}-{parsed_date.month:02d}"
    directory = safe_child(portable_root, entity, year)
    base_name = f"{entity}_{month}"
    base = safe_child(directory, f"{base_name}.csv")
    incoming_size = _encoded_size(entity, row)
    if not base.exists():
        return base

    pattern = re.compile(rf"^{re.escape(base_name)}_part(\d+)[.]csv$")
    highest_number = 1
    current = base
    if directory.exists():
        for candidate in directory.glob(f"{base_name}_part*.csv"):
            match = pattern.match(candidate.name)
            if match and int(match.group(1)) >= highest_number:
                highest_number = int(match.group(1))
                current = candidate
    _validate_partition_header(current, entity)
    if current.stat().st_size + incoming_size <= max_file_size_bytes:
        return current

    next_number = max(2, highest_number + 1)
    return safe_child(directory, f"{base_name}_part{next_number:0{part_number_width}d}.csv")


def _encoded_size(entity: str, row: dict[str, str] | None) -> int:
    if row is None:
        return 0
    buffer = io.StringIO(newline="")
    csv.DictWriter(buffer, fieldnames=header_for(entity), lineterminator="\n").writerow(row)
    return len(buffer.getvalue().encode("utf-8"))


def _validate_partition_header(path: Path, entity: str) -> None:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            actual = tuple(next(csv.reader(handle), []))
    except (OSError, UnicodeDecodeError) as exc:
        raise ValidationError(f"Existing partition cannot be read: {path}: {exc}") from exc
    if actual != header_for(entity):
        raise ValidationError(f"Existing partition has an invalid header: {path}")


def initialize_partition(path: Path, entity: str, *, create_parents: bool = False) -> bool:
    """Initialize a selected partition exactly once; return whether it was created."""
    _validate_entity(entity)
    if create_parents:
        path.parent.mkdir(parents=True, exist_ok=True)
    elif not path.parent.is_dir():
        raise PathContractError(f"Partition parent directory does not exist: {path.parent}")
    if path.exists():
        if not path.is_file():
            raise PathContractError(f"Partition path is not a file: {path}")
        _validate_partition_header(path, entity)
        return False
    with path.open("x", encoding="utf-8", newline="") as handle:
        csv.writer(handle, lineterminator="\n").writerow(header_for(entity))
    return True
