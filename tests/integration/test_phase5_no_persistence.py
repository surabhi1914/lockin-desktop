import hashlib
import sqlite3
from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.shortcuts.actions import ShortcutActionId
from tests.phase4_helpers import build_phase4_harness, focus_draft


def counts(connection: sqlite3.Connection) -> dict[str, int]:
    result = {
        table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in ("sessions", "segments", "distractions", "runtime_session_state")
    }
    result["session_sync_ledger"] = int(
        connection.execute(
            "SELECT COUNT(*) FROM sync_ledger WHERE record_type IN (?, ?, ?)",
            ("session", "segment", "distraction"),
        ).fetchone()[0]
    )
    return result


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_shortcuts_and_markers_write_only_qsettings_not_sessions_or_portable_data(
    qapp: QApplication, tmp_path: Path
) -> None:
    harness = build_phase4_harness(qapp, tmp_path)
    before_counts = counts(harness.connection)  # type: ignore[arg-type]
    before_portable = tree_hashes(harness.portable_root)
    bindings = harness.shortcut_settings.get_all()
    custom = tuple(
        harness.shortcut_settings.validator.make_binding(item.action_id, "Ctrl+P", item.enabled)
        if item.action_id is ShortcutActionId.PAUSE_RESUME
        else replace(item)
        for item in bindings
    )
    try:
        harness.shortcut_settings.save_all(custom)
        harness.service.start_focus(focus_draft(harness))
        for _ in range(3):
            harness.experience.mark_distraction_requested.emit()
        assert harness.distractions.count == 3
        harness.service.request_stop()
        assert harness.service.current_summary is not None
        assert harness.service.current_summary.distraction_count == 3
        harness.service.return_to_setup()
        harness.shortcut_settings.qsettings.sync()
        assert (
            counts(harness.connection)
            == before_counts
            == {  # type: ignore[arg-type]
                "sessions": 0,
                "segments": 0,
                "distractions": 0,
                "runtime_session_state": 0,
                "session_sync_ledger": 0,
            }
        )
        assert tree_hashes(harness.portable_root) == before_portable
        assert not any(
            path.is_file()
            for entity in ("sessions", "segments", "distractions")
            for path in (harness.portable_root / entity).rglob("*.csv")
        )
        ini = (tmp_path / "phase4-settings.ini").read_text(encoding="utf-8")
        assert "shortcuts" in ini and "Ctrl+P" in ini
    finally:
        harness.close()


def test_no_global_hook_dependency_or_import() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8").casefold()
    sources = "\n".join(path.read_text(encoding="utf-8") for path in Path("app").rglob("*.py"))
    for forbidden in ("pynput", "import keyboard", "import win32", "pywin32"):
        assert forbidden not in pyproject
        assert forbidden not in sources.casefold()
