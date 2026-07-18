import csv
from pathlib import Path

import pytest
from PySide6.QtCore import QDate
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
)

from app.analytics.analytics_service import AnalyticsService
from app.analytics.export_service import StatisticsExportService
from app.analytics.history_service import HistoryService
from app.dashboard.models import DashboardSnapshot
from app.portability.csv_contracts import header_for
from app.quotes.quote_store import QuoteStore
from app.recovery.models import RecoveryAction, RecoveryAnalysis, RecoveryType
from app.shortcuts.errors import ShortcutError
from app.ui.dialogs.recovery_dialog import RecoveredSessionReviewDialog, RecoveryDialog
from app.ui.focus.focus_dialogs import ExitDecision, StopDecision, ask_active_exit, ask_stop
from app.ui.pages.history_page import HistoryPage, SessionDetailDialog
from app.ui.pages.home_page import HomePage
from app.ui.pages.quotes_page import QuotesPage
from app.ui.pages.settings_page import SettingsPage
from app.ui.pages.statistics_page import StatisticsPage
from tests.integration.test_phase12_analytics import _fixture


def _analysis() -> RecoveryAnalysis:
    return RecoveryAnalysis(
        recovery_event_id="event-1",
        session_id="session-1",
        category_name="Writing",
        planned_focus_seconds=1800,
        confirmed_planned_focus_seconds=900,
        confirmed_overtime_seconds=60,
        confirmed_pause_seconds=30,
        confirmed_wall_clock_seconds=990,
        last_heartbeat_at_utc="2026-07-17T12:16:30Z",
        confirmed_boundary_at_utc="2026-07-17T12:16:30Z",
        detected_at_utc="2026-07-17T12:20:00Z",
        unknown_gap_seconds=210,
        original_timer_state="running_planned",
        open_segment_id="segment-1",
        open_segment_type="focus",
        recovery_type=RecoveryType.CRASH,
        can_resume_after_sleep=False,
        recommended_action=RecoveryAction.SAVE_CONFIRMED,
        warnings=("Unconfirmed time was excluded.",),
    )


@pytest.mark.parametrize(
    ("label", "expected"),
    (
        ("Continue Session", StopDecision.CONTINUE),
        ("Stop and Review", StopDecision.STOP_AND_REVIEW),
    ),
)
def test_stop_dialog_decisions(qtbot, monkeypatch, label: str, expected: StopDecision) -> None:
    parent = QPushButton()
    qtbot.addWidget(parent)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(
        QMessageBox,
        "clickedButton",
        lambda self: next(button for button in self.buttons() if button.text() == label),
    )
    assert ask_stop(parent) is expected


@pytest.mark.parametrize(
    ("available", "label", "expected"),
    (
        (False, "Keep Focusing", ExitDecision.KEEP_FOCUSING),
        (True, "Minimize to Tray", ExitDecision.MINIMIZE_TO_TRAY),
        (True, "End Session and Exit", ExitDecision.END_AND_EXIT),
    ),
)
def test_active_exit_dialog_decisions(
    qtbot, monkeypatch, available: bool, label: str, expected: ExitDecision
) -> None:
    parent = QPushButton()
    qtbot.addWidget(parent)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(
        QMessageBox,
        "clickedButton",
        lambda self: next(button for button in self.buttons() if button.text() == label),
    )
    assert ask_active_exit(parent, tray_available=available) is expected


@pytest.mark.parametrize(
    ("label", "result"),
    (
        ("Save Confirmed Time", RecoveryDialog.SAVE_CONFIRMED),
        ("Discard Session", RecoveryDialog.DISCARD),
        ("Review Details", RecoveryDialog.REVIEW),
        ("Exit", RecoveryDialog.EXIT),
    ),
)
def test_recovery_choice_and_review_dialogs(qtbot, label: str, result: int) -> None:
    dialog = RecoveryDialog(_analysis())
    qtbot.addWidget(dialog)
    button = next(item for item in dialog.findChildren(QPushButton) if item.text() == label)
    button.click()
    assert dialog.result() == result
    review = RecoveredSessionReviewDialog(_analysis())
    qtbot.addWidget(review)
    assert any("Unknown window: 210s" in item.text() for item in review.findChildren(QLabel))


