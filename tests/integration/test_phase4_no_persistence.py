import hashlib
import sqlite3
from pathlib import Path

from PySide6.QtWidgets import QApplication

from tests.phase4_helpers import build_phase4_harness, focus_draft


def _hashes(paths: tuple[Path, ...]) -> dict[Path, str]:
    return {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def _counts(connection: sqlite3.Connection) -> dict[str, int]:
    values = {
        table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in ("sessions", "segments", "distractions", "runtime_session_state")
    }
    values["session_sync_ledger"] = int(
        connection.execute(
            "SELECT COUNT(*) FROM sync_ledger WHERE record_type IN (?, ?, ?)",
            ("session", "segment", "distraction"),
        ).fetchone()[0]
    )
    return values


def test_full_phase4_flow_writes_no_session_data_or_reference_csv(
    qapp: QApplication, qtbot: object, tmp_path: Path
) -> None:
    harness = build_phase4_harness(qapp, tmp_path)
    protected = tuple(
        harness.portable_root / name
        for name in (
            "categories.csv",
            "quotes.csv",
            "daily_goals.csv",
            "manifest.json",
        )
    )
    before_hashes = _hashes(protected)
    before_counts = _counts(harness.connection)  # type: ignore[arg-type]
    before_history = tuple(
        sorted(
            path
            for entity in ("sessions", "segments", "distractions")
            for path in (harness.portable_root / entity).rglob("*.csv")
        )
    )
    intention = "SECRET PHASE FOUR INTENTION 41859"
    try:
        harness.service.start_focus(
            focus_draft(harness, duration=5, ritual=False, intention=intention)
        )
        harness.clock.advance_seconds(2)
        harness.coordinator.adapter.poll_once()
        harness.coordinator.pause()
        harness.clock.advance_seconds(1)
        harness.coordinator.adapter.poll_once()
        harness.coordinator.resume()
        harness.window.showMinimized()
        harness.clock.advance_seconds(3)
        harness.coordinator.adapter.poll_once()
        harness.experience.overtime_requested.emit()
        harness.clock.advance_seconds(2)
        harness.coordinator.adapter.poll_once()
        harness.service.request_stop()
        harness.service.return_to_setup()
        harness.setup._settings.sync()

        expected_zero = {
            "sessions": 0,
            "segments": 0,
            "distractions": 0,
            "runtime_session_state": 0,
            "session_sync_ledger": 0,
        }
        assert _counts(harness.connection) == before_counts == expected_zero  # type: ignore[arg-type]
        assert _hashes(protected) == before_hashes
        after_history = tuple(
            sorted(
                path
                for entity in ("sessions", "segments", "distractions")
                for path in (harness.portable_root / entity).rglob("*.csv")
            )
        )
        assert after_history == before_history == ()
        assert harness.setup.intention_input.text() == ""
        assert all(
            "intention" not in key.casefold() for key in harness.setup._settings.qsettings.allKeys()
        )
        assert intention.encode() not in (tmp_path / "phase4-settings.ini").read_bytes()
        assert all(intention.encode() not in path.read_bytes() for path in protected)
    finally:
        harness.close()
