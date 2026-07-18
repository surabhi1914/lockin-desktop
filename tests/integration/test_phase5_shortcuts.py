from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLineEdit, QMainWindow

from app.shortcuts.actions import ShortcutActionId
from app.shortcuts.dispatcher import DispatchResult
from app.timer.enums import TimerState
from tests.phase4_helpers import build_phase4_harness, focus_draft


def activate_focus_window(harness: object, qapp: QApplication, qtbot: object) -> None:
    harness.window.show()  # type: ignore[attr-defined]
    harness.window.raise_()  # type: ignore[attr-defined]
    harness.window.activateWindow()  # type: ignore[attr-defined]
    harness.experience.canvas.setFocus()  # type: ignore[attr-defined]
    qapp.processEvents()
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: QApplication.activeWindow() is harness.window,  # type: ignore[attr-defined]
        timeout=1000,
    )


def test_actual_local_keys_pause_mark_quote_controls_and_help(
    qapp: QApplication, qtbot: object, tmp_path: Path
) -> None:
    harness = build_phase4_harness(qapp, tmp_path)
    try:
        harness.service.start_focus(focus_draft(harness))
        activate_focus_window(harness, qapp, qtbot)
        assert len(harness.service.shortcut_manager.shortcut_objects) == 8
        qtbot.keyClick(harness.experience.canvas, Qt.Key.Key_Space)  # type: ignore[attr-defined]
        assert harness.coordinator.engine.state is TimerState.PAUSED
        qtbot.keyClick(harness.experience.canvas, Qt.Key.Key_Space)  # type: ignore[attr-defined]
        assert harness.coordinator.engine.state is TimerState.RUNNING
        qtbot.keyClick(harness.experience.canvas, Qt.Key.Key_D)  # type: ignore[attr-defined]
        assert harness.distractions.count == 1
        assert harness.experience.canvas.feedback_label.text() == (
            "Distraction marked · 1 this session"
        )
        quote_text = harness.experience.canvas.quote_label.text()
        qtbot.keyClick(harness.experience.canvas, Qt.Key.Key_Q)  # type: ignore[attr-defined]
        assert not harness.experience.canvas.quote_visible
        qtbot.keyClick(harness.experience.canvas, Qt.Key.Key_Q)  # type: ignore[attr-defined]
        assert harness.experience.canvas.quote_label.text() == quote_text
        harness.experience.canvas.hide_controls()
        qtbot.keyClick(harness.experience.canvas, Qt.Key.Key_C)  # type: ignore[attr-defined]
        assert harness.experience.canvas.controls_visible
        qtbot.keyClick(  # type: ignore[attr-defined]
            harness.experience.canvas,
            Qt.Key.Key_Slash,
            Qt.KeyboardModifier.ControlModifier,
        )
        assert harness.experience.help_visible
        assert harness.experience.shortcut_help.mapping_layout.rowCount() == 8
        marker_count = harness.distractions.count
        assert (
            harness.service.shortcut_dispatcher.dispatch(ShortcutActionId.MARK_DISTRACTION)
            is DispatchResult.BLOCKED
        )
        assert harness.distractions.count == marker_count
        qtbot.keyClick(  # type: ignore[attr-defined]
            harness.experience.shortcut_help,
            Qt.Key.Key_Slash,
            Qt.KeyboardModifier.ControlModifier,
        )
        assert not harness.experience.help_visible
    finally:
        harness.close()


def test_disable_and_reassign_apply_during_focus_and_update_hints(
    qapp: QApplication, qtbot: object, tmp_path: Path
) -> None:
    harness = build_phase4_harness(qapp, tmp_path)
    try:
        harness.service.start_focus(focus_draft(harness))
        activate_focus_window(harness, qapp, qtbot)
        bindings = harness.shortcut_settings.get_all()
        disabled = tuple(
            replace(item, enabled=False)
            if item.action_id is ShortcutActionId.PAUSE_RESUME
            else item
            for item in bindings
        )
        harness.shortcut_settings.save_all(disabled)
        qtbot.keyClick(harness.experience.canvas, Qt.Key.Key_Space)  # type: ignore[attr-defined]
        assert harness.coordinator.engine.state is TimerState.RUNNING
        assert "Shortcut:" not in harness.experience.canvas.controls.pause_button.toolTip()
        reassigned = tuple(
            harness.shortcut_settings.validator.make_binding(item.action_id, "Ctrl+P", True)
            if item.action_id is ShortcutActionId.PAUSE_RESUME
            else item
            for item in disabled
        )
        harness.shortcut_settings.save_all(reassigned)
        assert "Ctrl+P" in harness.experience.canvas.controls.pause_button.toolTip()
        qtbot.keyClick(  # type: ignore[attr-defined]
            harness.experience.canvas,
            Qt.Key.Key_P,
            Qt.KeyboardModifier.ControlModifier,
        )
        assert harness.coordinator.engine.state is TimerState.PAUSED
    finally:
        harness.close()


