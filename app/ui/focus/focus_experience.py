"""Visual container for ritual, focus canvas, completion, and summary."""

from enum import StrEnum
from importlib.resources import files

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QStackedWidget, QVBoxLayout, QWidget

from app.models.focus_session_draft import FocusSessionDraft
from app.models.focus_summary import FocusSummary
from app.services.portable_preview_service import QuotePreview
from app.shortcuts.bindings import ShortcutBinding
from app.shortcuts.registry import ShortcutRegistry
from app.timer.models import TimerSnapshot
from app.ui.focus.completion_overlay import CompletionOverlay
from app.ui.focus.focus_canvas import FocusCanvas
from app.ui.focus.focus_style import enforce_black_background
from app.ui.focus.session_summary_overlay import SessionSummaryOverlay
from app.ui.focus.shortcut_help_overlay import ShortcutHelpOverlay
from app.ui.focus.start_ritual import RitualDurations, StartRitual


class FocusViewStage(StrEnum):
    INACTIVE = "inactive"
    RITUAL = "ritual"
    FOCUS = "focus"
    COMPLETION = "completion"
    SUMMARY = "summary"


class FocusExperience(QWidget):
    ritual_completed = Signal()
    ritual_cancelled = Signal()
    pause_requested = Signal()
    resume_requested = Signal()
    stop_requested = Signal()
    enter_full_screen_requested = Signal()
    exit_full_screen_requested = Signal()
    minimize_requested = Signal()
    toggle_quote_requested = Signal()
    finish_requested = Signal()
    overtime_requested = Signal()
    return_to_setup_requested = Signal()
    mark_distraction_requested = Signal()
    shortcut_help_requested = Signal()

    def __init__(
        self,
        *,
        inactivity_ms: int = 3000,
        ritual_durations: RitualDurations | None = None,
        reduced_motion: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("focusExperience")
        enforce_black_background(self)
        self.setStyleSheet(files("app.themes").joinpath("focus_screen.qss").read_text("utf-8"))
        self.stage = FocusViewStage.INACTIVE
        self._completion_presented = False
        self._help_return_widget: QWidget | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.error_label = QLabel()
        self.error_label.setStyleSheet("background:#000;color:#ff9a9a;padding:8px;")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)
        self.stack = QStackedWidget()
        self.stack.setObjectName("focusViewStack")
        enforce_black_background(self.stack)
        layout.addWidget(self.stack, 1)
        self.ritual = StartRitual(
            durations=ritual_durations,
            reduced_motion=reduced_motion,
        )
        self.canvas = FocusCanvas(inactivity_ms=inactivity_ms)
        self.completion = CompletionOverlay()
        self.summary = SessionSummaryOverlay()
        self.shortcut_help = ShortcutHelpOverlay()
        for widget in (
            self.ritual,
            self.canvas,
            self.completion,
            self.summary,
            self.shortcut_help,
        ):
            self.stack.addWidget(widget)
        self._connect_signals()

    @property
    def completion_presented(self) -> bool:
        return self._completion_presented

    @property
    def help_visible(self) -> bool:
        return self.stack.currentWidget() is self.shortcut_help

    def begin(self, draft: FocusSessionDraft, quote: QuotePreview | None) -> None:
        self.close_shortcut_help()
        self._completion_presented = False
        self.clear_error()
        self.canvas.begin(draft.category_name_snapshot, quote)

    def show_ritual(self, intention: str | None) -> None:
        self.stage = FocusViewStage.RITUAL
        self.stack.setCurrentWidget(self.ritual)
        self.ritual.start(intention)

    def show_focus(self, snapshot: TimerSnapshot) -> None:
        self.activate_focus_canvas()
        self.canvas.render_snapshot(snapshot)

    def activate_focus_canvas(self) -> None:
        """Make black canvas active immediately before the engine start boundary."""
        self.stage = FocusViewStage.FOCUS
        self.stack.setCurrentWidget(self.canvas)
        self.canvas.set_overlay_active(False)

    def render_snapshot(self, snapshot: TimerSnapshot) -> None:
        self.canvas.render_snapshot(snapshot)

    def show_completion(self, snapshot: TimerSnapshot, *, overtime_enabled: bool) -> bool:
        if self._completion_presented:
            return False
        self.close_shortcut_help()
        self._completion_presented = True
        self.stage = FocusViewStage.COMPLETION
        self.completion.present(snapshot, overtime_enabled=overtime_enabled)
        self.stack.setCurrentWidget(self.completion)
        self.canvas.set_overlay_active(True)
        return True

    def show_summary(self, summary: FocusSummary) -> None:
        self.close_shortcut_help()
        self.stage = FocusViewStage.SUMMARY
        self.summary.present(summary)
        self.stack.setCurrentWidget(self.summary)
        self.canvas.set_overlay_active(True)

    def set_full_screen(self, enabled: bool) -> None:
        self.canvas.set_full_screen(enabled)

    def set_shortcut_bindings(self, bindings: tuple[ShortcutBinding, ...]) -> None:
        self.canvas.set_shortcut_bindings(bindings)

    def toggle_shortcut_help(
        self,
        registry: ShortcutRegistry,
        bindings: tuple[ShortcutBinding, ...],
    ) -> None:
        if self.help_visible:
            self.close_shortcut_help()
            return
        self._help_return_widget = self.stack.currentWidget()
        self.shortcut_help.present(registry, bindings)
        self.stack.setCurrentWidget(self.shortcut_help)
        self.canvas.set_overlay_active(True)
        self.canvas.reveal_controls()
        self.shortcut_help.close_button.setFocus()

    def close_shortcut_help(self) -> None:
        if not self.help_visible:
            self._help_return_widget = None
            return
        target = self._help_return_widget or self.canvas
        self._help_return_widget = None
        self.stack.setCurrentWidget(target)
        self.canvas.set_overlay_active(target is not self.canvas)
        self.canvas.setFocus()

    def show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()

    def clear_error(self) -> None:
        self.error_label.clear()
        self.error_label.hide()

    def cleanup(self) -> None:
        self.close_shortcut_help()
        self.ritual.shutdown()
        self.canvas.restore_cursor()
        self.canvas.set_overlay_active(False)
        self.stage = FocusViewStage.INACTIVE
        self._completion_presented = False
        self.clear_error()

    def _connect_signals(self) -> None:
        self.ritual.completed.connect(self.ritual_completed.emit)
        self.ritual.cancelled.connect(self.ritual_cancelled.emit)
        controls = self.canvas.controls
        controls.pause_requested.connect(self.pause_requested.emit)
        controls.resume_requested.connect(self.resume_requested.emit)
        controls.stop_requested.connect(self.stop_requested.emit)
        controls.enter_full_screen_requested.connect(self.enter_full_screen_requested.emit)
        controls.exit_full_screen_requested.connect(self.exit_full_screen_requested.emit)
        controls.minimize_requested.connect(self.minimize_requested.emit)
        controls.toggle_quote_requested.connect(self.toggle_quote_requested.emit)
        controls.finish_requested.connect(self.finish_requested.emit)
        controls.overtime_requested.connect(self.overtime_requested.emit)
        controls.mark_distraction_requested.connect(self.mark_distraction_requested.emit)
        controls.shortcut_help_requested.connect(self.shortcut_help_requested.emit)
        self.completion.finish_requested.connect(self.finish_requested.emit)
        self.completion.overtime_requested.connect(self.overtime_requested.emit)
        self.summary.return_requested.connect(self.return_to_setup_requested.emit)
        self.shortcut_help.close_requested.connect(self.shortcut_help_requested.emit)
