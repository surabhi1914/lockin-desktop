"""Coordinate the in-memory Phase 4 focus experience without owning timing truth."""

from collections.abc import Callable

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox

from app.audio.completion_sound import CompletionSoundService
from app.models.distraction_marker import DistractionMarker
from app.models.errors import (
    FocusSessionAlreadyActiveError,
    NoActiveFocusSessionError,
    SessionPersistenceError,
)
from app.models.focus_session_draft import FocusSessionDraft
from app.models.focus_summary import FocusSummary
from app.recovery.models import SleepResumeDecision
from app.recovery.recovery_service import RecoveryService
from app.recovery.sleep_detector import SleepDetector
from app.services.distraction_marker_service import DistractionMarkerService
from app.services.focus_quote_service import FocusQuoteService
from app.services.focus_session_coordinator import FocusSessionCoordinator
from app.services.focus_window_service import FocusWindowService
from app.services.heartbeat_service import HeartbeatService
from app.services.session_persistence_service import SessionPersistenceService
from app.services.shortcut_settings_service import ShortcutSettingsService
from app.services.tray_service import TrayService
from app.shortcuts.actions import ShortcutActionId
from app.shortcuts.bindings import ShortcutBinding
from app.shortcuts.dispatcher import ShortcutDispatcher
from app.shortcuts.errors import DistractionMarkerError
from app.shortcuts.qt_shortcut_manager import QtShortcutManager
from app.timer.enums import TimerState
from app.timer.errors import TimerError
from app.timer.models import TimerSnapshot
from app.ui.focus.focus_dialogs import (
    ExitDecision,
    StopDecision,
    ask_active_exit,
    ask_stop,
)
from app.ui.focus.focus_experience import FocusExperience, FocusViewStage
from app.ui.main_window import MainWindow
from app.ui.pages.focus_setup_page import FocusSetupPage

StopDecisionProvider = Callable[[], StopDecision]
ExitDecisionProvider = Callable[[bool], ExitDecision]
SleepDecisionProvider = Callable[[], SleepResumeDecision]