def _quote_store(tmp_path: Path) -> QuoteStore:
    path = tmp_path / "quotes.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header_for("quotes"), lineterminator="\n")
        writer.writeheader()
        writer.writerow(
            {
                "quote_id": "q1",
                "quote_text": "Begin now",
                "author": "Ada",
                "category": "focus",
                "is_active": "true",
                "is_favorite": "false",
            }
        )
    return QuoteStore(path, tmp_path / "backups")


def test_quote_page_crud_filters_import_export_and_failure(
    qtbot, monkeypatch, tmp_path: Path
) -> None:
    store = _quote_store(tmp_path)
    page = QuotesPage(store)
    qtbot.addWidget(page)
    values = iter((("A deliberate step", True), ("Grace", True)))
    monkeypatch.setattr(QInputDialog, "getMultiLineText", lambda *args: next(values))
    monkeypatch.setattr(QInputDialog, "getText", lambda *args: next(values))
    page._add()
    assert len(store.list_all()) == 2

    page.table.selectRow(1)
    monkeypatch.setattr(QInputDialog, "getMultiLineText", lambda *args: ("Edited", True))
    page._edit()
    page.table.selectRow(1)
    page._toggle_favorite()
    page.table.selectRow(1)
    page._toggle_active()
    assert store.list_all()[1].text == "Edited"

    page.search.setText("begin")
    assert len(page.quote_rows) == 1
    page.search.clear()
    page.active_filter.setCurrentIndex(1)
    assert len(page.quote_rows) == 1
    page.active_filter.setCurrentIndex(0)

    source = tmp_path / "source.csv"
    store.export_copy(source)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(source), "CSV"))
    page._import()
    destination = tmp_path / "export" / "copy.csv"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(destination), "CSV"))
    page._export()
    assert destination.exists()

    warnings: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _p, _t, message: warnings.append(message))
    page._mutate(lambda: store.add(""))
    assert warnings and "cannot be empty" in warnings[0]


def test_history_page_filters_paging_details_and_clipboard(
    qtbot, monkeypatch, tmp_path: Path
) -> None:
    connection, _devices, _categories = _fixture(tmp_path)
    history = HistoryService(connection)
    page = HistoryPage(history_service=history)
    qtbot.addWidget(page)
    assert page.table.rowCount() == 4
    page.search.setText("Fixture")
    page.overtime_only.setChecked(True)
    page.distraction_only.setChecked(True)
    page.minimum_minutes.setValue(1)
    page.maximum_minutes.setValue(60)
    page.from_date.setDate(QDate(2026, 7, 1))
    page.to_date.setDate(QDate(2026, 7, 31))
    assert page.table.rowCount() == 1
    page._next()
    page._previous()
    page.table.selectRow(0)
    detail = history.detail(page._session_ids[0])
    dialog = SessionDetailDialog(detail)
    qtbot.addWidget(dialog)
    copy = next(
        item for item in dialog.findChildren(QPushButton) if item.text() == "Copy full session ID"
    )
    copy.click()
    assert QApplication.clipboard().text() == detail.session.session_id
    monkeypatch.setattr(SessionDetailDialog, "exec", lambda self: 0)
    page._details()
    connection.close()


