"""Opt-in, privacy-safe tracing for manual past-session creation."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MANUAL_SESSION_TRACE_ENV = "LOCKIN_TRACE_MANUAL_SESSIONS"


def database_path(connection: sqlite3.Connection) -> Path:
    """Return the canonical main-database path for a SQLite connection."""
    row = connection.execute("PRAGMA database_list").fetchone()
    if row is None:
        raise RuntimeError("SQLite connection has no main database")
    raw = row["file"] if isinstance(row, sqlite3.Row) else row[2]
    return Path(str(raw)).resolve()


def trace_manual_session(
    event: str,
    *,
    connection: sqlite3.Connection | None = None,
    **details: object,
) -> None:
    """Write a development-only JSON trace without intention or credential data."""
    if os.environ.get(MANUAL_SESSION_TRACE_ENV) != "1":
        return
    record: dict[str, Any] = {
        "trace": "manual-session",
        "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "event": event,
        "code_path": _caller(),
    }
    if connection is not None:
        record["database_path"] = str(database_path(connection))
    record.update(details)
    print(json.dumps(record, ensure_ascii=True, sort_keys=True), file=sys.stderr, flush=True)


def _caller() -> str:
    frames = traceback.extract_stack(limit=8)[:-2]
    for frame in reversed(frames):
        normalized = frame.filename.replace("\\", "/")
        if normalized.endswith("/manual_session_tracing.py"):
            continue
        marker = "/app/"
        if marker in normalized:
            relative = "app/" + normalized.split(marker, 1)[1]
            return f"{relative}:{frame.lineno}:{frame.name}"
    return "unknown"
