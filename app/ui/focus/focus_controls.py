"""Visible mouse-revealed controls for the focus canvas."""

from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QApplication, QHBoxLayout, QPushButton, QWidget

from app.shortcuts.actions import ShortcutActionId
from app.shortcuts.bindings import ShortcutBinding
from app.timer.enums import TimerState
from app.timer.models import TimerSnapshot


class FocusControls(QWidget):
    pause_requested = Signal()
    resume_requested = Signal()
    stop_requested = Signal()
    enter_full_screen_requested = Signal()
    exit_full_screen_requested = Signal()
    minimize_requested = Signal()
    toggle_quote_requested = Signal()
    finish_requested = Signal()
    overtime_requested = Signal()
    mark_distraction_requested = Signal()
    shortcut_help_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("focusControls")
        self._bindings: dict[ShortcutActionId, ShortcutBinding] = {}
        self._snapshot_hint_context: tuple[TimerSnapshot, bool, bool] | None = None
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)
        self.pause_button = self._button("Pause", "Pause focus", self.pause_requested.emit)
        self.resume_button = self._button("Resume", "Resume focus", self.resume_requested.emit)
        self.stop_button = self._button("Stop", "Stop and review session", self.stop_requested.emit)
        self.enter_full_screen_button = self._button(
            "Full Screen", "Enter full screen", self.enter_full_screen_requested.emit
        )
        self.exit_full_screen_button = self._button(
            "Exit Full Screen", "Exit full screen", self.exit_full_screen_requested.emit
        )
        self.minimize_button = self._button(
            "Minimize", "Minimize while focus continues", self.minimize_requested.emit
        )
        self.quote_button = self._button(
            "Hide Quote", "Hide or show the session quote", self.toggle_quote_requested.emit
        )
        self.distraction_button = self._button(
            "Mark Distraction",
            "Mark a simple distraction without pausing focus",
            self.mark_distraction_requested.emit,
        )
        self.help_button = self._button(
            "Shortcuts", "Show current focus shortcuts", self.shortcut_help_requested.emit
        )
        self.finish_button = self._button(
            "Finish Session", "Finish and review completed focus", self.finish_requested.emit
        )
        self.overtime_button = self._button(
            "Continue Overtime", "Continue with explicit overtime", self.overtime_requested.emit
        )
        for button in (
            self.pause_button,
            self.resume_button,
            self.stop_button,
            self.enter_full_screen_button,
            self.exit_full_screen_button,
            self.minimize_button,
            self.quote_button,
            self.distraction_button,
            self.help_button,
            self.finish_button,
            self.overtime_button,
        ):
            layout.addWidget(button)

    def update_for_snapshot(
        self,
        snapshot: TimerSnapshot,
        *,
        full_screen: bool,
        quote_available: bool,
        quote_visible: bool,
    ) -> None:
        self.pause_button.setVisible(snapshot.can_pause)
        self.pause_button.setEnabled(snapshot.can_pause)
        self.resume_button.setVisible(snapshot.can_resume)
        self.resume_button.setEnabled(snapshot.can_resume)
        self.stop_button.setVisible(snapshot.can_stop and not snapshot.planned_complete)
        self.stop_button.setEnabled(snapshot.can_stop)
        self.enter_full_screen_button.setVisible(not full_screen)
        self.exit_full_screen_button.setVisible(full_screen)
        self.quote_button.setVisible(quote_available)
        self.quote_button.setText("Hide Quote" if quote_visible else "Show Quote")
        self.finish_button.setVisible(snapshot.planned_complete)
        self.finish_button.setEnabled(snapshot.can_stop)
        self.overtime_button.setVisible(snapshot.can_start_overtime)
        self.overtime_button.setEnabled(snapshot.can_start_overtime)
        distraction_allowed = snapshot.state in {TimerState.RUNNING, TimerState.OVERTIME}
        self.distraction_button.setVisible(distraction_allowed)
        self.distraction_button.setEnabled(distraction_allowed)
        help_allowed = snapshot.state in {
            TimerState.RUNNING,
            TimerState.PAUSED,
            TimerState.COMPLETED,
            TimerState.OVERTIME,
        }
        self.help_button.setVisible(help_allowed)
        self.help_button.setEnabled(help_allowed)
        self._refresh_hints(snapshot, full_screen=full_screen, quote_available=quote_available)

    def set_shortcut_bindings(self, bindings: tuple[ShortcutBinding, ...]) -> None:
        self._bindings = {binding.action_id: binding for binding in bindings}
        if self._snapshot_hint_context is not None:
            snapshot, full_screen, quote_available = self._snapshot_hint_context
            self._refresh_hints(snapshot, full_screen=full_screen, quote_available=quote_available)

    def _refresh_hints(
        self, snapshot: TimerSnapshot, *, full_screen: bool, quote_available: bool
    ) -> None:
        self._snapshot_hint_context = (snapshot, full_screen, quote_available)
        self._set_hint(self.pause_button, ShortcutActionId.PAUSE_RESUME, snapshot.can_pause)
        self._set_hint(self.resume_button, ShortcutActionId.PAUSE_RESUME, snapshot.can_resume)
        self._set_hint(self.stop_button, ShortcutActionId.STOP_SESSION, snapshot.can_stop)
        self._set_hint(
            self.enter_full_screen_button,
            ShortcutActionId.TOGGLE_FULLSCREEN,
            not full_screen,
        )

        self._set_hint(
            self.exit_full_screen_button,
            ShortcutActionId.EXIT_FULLSCREEN,
            full_screen,
        )
        self._set_hint(self.quote_button, ShortcutActionId.TOGGLE_QUOTE, quote_available)
        self._set_hint(
            self.distraction_button,
            ShortcutActionId.MARK_DISTRACTION,
            snapshot.state in {TimerState.RUNNING, TimerState.OVERTIME},
        )
        self._set_hint(self.help_button, ShortcutActionId.SHOW_SHORTCUT_HELP, True)
        controls_binding = self._bindings.get(ShortcutActionId.SHOW_CONTROLS)
        if controls_binding is not None and controls_binding.enabled:
            self.setToolTip(f"Show focus controls (Shortcut: {controls_binding.display_text})")
        else:
            self.setToolTip("Show focus controls")

    def set_distraction_count(self, count: int) -> None:
        suffix = f" ({count})" if count else ""
        self.distraction_button.setText(f"Mark Distraction{suffix}")
        self.distraction_button.setAccessibleDescription(
            f"{count} distraction marker{'s' if count != 1 else ''} in this session"
        )

    def _set_hint(
        self, button: QPushButton, action_id: ShortcutActionId, valid_state: bool
    ) -> None:
        base = str(button.property("baseToolTip") or button.accessibleName())
        binding = self._bindings.get(action_id)
        if valid_state and binding is not None and binding.enabled:
            button.setToolTip(f"{base} (Shortcut: {binding.display_text})")
        else:
            button.setToolTip(base)

    def has_focused_control(self) -> bool:
        focused = QApplication.focusWidget()
        return focused is not None and (focused is self or self.isAncestorOf(focused))

    @staticmethod
    def _button(text: str, accessible_name: str, callback: Callable[[], None]) -> QPushButton:
        button = QPushButton(text)
        button.setAccessibleName(accessible_name)
        button.setToolTip(accessible_name)
        button.setProperty("baseToolTip", accessible_name)
        button.clicked.connect(callback)
        return button
