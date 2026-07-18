"""Pure-black, snapshot-driven focus canvas with responsive timer text."""

from importlib.resources import files

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QMouseEvent, QResizeEvent
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.services.portable_preview_service import QuotePreview
from app.shortcuts.bindings import ShortcutBinding
from app.timer.enums import TimerState
from app.timer.models import TimerSnapshot
from app.ui.focus.focus_controls import FocusControls
from app.ui.focus.focus_style import enforce_black_background


def format_focus_time(seconds: int) -> str:
    """Format a non-negative focus duration without deriving timing truth."""
    safe = max(0, seconds)
    hours, remainder = divmod(safe, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_overtime(seconds: int) -> str:
    safe = max(0, seconds)
    hours, remainder = divmod(safe, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"+{hours:02d}:{minutes:02d}:{secs:02d}"


class FocusCanvas(QWidget):
    """Dedicated black view; QTimer controls visibility, never elapsed time."""

    controls_visibility_changed = Signal(bool)

    def __init__(
        self,
        *,
        inactivity_ms: int = 3000,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if inactivity_ms <= 0:
            raise ValueError("inactivity_ms must be positive")
        self.setObjectName("focusCanvas")
        enforce_black_background(self)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(files("app.themes").joinpath("focus_screen.qss").read_text("utf-8"))
        self._snapshot: TimerSnapshot | None = None
        self._quote: QuotePreview | None = None
        self._quote_visible = False
        self._full_screen = False
        self._overlay_active = False
        self._cursor_hidden = False
        self._inactivity_timer = QTimer(self)
        self._inactivity_timer.setSingleShot(True)
        self._inactivity_timer.setInterval(inactivity_ms)
        self._inactivity_timer.timeout.connect(self._hide_inactive_ui)
        self._feedback_timer = QTimer(self)
        self._feedback_timer.setSingleShot(True)
        self._feedback_timer.setInterval(1500)
        self._feedback_timer.timeout.connect(self._hide_feedback)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 28, 34, 24)
        layout.setSpacing(16)
        layout.addStretch(2)
        self.category_label = QLabel()
        self.category_label.setObjectName("focusCategory")
        self.category_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.category_label.setAccessibleName("Focus category")
        layout.addWidget(self.category_label)
        self.state_label = QLabel()
        self.state_label.setObjectName("focusState")
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.state_label.setAccessibleName("Timer state")
        layout.addWidget(self.state_label)
        self.timer_label = QLabel("00:00")
        self.timer_label.setObjectName("focusTimer")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.timer_label.setAccessibleName("Focus timer")
        layout.addWidget(self.timer_label, 3)
        self.feedback_label = QLabel()
        self.feedback_label.setObjectName("focusFeedback")
        self.feedback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.feedback_label.setAccessibleName("Focus action feedback")
        self.feedback_label.hide()
        layout.addWidget(self.feedback_label)
        self.quote_label = QLabel()
        self.quote_label.setObjectName("focusQuote")
        self.quote_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.quote_label.setWordWrap(True)
        self.quote_label.setAccessibleName("Static session quote")
        layout.addWidget(self.quote_label)
        layout.addStretch(2)
        self.controls = FocusControls()
        layout.addWidget(self.controls, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.controls.installEventFilter(self)

    @property
    def controls_visible(self) -> bool:
        return self.controls.isVisibleTo(self)

    @property
    def cursor_hidden(self) -> bool:
        return self._cursor_hidden

    @property
    def quote_visible(self) -> bool:
        return self._quote_visible and self._quote is not None

    @property
    def quote_available(self) -> bool:
        return self._quote is not None

    @property
    def quote_id(self) -> str | None:
        return None if self._quote is None else self._quote.quote_id

    def begin(self, category_name: str, quote: QuotePreview | None) -> None:
        self.category_label.setText(category_name)
        self._quote = quote
        self._quote_visible = quote is not None
        self._render_quote()
        self.show_controls()
        self.restore_cursor()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def render_snapshot(self, snapshot: TimerSnapshot) -> None:
        self._snapshot = snapshot
        if snapshot.state is TimerState.OVERTIME:
            self.timer_label.setText(format_overtime(snapshot.overtime_seconds))
            self.state_label.setText("OVERTIME")
        else:
            self.timer_label.setText(format_focus_time(snapshot.remaining_planned_seconds))
            labels = {
                TimerState.PAUSED: "PAUSED",
                TimerState.COMPLETED: "COMPLETED",
                TimerState.STOPPED: "STOPPED",
            }
            self.state_label.setText(labels.get(snapshot.state, ""))
        self.controls.update_for_snapshot(
            snapshot,
            full_screen=self._full_screen,
            quote_available=self._quote is not None,
            quote_visible=self.quote_visible,
        )
        if snapshot.state in {TimerState.RUNNING, TimerState.OVERTIME} and not self._overlay_active:
            self._restart_inactivity_timer()
        else:
            self.show_controls()
            self.restore_cursor()
            self._inactivity_timer.stop()

    def set_full_screen(self, enabled: bool) -> None:
        self._full_screen = enabled
        if self._snapshot is not None:
            self.render_snapshot(self._snapshot)

    def set_shortcut_bindings(self, bindings: tuple[ShortcutBinding, ...]) -> None:
        self.controls.set_shortcut_bindings(bindings)

    def set_quote(self, quote: QuotePreview | None) -> None:
        """Replace the session snapshot quote without changing visibility preference."""
        was_visible = self._quote_visible
        self._quote = quote
        self._quote_visible = quote is not None and was_visible
        self._render_quote()
        if self._snapshot is not None:
            self.render_snapshot(self._snapshot)

    def show_feedback(self, message: str) -> None:
        self.feedback_label.setText(message)
        self.feedback_label.show()
        self._feedback_timer.start()

    def reveal_controls(self) -> None:
        self.note_pointer_activity(near_bottom=True)

    def set_overlay_active(self, active: bool) -> None:
        self._overlay_active = active
        if active:
            self.show_controls()
            self.restore_cursor()
            self._inactivity_timer.stop()
        elif self._snapshot is not None:
            self.render_snapshot(self._snapshot)

    def toggle_quote(self) -> None:
        if self._quote is None:
            return
        self._quote_visible = not self._quote_visible
        self._render_quote()
        if self._snapshot is not None:
            self.controls.update_for_snapshot(
                self._snapshot,
                full_screen=self._full_screen,
                quote_available=True,
                quote_visible=self._quote_visible,
            )

    def note_pointer_activity(self, *, near_bottom: bool = True) -> None:
        self.restore_cursor()
        if near_bottom:
            self.show_controls()
        self._restart_inactivity_timer()

    def show_controls(self) -> None:
        if not self.controls.isVisible():
            self.controls.show()
            self.controls_visibility_changed.emit(True)

    def hide_controls(self) -> None:
        if self.controls.isVisible():
            self.controls.hide()
            self.controls_visibility_changed.emit(False)

    def restore_cursor(self) -> None:
        self.unsetCursor()
        self._cursor_hidden = False

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self.note_pointer_activity(near_bottom=event.position().y() >= self.height() * 0.65)
        super().mouseMoveEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() in {QEvent.Type.MouseMove, QEvent.Type.Enter}:
            self.note_pointer_activity(near_bottom=True)
        return super().eventFilter(watched, event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        timer_size = max(52, min(220, int(min(self.width(), self.height()) * 0.22)))
        timer_font = QFont(self.timer_label.font())
        timer_font.setPixelSize(timer_size)
        timer_font.setWeight(QFont.Weight.Light)
        self.timer_label.setFont(timer_font)
        self.timer_label.setStyleSheet(
            f"font-size: {timer_size}px; font-weight: 300; background: transparent;"
        )
        category_font = QFont(self.category_label.font())
        category_size = max(16, min(34, timer_size // 5))
        category_font.setPixelSize(category_size)
        self.category_label.setFont(category_font)
        self.category_label.setStyleSheet(
            f"font-size: {category_size}px; color: #b7b7b7; background: transparent;"
        )

    def _render_quote(self) -> None:
        if not self.quote_visible or self._quote is None:
            self.quote_label.hide()
            self.quote_label.clear()
            return
        suffix = f" — {self._quote.author}" if self._quote.author else ""
        self.quote_label.setText(f"“{self._quote.text}”{suffix}")
        self.quote_label.show()

    def _hide_feedback(self) -> None:
        self.feedback_label.hide()
        self.feedback_label.clear()

    def _restart_inactivity_timer(self) -> None:
        if self._snapshot is None:
            return
        if (
            self._snapshot.state in {TimerState.RUNNING, TimerState.OVERTIME}
            and not self._inactivity_timer.isActive()
            and not self._cursor_hidden
        ):
            self._inactivity_timer.start()

    def _hide_inactive_ui(self) -> None:
        if self._snapshot is None or self._overlay_active:
            return
        if self._snapshot.state not in {TimerState.RUNNING, TimerState.OVERTIME}:
            return
        if self.controls.has_focused_control():
            self._inactivity_timer.start()
            return
        self.hide_controls()
        self.setCursor(Qt.CursorShape.BlankCursor)
        self._cursor_hidden = True