def test_dispatcher_blocks_text_other_window_minimized_hidden_and_normal_pages(
    qapp: QApplication, qtbot: object, tmp_path: Path
) -> None:
    harness = build_phase4_harness(qapp, tmp_path, tray_available=True)
    other = QMainWindow()
    qtbot.addWidget(other)  # type: ignore[attr-defined]
    editor = QLineEdit(harness.experience)
    try:
        harness.service.start_focus(focus_draft(harness))
        activate_focus_window(harness, qapp, qtbot)
        dispatcher = harness.service.shortcut_dispatcher
        assert dispatcher.dispatch(ShortcutActionId.PAUSE_RESUME) is DispatchResult.HANDLED
        assert harness.coordinator.engine.state is TimerState.PAUSED
        assert dispatcher.dispatch(ShortcutActionId.MARK_DISTRACTION) is DispatchResult.BLOCKED
        assert harness.distractions.count == 0
        dispatcher.dispatch(ShortcutActionId.PAUSE_RESUME)
        editor.show()
        editor.setFocus()
        qapp.processEvents()
        assert dispatcher.dispatch(ShortcutActionId.MARK_DISTRACTION) is DispatchResult.BLOCKED
        editor.hide()
        harness.experience.canvas.setFocus()
        harness.window.showMinimized()
        qapp.processEvents()
        assert dispatcher.dispatch(ShortcutActionId.PAUSE_RESUME) is DispatchResult.BLOCKED
        harness.tray.hide_window()
        assert dispatcher.dispatch(ShortcutActionId.PAUSE_RESUME) is DispatchResult.BLOCKED
        harness.tray.show_window()
        other.show()
        other.activateWindow()
        qapp.processEvents()
        assert dispatcher.dispatch(ShortcutActionId.PAUSE_RESUME) is DispatchResult.BLOCKED
        other.hide()
        activate_focus_window(harness, qapp, qtbot)
        assert dispatcher.dispatch(ShortcutActionId.PAUSE_RESUME) is DispatchResult.HANDLED
        harness.service.return_to_setup()
        assert not harness.service.shortcut_manager.active
        assert dispatcher.dispatch(ShortcutActionId.PAUSE_RESUME) is DispatchResult.BLOCKED
    finally:
        other.hide()
        harness.close()


def test_fullscreen_escape_stop_once_distractions_summary_and_reset(
    qapp: QApplication, qtbot: object, tmp_path: Path
) -> None:
    harness = build_phase4_harness(qapp, tmp_path)
    try:
        harness.service.start_focus(focus_draft(harness, full_screen=False))
        activate_focus_window(harness, qapp, qtbot)
        dispatcher = harness.service.shortcut_dispatcher
        assert dispatcher.dispatch(ShortcutActionId.EXIT_FULLSCREEN) is DispatchResult.IGNORED
        assert dispatcher.dispatch(ShortcutActionId.TOGGLE_FULLSCREEN) is DispatchResult.HANDLED
        assert harness.window_service.is_full_screen
        activate_focus_window(harness, qapp, qtbot)
        assert dispatcher.dispatch(ShortcutActionId.EXIT_FULLSCREEN) is DispatchResult.HANDLED
        assert not harness.window_service.is_full_screen
        for _ in range(3):
            assert dispatcher.dispatch(ShortcutActionId.MARK_DISTRACTION) is DispatchResult.HANDLED
        calls = 0

        def cancel_once() -> object:
            nonlocal calls
            calls += 1
            assert not harness.service.request_stop()
            from app.ui.focus.focus_dialogs import StopDecision

            return StopDecision.CONTINUE

        harness.service._stop_decision_provider = cancel_once
        assert dispatcher.dispatch(ShortcutActionId.STOP_SESSION) is DispatchResult.HANDLED
        assert calls == 1 and harness.coordinator.engine.state is TimerState.RUNNING
        from app.ui.focus.focus_dialogs import StopDecision

        harness.service._stop_decision_provider = lambda: StopDecision.STOP_AND_REVIEW
        harness.service.request_stop()
        assert harness.service.current_summary is not None
        assert harness.service.current_summary.distraction_count == 3
        assert harness.experience.summary.values["distractions"].text() == "3"
        harness.service.return_to_setup()
        assert harness.distractions.count == 0
        harness.service.start_focus(focus_draft(harness))
        assert harness.distractions.count == 0
    finally:
        harness.close()
