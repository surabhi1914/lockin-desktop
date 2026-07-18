"""Local import metadata and conflict diagnostics outside portable data."""

import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path

from app.portability.import_models import ImportConflict


def store_import_metadata(connection: object, import_id: str, values: dict[str, object]) -> None:
    payload = json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    connection.execute(  # type: ignore[attr-defined]
        "INSERT OR REPLACE INTO app_metadata(key, value) VALUES (?, ?)",
        (f"portable_import/{import_id}", payload),
    )


def write_conflict_report(
    diagnostics_root: Path,
    *,
    import_id: str,
    source_root: Path,
    timestamp: str,
    conflicts: tuple[ImportConflict, ...],
) -> Path:
    diagnostics_root.mkdir(parents=True, exist_ok=True)
    path = diagnostics_root / f"import_conflicts_{import_id}.json"
    payload = {
        "import_id": import_id,
        "source_root": str(source_root),
        "timestamp_utc": timestamp,
        "conflicts": [
            {
                **asdict(conflict),
                "location": (
                    None
                    if conflict.location is None
                    else {
                        "path": str(conflict.location.path),
                        "row_number": conflict.location.row_number,
                    }
                ),
            }
            for conflict in conflicts
        ],
    }
    _write_json_atomic(path, payload)
    return path


def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    descriptor, raw = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
