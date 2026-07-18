"""In-memory handoff from validated setup to the Phase 2 timer."""

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from app.models.category import Category
from app.models.errors import FocusSessionAlreadyActiveError, NoActiveFocusSessionError
from app.models.focus_session_draft import FocusSessionDraft
from app.services.category_service import CategoryService
from app.timer.clock import Clock, MonotonicClock
from app.timer.enums import TimerState
from app.timer.models import TimerConfig, TimerSnapshot
from app.timer.qt_timer_adapter import QtTimerAdapter
from app.timer.timer_engine import TimerEngine


@dataclass(frozen=True, slots=True)
class FocusSessionContext:
    """Immutable current view of the active timer session."""

    draft: FocusSessionDraft
    category: Category
    snapshot: TimerSnapshot


@dataclass(frozen=True, slots=True)
class PreparedFocusSession:
    """Validated setup retained in memory before the ritual starts the timer."""

    draft: FocusSessionDraft
    category: Category


class FocusSessionCoordinator(QObject):
    """Own exactly one focus timer session at a time."""

    session_prepared = Signal(object)
    preview_started = Signal(object)
    preview_ended = Signal()
    snapshot_changed = Signal(object)
    state_changed = Signal(object)
    planned_completed = Signal(object)

    def __init__(
        self,
        category_service: CategoryService,
        *,
        clock_factory: Callable[[], Clock] = MonotonicClock,
        poll_interval_ms: int = 150,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._category_service = category_service
        self._clock_factory = clock_factory
        self._poll_interval_ms = poll_interval_ms
        self._draft: FocusSessionDraft | None = None
        self._category: Category | None = None
        self._engine: TimerEngine | None = None
        self._adapter: QtTimerAdapter | None = None

    @property
    def has_active_preview(self) -> bool:
        return self._engine is not None

    @property
    def has_active_session(self) -> bool:
        return self._draft is not None

    @property
    def prepared_session(self) -> PreparedFocusSession | None:
        if self._draft is None or self._category is None:
            return None
        return PreparedFocusSession(self._draft, self._category)

    @property
    def engine(self) -> TimerEngine:
        if self._engine is None:
            raise NoActiveFocusSessionError("there is no active focus-session preview")
        return self._engine

    @property
    def adapter(self) -> QtTimerAdapter:
        if self._adapter is None:
            raise NoActiveFocusSessionError("there is no active focus-session preview")
        return self._adapter

    @property
    def current_context(self) -> FocusSessionContext | None:
        if self._engine is None or self._draft is None or self._category is None:
            return None
        return FocusSessionContext(self._draft, self._category, self._engine.snapshot())

    def start(self, draft: FocusSessionDraft) -> FocusSessionContext:
        """Compatibility-friendly immediate start used outside the Phase 4 ritual."""
        self.prepare(draft)
        return self.start_timer()

    def prepare(self, draft: FocusSessionDraft) -> PreparedFocusSession:
        """Validate and retain a draft without starting or creating a timer engine."""
        if self.has_active_session:
            raise FocusSessionAlreadyActiveError(
                "end the current focus session before starting another"
            )
        category = self._category_service.resolve_selected_category(draft.category_id)
        self._draft = draft
        self._category = category
        prepared = PreparedFocusSession(draft, category)
        self.session_prepared.emit(prepared)
        return prepared

    def start_timer(self) -> FocusSessionContext:
        """Create and start the engine at the ritual-completion boundary."""
        if self._draft is None or self._category is None:
            raise NoActiveFocusSessionError("there is no prepared focus session")
        if self._engine is not None:
            raise FocusSessionAlreadyActiveError("the focus timer has already started")
        draft = self._draft
        config = TimerConfig(
            planned_duration_seconds=draft.planned_duration_seconds,
            pause_grace_seconds=draft.pause_grace_seconds,
            overtime_enabled=draft.overtime_enabled,
        )
        engine = TimerEngine(config, self._clock_factory())
        engine.start()
        adapter = QtTimerAdapter(
            engine,
            poll_interval_ms=self._poll_interval_ms,
            parent=self,
        )
        adapter.snapshot_changed.connect(self.snapshot_changed.emit)
        adapter.state_changed.connect(self.state_changed.emit)
        adapter.planned_completed.connect(self.planned_completed.emit)
        self._engine = engine
        self._adapter = adapter
        adapter.poll_once()
        adapter.start_polling()
        context = self.current_context
        if context is None:
            raise RuntimeError("focus-session preview failed to initialize")
        self.preview_started.emit(context)
        return context

    def pause(self) -> TimerSnapshot:
        self.engine.pause()
        return self._poll()

    def resume(self) -> TimerSnapshot:
        self.engine.resume()
        return self._poll()

    def start_overtime(self) -> TimerSnapshot:
        self.engine.start_overtime()
        return self._poll()

    def stop_and_end(self) -> TimerSnapshot:
        snapshot = self.stop()
        self._clear_active()
        return snapshot

    def stop(self) -> TimerSnapshot:
        """Stop the engine but retain its in-memory context for summary display."""
        engine = self.engine
        if engine.state is not TimerState.STOPPED:
            engine.stop()
        return self._poll()

    def reset(self) -> None:
        if self._engine is not None and self._engine.state is not TimerState.STOPPED:
            self._engine.stop()
        if self._draft is not None:
            self._clear_active()

    def shutdown(self) -> None:
        """Discard all preview references, including the temporary intention."""
        self.reset()

    def _poll(self) -> TimerSnapshot:
        snapshot = self.adapter.poll_once()
        if snapshot is None:
            raise RuntimeError("focus-session adapter was unexpectedly disposed")
        return snapshot

    def _clear_active(self) -> None:
        adapter = self._adapter
        self._adapter = None
        self._engine = None
        self._category = None
        self._draft = None
        if adapter is not None:
            adapter.dispose()
            adapter.deleteLater()
        self.preview_ended.emit()
