import os
import subprocess
from typing import Any

from PySide6.QtCore import QEvent, QProcess, Qt, QTime
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.models.manual_session import OverlapKind, SessionOverlap
from app.models.manual_session_errors import (
    ManualSessionOverlapError,
    ManualSessionValidationError,
)
from app.ui.dialogs.add_past_session_dialog import AddPastSessionDialog
from app.ui.pages.history_page import HistoryPage


def test_history_action_and_dialog_are_parented_accessible_and_cancel_is_safe(
    app_context: Any, qapp: QApplication, qtbot: Any
) -> None:
    page = app_context.window.page("history")
    assert isinstance(page, HistoryPage)
    assert page.add_past_session_button.isEnabled()
    before = app_context.connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    dialog = AddPastSessionDialog(app_context.manual_session_service, page)
    qtbot.addWidget(dialog)
    assert dialog.parentWidget() is page
    assert dialog.windowTitle() == "Add Past Focus Session"
    assert dialog.save_button.accessibleName() or dialog.save_button.text()
    assert dialog.category.accessibleName()
    dialog.reject()
    assert app_context.connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == before


def test_dialog_preview_validation_no_accidental_enter_and_save(
    app_context: Any, qapp: QApplication, qtbot: Any
) -> None:
    page = app_context.window.page("history")
    assert isinstance(page, HistoryPage)
    dialog = AddPastSessionDialog(app_context.manual_session_service, page)
    qtbot.addWidget(dialog)
    assert "Manually added — completed" in dialog.preview.text()
    dialog.actual_minutes.setValue(0)
    assert not dialog.save_button.isEnabled()
    assert "1 minute" in dialog.validation.text()
    dialog.actual_minutes.setValue(30)
    assert dialog.save_button.isEnabled()
    dialog.show()
    QTest.keyClick(dialog, Qt.Key.Key_Return)
    qapp.processEvents()
    assert dialog.isVisible()
    dialog.save_button.click()
    assert dialog.result_record is not None
    session = app_context.connection.execute("SELECT * FROM sessions").fetchone()
    assert session["entry_source"] == "manual"
    assert session["completion_reason"] == "manual_entry"


def test_manual_dialog_creates_no_process_or_unintended_parentless_window(
    app_context: Any,
    qapp: QApplication,
    qtbot: Any,
    monkeypatch: Any,
) -> None:
    attempts: list[str] = []

    def fail(api: str) -> Any:
        def record(*_args: Any, **_kwargs: Any) -> Any:
            attempts.append(api)
            raise AssertionError(f"unexpected process launch through {api}")

        return record

    for name in ("Popen", "run", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, fail(f"subprocess.{name}"))
    monkeypatch.setattr(os, "system", fail("os.system"))
    if hasattr(os, "startfile"):
        monkeypatch.setattr(os, "startfile", fail("os.startfile"))
    monkeypatch.setattr(QProcess, "start", fail("QProcess.start"))
    monkeypatch.setattr(QProcess, "startDetached", fail("QProcess.startDetached"))
    page = app_context.window.page("history")
    assert isinstance(page, HistoryPage)
    before = {widget for widget in QApplication.topLevelWidgets() if widget.isVisible()}
    dialog = AddPastSessionDialog(app_context.manual_session_service, page)
    qtbot.addWidget(dialog)
    dialog.show()
    qapp.processEvents()
    added = {widget for widget in QApplication.topLevelWidgets() if widget.isVisible()} - before
    assert added == {dialog}
    assert dialog.parentWidget() is page
    assert attempts == []
    dialog.reject()


def test_dialog_blocks_duplicate_and_confirms_partial_overlap(
    app_context: Any,
    qapp: QApplication,
    qtbot: Any,
    monkeypatch: Any,
) -> None:
    page = app_context.window.page("history")
    assert isinstance(page, HistoryPage)
    first = AddPastSessionDialog(app_context.manual_session_service, page)
    qtbot.addWidget(first)
    first.save_button.click()
    assert first.result_record is not None

    duplicate = AddPastSessionDialog(app_context.manual_session_service, page)
    qtbot.addWidget(duplicate)
    duplicate.save_button.click()
    assert duplicate.result_record is None
    assert "same time and category" in duplicate.validation.text().casefold()

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Cancel,
    )
    cancelled = AddPastSessionDialog(app_context.manual_session_service, page)
    qtbot.addWidget(cancelled)
    cancelled.start_time.setTime(QTime(19, 15))
    cancelled.save_button.click()
    assert cancelled.result_record is None

    answers: list[str] = []

    def approve(*_args: Any, **_kwargs: Any) -> QMessageBox.StandardButton:
        answers.append("approved")
        return QMessageBox.StandardButton.Save

    monkeypatch.setattr(QMessageBox, "warning", approve)
    partial = AddPastSessionDialog(app_context.manual_session_service, page)
    qtbot.addWidget(partial)
    partial.start_time.setTime(QTime(19, 15))
    partial.save_button.click()
    assert answers == ["approved"]
    assert partial.result_record is not None
    assert app_context.connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 2


def test_dialog_duration_labels_and_non_enter_key_path(
    app_context: Any,
    qapp: QApplication,
    qtbot: Any,
) -> None:
    page = app_context.window.page("history")
    assert isinstance(page, HistoryPage)
    dialog = AddPastSessionDialog(app_context.manual_session_service, page)
    qtbot.addWidget(dialog)
    assert dialog._duration_label(5400) == "1h 30m"
    assert dialog._duration_label(3600) == "1h"
    assert dialog._duration_label(1800) == "30m"
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier)
    dialog.keyPressEvent(event)
    assert not event.isAccepted()


def test_dialog_surfaces_save_and_confirmed_retry_errors(
    app_context: Any,
    qtbot: Any,
    monkeypatch: Any,
) -> None:
    page = app_context.window.page("history")
    assert isinstance(page, HistoryPage)
    service = app_context.manual_session_service

    def validation_failure(*_args: Any, **_kwargs: Any) -> Any:
        raise ManualSessionValidationError("Save validation failed")

    monkeypatch.setattr(service, "create_manual_session", validation_failure)
    invalid = AddPastSessionDialog(service, page)
    qtbot.addWidget(invalid)
    invalid.save_button.click()
    assert invalid.validation.text() == "Save validation failed"

    calls = 0

    def overlap_then_retry_failure(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ManualSessionOverlapError(
                "Partial overlap",
                SessionOverlap(OverlapKind.PARTIAL, ("existing",)),
            )
        raise ManualSessionValidationError("Retry validation failed")

    monkeypatch.setattr(service, "create_manual_session", overlap_then_retry_failure)
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Save,
    )
    retry = AddPastSessionDialog(service, page)
    qtbot.addWidget(retry)
    retry.save_button.click()
    assert calls == 2
    assert retry.validation.text() == "Retry validation failed"
