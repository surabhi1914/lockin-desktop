import hashlib
import sqlite3
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.models.focus_session_draft import FocusSessionDraft
from app.services.focus_session_coordinator import FocusSessionCoordinator
from app.timer import ManualClock
from tests.phase3_helpers import isolated_category_service, path_config


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _counts(connection: sqlite3.Connection) -> dict[str, int]:
    counts = {
        table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in ("sessions", "segments", "distractions", "runtime_session_state")
    }
    counts["session_sync_ledger"] = int(
        connection.execute(
            "SELECT COUNT(*) FROM sync_ledger WHERE record_type IN (?, ?, ?)",
            ("session", "segment", "distraction"),
        ).fetchone()[0]
    )
    return counts


def test_preview_writes_no_session_state_csv_or_intention(
    qapp: QApplication, tmp_path: Path
) -> None:
    config = path_config(tmp_path)
    service, connection, _ = isolated_category_service(config)
    category = service.list_active()[0]
    intention = "PRIVATE TEMPORARY INTENTION 8675309"
    protected_files = (
        config.portable_root / "categories.csv",
        config.portable_root / "daily_goals.csv",
        config.portable_root / "manifest.json",
        config.portable_root / "quotes.csv",
    )
    before_hashes = {path: _hash(path) for path in protected_files}
    before_partitions = {
        entity: tuple((config.portable_root / entity).rglob("*.csv"))
        for entity in ("sessions", "segments", "distractions")
    }
    before_counts = _counts(connection)
    clock = ManualClock()
    coordinator = FocusSessionCoordinator(service, clock_factory=lambda: clock)
    draft = FocusSessionDraft(
        60,
        category.category_id,
        category.category_name,
        intention,
        True,
        True,
        True,
        True,
        True,
        10,
    )
    try:
        coordinator.start(draft)
        clock.advance_seconds(5)
        coordinator.adapter.poll_once()
        coordinator.pause()
        clock.advance_seconds(2)
        coordinator.adapter.poll_once()
        coordinator.resume()
        coordinator.stop_and_end()
        assert coordinator.current_context is None
        assert (
            _counts(connection)
            == before_counts
            == {
                "sessions": 0,
                "segments": 0,
                "distractions": 0,
                "runtime_session_state": 0,
                "session_sync_ledger": 0,
            }
        )
        assert {path: _hash(path) for path in protected_files} == before_hashes
        assert {
            entity: tuple((config.portable_root / entity).rglob("*.csv"))
            for entity in ("sessions", "segments", "distractions")
        } == before_partitions
        assert all(intention.encode() not in path.read_bytes() for path in protected_files)
    finally:
        coordinator.shutdown()
        connection.close()