def test_statistics_page_filters_render_export_and_failures(
    qtbot, monkeypatch, tmp_path: Path
) -> None:
    connection, devices, _categories = _fixture(tmp_path)
    analytics = AnalyticsService(connection, current_device_id=devices[0])
    history = HistoryService(connection)
    exporter = StatisticsExportService(tmp_path / "portable")
    page = StatisticsPage(analytics, history, exporter)
    qtbot.addWidget(page)
    page.from_date.setDate(QDate(2026, 7, 16))
    page.to_date.setDate(QDate(2026, 7, 17))
    page.refresh()
    assert page.last_result is not None and page.last_result.session_count == 4
    assert page._percent(None)
    page.preset.setCurrentIndex(1)
    page.heatmap_goal_mode.setChecked(True)
    destination = tmp_path / "reports" / "statistics.csv"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(destination), "CSV"))
    messages: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda _p, _t, message: messages.append(message)
    )
    page._export()
    assert destination.exists() and messages
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args: (str(tmp_path / "portable" / "bad.csv"), "CSV"),
    )
    monkeypatch.setattr(QMessageBox, "warning", lambda _p, _t, message: messages.append(message))
    page._export()
    assert any("outside portable" in message for message in messages)
    connection.close()


class _Dashboard:
    def __init__(self, snapshot: DashboardSnapshot) -> None:
        self.value = snapshot
        self.invalidated = False

    def snapshot(self) -> DashboardSnapshot:
        return self.value

    def invalidate(self) -> None:
        self.invalidated = True


class _Goals:
    def __init__(self) -> None:
        self.listener = lambda: None
        self.saved: tuple[int, object] | None = None

    def subscribe(self, listener):
        self.listener = listener
        return lambda: None

    def effective_on(self, _local_date):
        return None

    def set_goal(self, seconds: int, effective_date: object) -> None:
        self.saved = (seconds, effective_date)


@pytest.mark.parametrize("goal,ratio", ((None, None), (0, None), (3600, 0.5)))
def test_home_dashboard_goal_render_and_save(qtbot, goal: int | None, ratio: float | None) -> None:
    snapshot = DashboardSnapshot(
        local_date="2026-07-17",
        today_focus_seconds=1800,
        today_goal_seconds=goal,
        today_progress_ratio=ratio,
        yesterday_focus_seconds=1200,
        current_week_seconds=7200,
        prior_week_same_point_seconds=6000,
        today_longest_block_seconds=900,
        personal_longest_block_seconds=3600,
        goal_streak_days=2,
        motivation_message="One clear step.",
        has_focus_history=True,
    )
    dashboard = _Dashboard(snapshot)
    goals = _Goals()
    page = HomePage(dashboard, goals)  # type: ignore[arg-type]
    qtbot.addWidget(page)
    page.goal_minutes.setValue(45)
    page.goal_effective_date.setDate(QDate.currentDate())
    page._save_goal()
    assert goals.saved is not None and goals.saved[0] == 2700
    assert dashboard.invalidated
    no_services = HomePage()
    qtbot.addWidget(no_services)
    assert "small start" in no_services.motivation.text()


def test_settings_secondary_actions_and_error_paths(
    app_context, monkeypatch, tmp_path: Path
) -> None:
    page = app_context.window.page("settings")
    assert isinstance(page, SettingsPage)
    page._sync_now()
    assert page.sync_status_label.text()
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda _url: True)
    page._open_portable_folder()

    selected = tmp_path / "selected-portable"
    selected.mkdir()
    received: list[Path] = []
    page.set_portable_import_handler(received.append)
    monkeypatch.setattr(
        "app.ui.pages.settings_page.select_portable_data_folder",
        lambda *_args: selected,
    )
    page._request_portable_import()
    assert received == [selected]

    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Cancel)
    page._confirm_reset_all_shortcuts()
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Reset)
    page._confirm_reset_all_shortcuts()
    page._reset_shortcut_row(object())
    page._reset_shortcut_row("not-an-action")

    monkeypatch.setattr(
        app_context.shortcut_settings_service,
        "save_all",
        lambda _bindings: (_ for _ in ()).throw(ShortcutError("test conflict")),
    )
    page.apply_shortcuts()
    assert not page.shortcut_apply_button.isEnabled()
    page._preview_sound()