class FocusExperienceService(QObject):
    """Own visual/window flow while the coordinator and engine own session time."""

    focus_started = Signal()
    focus_ended = Signal()
    summary_ready = Signal(object)
    focus_suspended = Signal()
    focus_resumed_after_sleep = Signal()

    def __init__(
        self,
        window: MainWindow,
        setup_page: FocusSetupPage,
        coordinator: FocusSessionCoordinator,
        experience: FocusExperience,
        window_service: FocusWindowService,
        tray_service: TrayService,
        quote_service: FocusQuoteService,
        shortcut_settings_service: ShortcutSettingsService,
        distraction_marker_service: DistractionMarkerService,
        *,
        persistence_service: SessionPersistenceService | None = None,
        recovery_service: RecoveryService | None = None,
        sleep_detector: SleepDetector | None = None,
        completion_sound: CompletionSoundService | None = None,
        stop_decision_provider: StopDecisionProvider | None = None,
        exit_decision_provider: ExitDecisionProvider | None = None,
        sleep_decision_provider: SleepDecisionProvider | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent or window)
        self._window = window
        self._setup_page = setup_page
        self._coordinator = coordinator
        self._experience = experience
        self._window_service = window_service
        self._tray_service = tray_service
        self._quote_service = quote_service
        self._shortcut_settings = shortcut_settings_service
        self._distractions = distraction_marker_service
        self._persistence = persistence_service
        self._recovery = recovery_service
        self._sleep_detector = sleep_detector
        self._completion_sound = completion_sound
        self._stop_decision_provider = stop_decision_provider or (lambda: ask_stop(self._window))
        self._exit_decision_provider = exit_decision_provider or (
            lambda available: ask_active_exit(self._window, tray_available=available)
        )
        self._sleep_decision_provider = sleep_decision_provider or self._ask_sleep_decision
        self._sleep_paused = False
        self._summary: FocusSummary | None = None
        self._completion_persisted = False
        self._stop_confirmation_active = False
        self._shortcut_bindings = self._shortcut_settings.get_all()
        self.shortcut_dispatcher = ShortcutDispatcher(
            self._shortcut_settings.registry,
            self._window,
            self._experience,
            lambda: self._shortcut_bindings,
            self._shortcut_focus_active,
            self._shortcut_timer_state,
            lambda: self._window_service.is_full_screen,
            lambda: self._experience.canvas.quote_available,
            lambda: self._experience.help_visible,
            self._handle_shortcut,
        )
        self.shortcut_manager = QtShortcutManager(
            self._experience,
            self.shortcut_dispatcher,
            parent=self,
        )
        self._experience.set_shortcut_bindings(self._shortcut_bindings)
        self._heartbeat = (
            HeartbeatService(
                persistence_service,
                lambda: self._coordinator.engine.snapshot(),
                parent=self,
            )
            if persistence_service is not None
            else None
        )
        if self._heartbeat is not None:
            self._heartbeat.repeated_failure.connect(self._persistence_failure)
        self._connect()
        if self._sleep_detector is not None:
            self._sleep_detector.suspended.connect(self._system_suspend)
            self._sleep_detector.resumed.connect(self._system_resume)

    @property
    def has_active_session(self) -> bool:
        if (
            self._persistence is not None
            and self._summary is not None
            and self._summary.saved_locally
            and self._persistence.active_context is None
        ):
            return False
        return self._coordinator.has_active_session

    @property
    def current_summary(self) -> FocusSummary | None:
        return self._summary

    @property
    def stage(self) -> FocusViewStage:
        return self._experience.stage

    @property
    def distraction_markers(self) -> tuple[DistractionMarker, ...]:
        return self._distractions.markers

    def start_focus(self, draft: FocusSessionDraft) -> None:
        if self.has_active_session:
            raise FocusSessionAlreadyActiveError("a focus session is already active")
        prepared = self._coordinator.prepare(draft)
        self._distractions.clear()
        self._experience.canvas.controls.set_distraction_count(0)
        self.shortcut_manager.deactivate()
        quote = self._quote_service.select_for_session(show_quotes=draft.show_quotes)
        if self._completion_sound is not None:
            self._completion_sound.begin_session()
        self._summary = None
        self._completion_persisted = False
        self._experience.begin(draft, quote)
        self._window.enter_focus_view()
        self._tray_service.set_focus_status("LockIn — Preparing focus")
        if draft.start_in_fullscreen:
            entered = self._window_service.enter_full_screen()
            self._experience.set_full_screen(entered)
        else:
            self._experience.set_full_screen(False)
        if prepared.draft.start_ritual_enabled:
            self._experience.show_ritual(prepared.draft.temporary_intention)
        else:
            self._begin_timer()
        self.focus_started.emit()

    def request_stop(self) -> bool:
        if not self.has_active_session:
            return False
        if self._stop_confirmation_active:
            return False
        self._stop_confirmation_active = True
        try:
            if self._stop_decision_provider() is StopDecision.CONTINUE:
                return False
        finally:
            self._stop_confirmation_active = False
        return self._stop_to_summary("manual_stop")

    def request_close(self) -> bool:
        """Return True only when the caller may exit the process."""
        if not self.has_active_session:
            return True
        decision = self._exit_decision_provider(self._tray_service.available)
        if decision is ExitDecision.KEEP_FOCUSING:
            return False
        if decision is ExitDecision.MINIMIZE_TO_TRAY and self._tray_service.available:
            self._tray_service.hide_window()
            return False
        return self.end_for_exit()

    def end_for_exit(self) -> bool:
        self.shortcut_manager.deactivate()
        self._experience.ritual.shutdown()
        if self._coordinator.has_active_preview:
            try:
                snapshot = self._coordinator.stop()
                if self._persistence is not None:
                    self._persistence.finalize(snapshot, "app_close")
            except (TimerError, SessionPersistenceError) as exc:
                self._experience.show_error(str(exc))
                return False
        if self._heartbeat is not None:
            self._heartbeat.stop()
        self._coordinator.reset()
        self._window_service.restore_before_shell()
        self._experience.cleanup()
        self._tray_service.clear_focus_status()
        self._setup_page.clear_after_session()
        self._summary = None
        self._distractions.clear()
        return True

    def shutdown(self) -> None:
        self.shortcut_manager.deactivate()
        if self._heartbeat is not None:
            self._heartbeat.stop()
        if self.has_active_session:
            self.end_for_exit()
        else:
            self._experience.cleanup()

    def return_to_setup(self) -> None:
        self.shortcut_manager.deactivate()
        if self._heartbeat is not None:
            self._heartbeat.stop()
        self._coordinator.reset()
        self._window_service.restore_before_shell()
        self._experience.cleanup()
        self._window.leave_focus_view()
        self._setup_page.clear_after_session()
        self._tray_service.clear_focus_status()
        self._summary = None
        self._distractions.clear()
        self.focus_ended.emit()

    def _connect(self) -> None:
        self._experience.ritual_completed.connect(self._begin_timer)
        self._experience.ritual_cancelled.connect(self._cancel_ritual)
        self._experience.pause_requested.connect(self._pause)
        self._experience.resume_requested.connect(self._resume)
        self._experience.stop_requested.connect(self.request_stop)
        self._experience.enter_full_screen_requested.connect(self._enter_full_screen)
        self._experience.exit_full_screen_requested.connect(self._exit_full_screen)
        self._experience.minimize_requested.connect(self._window.showMinimized)
        self._experience.toggle_quote_requested.connect(self._experience.canvas.toggle_quote)
        self._experience.finish_requested.connect(self._finish_completed)
        self._experience.overtime_requested.connect(self._start_overtime)
        self._experience.return_to_setup_requested.connect(self.return_to_setup)
        self._experience.mark_distraction_requested.connect(self._mark_distraction)
        self._experience.shortcut_help_requested.connect(self._toggle_shortcut_help)
        self._coordinator.snapshot_changed.connect(self._snapshot_changed)
        self._coordinator.planned_completed.connect(self._planned_completed)
        self._window_service.window_error.connect(self._experience.show_error)
        self._window_service.recovered_to_primary.connect(self._recovered_to_primary)
        self._shortcut_settings.bindings_changed.connect(self._shortcut_bindings_changed)

    def _begin_timer(self) -> None:
        self._experience.activate_focus_canvas()
        try:
            context = self._coordinator.start_timer()
            if self._persistence is not None:
                self._persistence.start_session(context.draft, context.category, context.snapshot)
        except (
            TimerError,
            NoActiveFocusSessionError,
            FocusSessionAlreadyActiveError,
            SessionPersistenceError,
        ) as exc:
            self._coordinator.reset()
            self._window_service.restore_before_shell()
            self._experience.cleanup()
            self._window.leave_focus_view()
            self._setup_page.clear_after_session()
            self._setup_page.form_validation.set_error(str(exc))
            self._experience.show_error(str(exc))
            return
        self._experience.show_focus(context.snapshot)
        self.shortcut_manager.activate(self._shortcut_bindings)
        if self._heartbeat is not None:
            self._heartbeat.start()
        self._update_tray(context.snapshot)

    def _cancel_ritual(self) -> None:
        self.shortcut_manager.deactivate()
        self._coordinator.reset()
        self._window_service.restore_before_shell()
        self._experience.cleanup()
        self._window.leave_focus_view()
        self._setup_page.clear_after_session()
        self._tray_service.clear_focus_status()
        self._distractions.clear()
        self.focus_ended.emit()

    def _pause(self) -> None:
        self._timer_action(
            self._coordinator.pause,
            self._persistence.pause if self._persistence is not None else None,
        )

    def _resume(self) -> None:
        self._timer_action(
            self._coordinator.resume,
            self._persistence.resume if self._persistence is not None else None,
        )

    def _system_suspend(self) -> None:
        context = self._coordinator.current_context
        if context is None or self._persistence is None:
            return
        try:
            if context.snapshot.state in {TimerState.RUNNING, TimerState.OVERTIME}:
                snapshot = self._coordinator.pause()
            elif context.snapshot.state is TimerState.PAUSED:
                snapshot = context.snapshot
            else:
                return
            self._persistence.system_sleep_pause(snapshot)
            if self._recovery is not None and self._persistence.active_context is not None:
                self._recovery.record_sleep_pause(self._persistence.active_context.session_id)
        except (TimerError, SessionPersistenceError, RuntimeError) as exc:
            self._experience.show_error(str(exc))
            return
        self._sleep_paused = True
        self._experience.render_snapshot(snapshot)
        self._experience.canvas.show_feedback("LockIn paused because the computer slept.")
        self._tray_service.set_focus_status("LockIn — Paused after sleep")
        self.focus_suspended.emit()

    def _system_resume(self) -> None:
        if not self._sleep_paused:
            return
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()
        self._experience.canvas.show_feedback("LockIn paused because the computer slept.")
        decision = self._sleep_decision_provider()
        if decision is SleepResumeDecision.RESUME:
            self._resume()
            if self._recovery is not None and self._persistence is not None:
                context = self._persistence.active_context
                if context is not None:
                    self._recovery.record_sleep_resume(context.session_id)
            self._sleep_paused = False
            self.focus_resumed_after_sleep.emit()
        elif decision is SleepResumeDecision.STOP_AND_SAVE:
            self._stop_to_summary("sleep_detected")
            self._sleep_paused = False

    def _start_overtime(self) -> None:
        try:
            if self._persistence is not None:
                context = self._coordinator.current_context
                if context is None:
                    raise NoActiveFocusSessionError("there is no active session")
                self._persistence.start_overtime(context.snapshot)
            snapshot = self._coordinator.start_overtime()
        except (TimerError, NoActiveFocusSessionError, SessionPersistenceError) as exc:
            self._experience.show_error(str(exc))
            return
        self._experience.show_focus(snapshot)
        self._update_tray(snapshot)

    def _finish_completed(self) -> None:
        if not self.has_active_session:
            return
        self._stop_to_summary("timer_completed")

    def _stop_to_summary(self, completion_reason: str) -> bool:
        context = self._coordinator.current_context
        if context is None:
            return False
        try:
            snapshot = self._coordinator.stop()
            if self._persistence is not None:
                persisted = self._persistence.finalize(snapshot, completion_reason)
                summary = FocusSummary.from_persisted(persisted)
            else:
                summary = FocusSummary.from_snapshot(
                    context.category.category_name,
                    snapshot,
                    distraction_count=self._distractions.count,
                )
        except (TimerError, SessionPersistenceError) as exc:
            self._experience.show_error(str(exc))
            return False
        if self._heartbeat is not None:
            self._heartbeat.stop()
        self.shortcut_manager.deactivate()
        self._summary = summary
        self._experience.show_summary(summary)
        self._tray_service.set_focus_status("LockIn — Session saved locally")
        self.summary_ready.emit(summary)
        return True

    def _timer_action(
        self,
        action: Callable[[], TimerSnapshot],
        persist: Callable[[TimerSnapshot], None] | None = None,
    ) -> None:
        try:
            snapshot = action()
            if persist is not None:
                persist(snapshot)
        except (TimerError, NoActiveFocusSessionError, SessionPersistenceError) as exc:
            self._experience.show_error(str(exc))
            return
        self._experience.render_snapshot(snapshot)
        self._update_tray(snapshot)

    def _snapshot_changed(self, value: object) -> None:
        if not isinstance(value, TimerSnapshot):
            return
        rotated = self._quote_service.quote_for_focus(value.total_focus_seconds)
        if rotated is not None and self._experience.canvas.quote_id != rotated.quote_id:
            self._experience.canvas.set_quote(rotated)
        self._experience.render_snapshot(value)
        self._update_tray(value)
        if value.state is TimerState.COMPLETED:
            self._show_completion(value)

    def _planned_completed(self, value: object) -> None:
        if isinstance(value, TimerSnapshot):
            self._show_completion(value)

    def _show_completion(self, snapshot: TimerSnapshot) -> None:
        context = self._coordinator.current_context
        if context is None:
            return
        if self._persistence is not None and not self._completion_persisted:
            try:
                self._persistence.planned_completed(snapshot)
            except SessionPersistenceError as exc:
                self._experience.show_error(str(exc))
                return
            self._completion_persisted = True
        if self._completion_sound is not None:
            self._completion_sound.play_planned_completion(
                session_enabled=context.draft.play_completion_sound
            )
        self._experience.show_completion(
            snapshot,
            overtime_enabled=context.draft.overtime_enabled,
        )
        self._tray_service.set_focus_status("LockIn — Planned focus complete")

    def _enter_full_screen(self) -> None:
        entered = self._window_service.enter_full_screen()
        self._experience.set_full_screen(entered)

    def _exit_full_screen(self) -> None:
        self._window_service.exit_full_screen()
        self._experience.set_full_screen(False)

    def _recovered_to_primary(self) -> None:
        self._experience.set_full_screen(False)
        self._experience.show_error(
            "The focus monitor was removed. LockIn recovered windowed on the primary screen."
        )

    def _mark_distraction(self) -> None:
        context = self._coordinator.current_context
        if context is None:
            return
        try:
            snapshot = context.snapshot
            callback = None
            persistence = self._persistence
            if persistence is not None:

                def persist_marker(marker: DistractionMarker) -> None:
                    persistence.record_distraction(marker, snapshot)

                callback = persist_marker
            self._distractions.mark(
                snapshot,
                context.category,
                before_append=callback,
            )
        except (DistractionMarkerError, SessionPersistenceError) as exc:
            self._experience.show_error(str(exc))
            return
        self._experience.canvas.controls.set_distraction_count(self._distractions.count)
        self._experience.canvas.show_feedback(
            f"Distraction marked · {self._distractions.count} this session"
        )

    def _persistence_failure(self, message: str) -> None:
        if self._persistence is not None:
            self._persistence.block_new_sessions(
                "Repeated local database heartbeat failures require an application restart."
            )
        self._experience.show_error(f"Local session heartbeat failed repeatedly: {message}")

    def _toggle_shortcut_help(self) -> None:
        self._experience.toggle_shortcut_help(
            self._shortcut_settings.registry,
            self._shortcut_bindings,
        )

    def _shortcut_focus_active(self) -> bool:
        return (
            self.shortcut_manager.active
            and self._window.focus_view_active
            and self._coordinator.has_active_preview
            and self._experience.stage in {FocusViewStage.FOCUS, FocusViewStage.COMPLETION}
        )

    def _shortcut_timer_state(self) -> TimerState | None:
        context = self._coordinator.current_context
        return context.snapshot.state if context is not None else None

    def _handle_shortcut(self, action_id: ShortcutActionId) -> bool:
        state = self._shortcut_timer_state()
        if action_id is ShortcutActionId.PAUSE_RESUME:
            if state is TimerState.PAUSED:
                self._resume()
            else:
                self._pause()
            return True
        if action_id is ShortcutActionId.TOGGLE_FULLSCREEN:
            if self._window_service.is_full_screen:
                self._exit_full_screen()
            else:
                self._enter_full_screen()
            return True
        if action_id is ShortcutActionId.EXIT_FULLSCREEN:
            self._exit_full_screen()
            return True
        if action_id is ShortcutActionId.STOP_SESSION:
            self.request_stop()
            return True
        if action_id is ShortcutActionId.MARK_DISTRACTION:
            before = self._distractions.count
            self._mark_distraction()
            return self._distractions.count > before
        if action_id is ShortcutActionId.TOGGLE_QUOTE:
            self._experience.canvas.toggle_quote()
            return True
        if action_id is ShortcutActionId.SHOW_CONTROLS:
            self._experience.canvas.reveal_controls()
            return True
        if action_id is ShortcutActionId.SHOW_SHORTCUT_HELP:
            self._toggle_shortcut_help()
            return True

    def _shortcut_bindings_changed(self, value: object) -> None:
        if not isinstance(value, tuple) or not all(
            isinstance(item, ShortcutBinding) for item in value
        ):
            return
        self._shortcut_bindings = value
        self._experience.set_shortcut_bindings(value)
        self.shortcut_manager.refresh(value)

    def _update_tray(self, snapshot: TimerSnapshot) -> None:
        if snapshot.state is TimerState.PAUSED:
            status = "LockIn — Paused"
        elif snapshot.state is TimerState.COMPLETED:
            status = "LockIn — Planned focus complete"
        elif snapshot.state is TimerState.OVERTIME:
            status = f"LockIn — Overtime +{_clock_text(snapshot.overtime_seconds)}"
        elif snapshot.state is TimerState.STOPPED:
            status = "LockIn — Session stopped"
        else:
            status = f"LockIn — {_clock_text(snapshot.remaining_planned_seconds)} remaining"
        self._tray_service.set_focus_status(status)

    def _ask_sleep_decision(self) -> SleepResumeDecision:
        choice = QMessageBox.question(
            self._window,
            "Computer resumed from sleep",
            "LockIn paused because the computer slept. Resume this session or stop and save "
            "the confirmed focus time?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if choice is QMessageBox.StandardButton.Yes:
            return SleepResumeDecision.RESUME
        if choice is QMessageBox.StandardButton.No:
            return SleepResumeDecision.STOP_AND_SAVE
        return SleepResumeDecision.STAY_PAUSED


def _clock_text(seconds: int) -> str:
    safe = max(0, seconds)
    hours, remainder = divmod(safe, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
