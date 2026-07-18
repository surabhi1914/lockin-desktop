"""Validated, backup-aware atomic CSV replacement."""

import csv
import os
import shutil
import tempfile
import time
from collections.abc import Iterable
from pathlib import Path

from app.portability.csv_contracts import header_for
from app.portability.csv_validation import validate_csv
from app.portability.errors import PortableFileLockedError, PortableValidationError


class AtomicCsvWriter:
    def __init__(self, backup_root: Path, *, retry_delays: tuple[float, ...] = (0.05, 0.15, 0.3)):
        self._backup_root = backup_root
        self._retry_delays = retry_delays

    def replace(
        self,
        path: Path,
        entity: str,
        rows: Iterable[dict[str, str]],
        *,
        backup_name: str | None = None,
    ) -> Path | None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, raw_temp = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
        )
        temporary = Path(raw_temp)
        backup: Path | None = None
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=header_for(entity), lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
                handle.flush()
                os.fsync(handle.fileno())
            issues = validate_csv(temporary, entity)
            if issues:
                detail = "; ".join(issue.message for issue in issues[:3])
                raise PortableValidationError(f"staged CSV validation failed for {path}: {detail}")
            if path.exists() and path.stat().st_size > 0:
                backup = self._backup_path(path, entity, backup_name)
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, backup)
            self._replace_with_retry(temporary, path)
            installed_issues = validate_csv(path, entity)
            if installed_issues:
                raise PortableValidationError(f"installed CSV validation failed for {path}")
            return backup
        finally:
            temporary.unlink(missing_ok=True)

    def _backup_path(self, path: Path, entity: str, name: str | None) -> Path:
        label = name or f"{path.name}.bak"
        candidate = self._backup_root / entity / label
        counter = 2
        while candidate.exists():
            candidate = self._backup_root / entity / f"{label}.{counter:03d}"
            counter += 1
        return candidate

    def _replace_with_retry(self, source: Path, destination: Path) -> None:
        last_error: PermissionError | None = None
        for attempt in range(len(self._retry_delays) + 1):
            try:
                os.replace(source, destination)
                return
            except PermissionError as exc:
                last_error = exc
                if attempt < len(self._retry_delays):
                    time.sleep(self._retry_delays[attempt])
        raise PortableFileLockedError(f"portable CSV is locked: {destination}") from last_error


def read_csv_rows(path: Path, entity: str) -> list[dict[str, str]]:
    if not path.exists():
        return []
    issues = validate_csv(path, entity)
    if issues:
        detail = "; ".join(issue.message for issue in issues[:3])
        raise PortableValidationError(f"invalid portable CSV {path}: {detail}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
