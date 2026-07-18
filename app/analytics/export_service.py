"""Explicit atomic statistics CSV export, separate from portable raw history."""

import csv
import os
import tempfile
from pathlib import Path

from app.analytics.models import StatisticsResult

EXPORT_HEADER = (
    "date",
    "focus_seconds",
    "goal_seconds",
    "session_count",
    "longest_block_seconds",
    "pause_seconds",
    "distraction_count",
)


class StatisticsExportService:
    def __init__(self, portable_root: Path) -> None:
        self._portable_root = portable_root.resolve()

    def export(self, result: StatisticsResult, destination: Path) -> Path:
        resolved = destination.resolve()
        if resolved == self._portable_root or self._portable_root in resolved.parents:
            raise ValueError("statistics export must be outside portable raw data")
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, raw = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
        )
        temporary = Path(raw)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=EXPORT_HEADER, lineterminator="\n")
                writer.writeheader()
                for row in result.daily:
                    writer.writerow(
                        {
                            "date": row.local_date,
                            "focus_seconds": row.focus_seconds,
                            "goal_seconds": row.goal_seconds,
                            "session_count": row.session_count,
                            "longest_block_seconds": row.longest_block_seconds,
                            "pause_seconds": row.pause_seconds,
                            "distraction_count": row.distraction_count,
                        }
                    )
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination
