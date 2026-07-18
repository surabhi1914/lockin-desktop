"""Single-thread-owned, GUI-independent timer engine.

The engine is intended to be called only by its owning thread (the Qt GUI thread
in the desktop app). It deliberately contains no locks, threads, sleeps, wall
clock reads, persistence, or UI refresh-count timing.
"""

from dataclasses import replace

from app.timer.clock import NANOSECONDS_PER_SECOND, Clock, MonotonicClock
from app.timer.continuous_blocks import (
    calculate_continuous_blocks,
    summarize_block_durations,
)
from app.timer.enums import FocusPhase, TimerEventType, TimerState
from app.timer.errors import ClockRegressionError, InvalidTimerTransitionError, TimerError
from app.timer.events import EventDetails, TimerEvent
from app.timer.models import FocusInterval, PauseInterval, TimerConfig, TimerSnapshot


class TimerEngine:
    """Accurate in-memory timer driven exclusively by an injected monotonic clock."""

    def __init__(self, config: TimerConfig, clock: Clock | None = None) -> None:
        self._config = config
        self._clock = clock or MonotonicClock()
        self._state = TimerState.IDLE
        self._paused_return_state: TimerState | None = None
        self._first_start_ns: int | None = None
        self._last_sync_ns: int | None = None
        self._last_observed_ns: int | None = None
        self._stop_offset_ns: int | None = None
        self._completion_offset_ns: int | None = None
        self._planned_focus_ns = 0
        self._overtime_ns = 0
        self._pause_ns = 0
        self._pause_start_offset_ns: int | None = None
        self._pause_count = 0
        self._short_pause_count = 0
        self._long_pause_count = 0
        self._focus_intervals: list[FocusInterval] = []
        self._pause_intervals: list[PauseInterval] = []
        self._active_focus_start_offset_ns: int | None = None
        self._active_focus_phase: FocusPhase | None = None
        self._completion_emitted = False
        self._events: list[TimerEvent] = []
        self._event_sequence = 0
        self._version = 0
        self._last_snapshot_signature: TimerSnapshot | None = None
        self._terminal_snapshot: TimerSnapshot | None = None
        self._last_snapshot_signature = replace(self._build_snapshot(None), version=0)

    @property
    def config(self) -> TimerConfig:
        return self._config

    @property
    def state(self) -> TimerState:
        return self._state

    def start(self) -> TimerSnapshot:
        if self._state is not TimerState.IDLE:
            self._invalid("start")
        now_ns = self._observe_clock()
        self._first_start_ns = now_ns
        self._last_sync_ns = now_ns
        self._state = TimerState.RUNNING
        self._active_focus_start_offset_ns = 0
        self._active_focus_phase = FocusPhase.PLANNED
        self._emit(TimerEventType.TIMER_STARTED, 0)
        self.validate_invariants()
        return self.snapshot()

    def pause(self) -> TimerSnapshot:
        now_ns = self._observe_clock()
        self._synchronize(now_ns)
        if self._state not in {TimerState.RUNNING, TimerState.OVERTIME}:
            self._invalid("pause")
        offset_ns = self._offset(now_ns)
        return_state = self._state
        self._close_active_focus(offset_ns)
        self._state = TimerState.PAUSED
        self._paused_return_state = return_state
        self._pause_start_offset_ns = offset_ns
        self._emit(
            TimerEventType.TIMER_PAUSED,
            offset_ns,
            (("return_state", return_state.value),),
        )
        self.validate_invariants()
        return self.snapshot()

    def resume(self) -> TimerSnapshot:
        now_ns = self._observe_clock()
        self._synchronize(now_ns)
        if self._state is not TimerState.PAUSED or self._paused_return_state is None:
            self._invalid("resume")
        offset_ns = self._offset(now_ns)
        return_state = self._paused_return_state
        assert return_state is not None
        pause_duration_ns = self._finalize_pause(offset_ns)
        self._state = return_state
        self._paused_return_state = None
        self._active_focus_start_offset_ns = offset_ns
        self._active_focus_phase = (
            FocusPhase.PLANNED if return_state is TimerState.RUNNING else FocusPhase.OVERTIME
        )
        self._emit(
            TimerEventType.TIMER_RESUMED,
            offset_ns,
            (("pause_duration_ns", pause_duration_ns),),
        )
        self.validate_invariants()
        return self.snapshot()

    def stop(self) -> TimerSnapshot:
        if self._state is TimerState.IDLE:
            self._invalid("stop")
        if self._state is TimerState.STOPPED:
            self._invalid("stop")
        now_ns = self._observe_clock()
        self._synchronize(now_ns)
        offset_ns = self._offset(now_ns)
        prior_state = self._state
        if self._state in {TimerState.RUNNING, TimerState.OVERTIME}:
            self._close_active_focus(offset_ns)
        elif self._state is TimerState.PAUSED:
            self._finalize_pause(offset_ns)
            self._paused_return_state = None
        self._state = TimerState.STOPPED
        self._stop_offset_ns = offset_ns
        self._emit(
            TimerEventType.TIMER_STOPPED,
            offset_ns,
            (("prior_state", prior_state.value),),
        )
        self.validate_invariants()
        return self.snapshot()

    def start_overtime(self) -> TimerSnapshot:
        now_ns = self._observe_clock()
        self._synchronize(now_ns)
        if not self._config.overtime_enabled:
            raise InvalidTimerTransitionError(
                f"cannot start_overtime from {self._state.value}: overtime is disabled"
            )
        if self._state is not TimerState.COMPLETED:
            self._invalid("start_overtime")
        offset_ns = self._offset(now_ns)
        if self._completion_offset_ns is None:
            raise TimerError("completed timer is missing its completion offset")
        completion_gap_ns = offset_ns - self._completion_offset_ns
        if completion_gap_ns > self._config.pause_grace_ns:
            self._emit_continuity_broken(offset_ns, completion_gap_ns, "completion_wait")
        self._state = TimerState.OVERTIME
        self._active_focus_start_offset_ns = offset_ns
        self._active_focus_phase = FocusPhase.OVERTIME
        self._emit(
            TimerEventType.OVERTIME_STARTED,
            offset_ns,
            (("completion_gap_ns", completion_gap_ns),),
        )
        self.validate_invariants()
        return self.snapshot()

    def refresh(self) -> TimerSnapshot:
        return self.snapshot()

    def tick(self) -> TimerSnapshot:
        """Alias for callers that prefer polling terminology."""
        return self.refresh()

    def snapshot(self) -> TimerSnapshot:
        if self._terminal_snapshot is not None:
            return self._terminal_snapshot
        if self._state is TimerState.STOPPED:
            now_ns = None
        else:
            now_ns = self._observe_clock()
            self._synchronize(now_ns)
        snapshot = self._build_snapshot(now_ns)
        signature = replace(snapshot, version=0)
        if self._last_snapshot_signature is None:
            self._last_snapshot_signature = signature
        elif signature != self._last_snapshot_signature:
            self._version += 1
            self._last_snapshot_signature = signature
        snapshot = replace(snapshot, version=self._version)
        if self._state is TimerState.STOPPED:
            self._terminal_snapshot = snapshot
        self.validate_invariants()
        return snapshot

    def drain_events(self) -> tuple[TimerEvent, ...]:
        events = tuple(self._events)
        self._events.clear()
        return events

    def validate_invariants(self) -> None:
        """Raise ``TimerError`` if an internal accounting invariant is violated."""
        values = (self._planned_focus_ns, self._overtime_ns, self._pause_ns)
        if any(value < 0 for value in values):
            raise TimerError("timer duration values cannot be negative")
        if self._planned_focus_ns > self._config.planned_duration_ns:
            raise TimerError("planned focus exceeds configured duration")
        if self._pause_count != self._short_pause_count + self._long_pause_count:
            raise TimerError("pause classification counts do not balance")
        active_states = {TimerState.RUNNING, TimerState.OVERTIME}
        has_active = self._active_focus_start_offset_ns is not None
        if (self._state in active_states) != has_active:
            raise TimerError("active focus interval does not match timer state")
        if has_active:
            expected_phase = (
                FocusPhase.PLANNED if self._state is TimerState.RUNNING else FocusPhase.OVERTIME
            )
            if self._active_focus_phase is not expected_phase:
                raise TimerError("active focus phase does not match timer state")
        previous_end = -1
        for interval in self._focus_intervals:
            if interval.start_offset_ns < previous_end:
                raise TimerError("focus intervals overlap")
            previous_end = interval.end_offset_ns
        if self._event_sequence < len(self._events):
            raise TimerError("event sequence accounting is invalid")

    def _observe_clock(self) -> int:
        now_ns = self._clock.now_ns()
        if isinstance(now_ns, bool) or not isinstance(now_ns, int):
            raise TimerError("clock now_ns() must return an integer")
        if self._last_observed_ns is not None and now_ns < self._last_observed_ns:
            raise ClockRegressionError(
                f"clock regressed from {self._last_observed_ns}ns to {now_ns}ns "
                f"while timer state was {self._state.value}"
            )
        self._last_observed_ns = now_ns
        return now_ns

    def _synchronize(self, now_ns: int) -> None:
        if self._state in {TimerState.IDLE, TimerState.STOPPED}:
            return
        if self._last_sync_ns is None:
            raise TimerError("started timer is missing its last synchronization time")
        delta_ns = now_ns - self._last_sync_ns
        if delta_ns < 0:
            raise ClockRegressionError("timer synchronization clock moved backward")
        if self._state is TimerState.RUNNING:
            remaining_ns = self._config.planned_duration_ns - self._planned_focus_ns
            if delta_ns >= remaining_ns:
                completion_ns = self._last_sync_ns + remaining_ns
                completion_offset_ns = self._offset(completion_ns)
                self._planned_focus_ns = self._config.planned_duration_ns
                self._close_active_focus(completion_offset_ns)
                self._state = TimerState.COMPLETED
                self._completion_offset_ns = completion_offset_ns
                if not self._completion_emitted:
                    self._completion_emitted = True
                    self._emit(TimerEventType.PLANNED_COMPLETED, completion_offset_ns)
            else:
                self._planned_focus_ns += delta_ns
        elif self._state is TimerState.OVERTIME:
            self._overtime_ns += delta_ns
        elif self._state is TimerState.PAUSED:
            self._pause_ns += delta_ns
        self._last_sync_ns = now_ns

    def _close_active_focus(self, end_offset_ns: int) -> None:
        if self._active_focus_start_offset_ns is None or self._active_focus_phase is None:
            raise TimerError("no active focus interval to close")
        self._focus_intervals.append(
            FocusInterval(
                start_offset_ns=self._active_focus_start_offset_ns,
                end_offset_ns=end_offset_ns,
                phase=self._active_focus_phase,
            )
        )
        self._active_focus_start_offset_ns = None
        self._active_focus_phase = None

    def _finalize_pause(self, end_offset_ns: int) -> int:
        if self._pause_start_offset_ns is None:
            raise TimerError("paused timer is missing its pause start")
        pause = PauseInterval(self._pause_start_offset_ns, end_offset_ns)
        self._pause_intervals.append(pause)
        self._pause_start_offset_ns = None
        self._pause_count += 1
        if pause.duration_ns <= self._config.pause_grace_ns:
            self._short_pause_count += 1
        else:
            self._long_pause_count += 1
            self._emit_continuity_broken(end_offset_ns, pause.duration_ns, "pause")
        return pause.duration_ns

    def _emit_continuity_broken(self, offset_ns: int, gap_duration_ns: int, gap_type: str) -> None:
        self._emit(
            TimerEventType.CONTINUITY_BROKEN,
            offset_ns,
            (("gap_type", gap_type), ("gap_duration_ns", gap_duration_ns)),
        )

    def _emit(
        self,
        event_type: TimerEventType,
        offset_ns: int,
        details: EventDetails = (),
    ) -> None:
        self._event_sequence += 1
        self._events.append(
            TimerEvent(
                event_type=event_type,
                sequence=self._event_sequence,
                offset_ns=offset_ns,
                state=self._state,
                planned_focus_ns=self._planned_focus_ns,
                overtime_ns=self._overtime_ns,
                pause_ns=self._pause_ns,
                total_focus_ns=self._planned_focus_ns + self._overtime_ns,
                details=details,
            )
        )

    def _offset(self, absolute_ns: int) -> int:
        if self._first_start_ns is None:
            return 0
        return absolute_ns - self._first_start_ns

    def _observable_focus_intervals(self, now_ns: int | None) -> tuple[FocusInterval, ...]:
        intervals = list(self._focus_intervals)
        if self._active_focus_start_offset_ns is not None:
            if now_ns is None or self._active_focus_phase is None:
                raise TimerError("active interval cannot be represented without current time")
            intervals.append(
                FocusInterval(
                    self._active_focus_start_offset_ns,
                    self._offset(now_ns),
                    self._active_focus_phase,
                    active=True,
                )
            )
        return tuple(intervals)

    def _build_snapshot(self, now_ns: int | None) -> TimerSnapshot:
        remaining_ns = self._config.planned_duration_ns - self._planned_focus_ns
        total_focus_ns = self._planned_focus_ns + self._overtime_ns
        if self._state is TimerState.IDLE:
            wall_elapsed_ns = 0
        elif self._state is TimerState.STOPPED:
            wall_elapsed_ns = self._stop_offset_ns or 0
        elif now_ns is not None:
            wall_elapsed_ns = self._offset(now_ns)
        else:
            raise TimerError("active snapshot requires a clock value")
        blocks = calculate_continuous_blocks(
            self._observable_focus_intervals(now_ns),
            self._pause_intervals,
            self._config.pause_grace_ns,
        )
        longest_ns, average_ns, median_ns, current_ns = summarize_block_durations(blocks)
        current_active = bool(blocks and blocks[-1].end_offset_ns is None)
        return TimerSnapshot(
            state=self._state,
            planned_duration_seconds=self._config.planned_duration_seconds,
            planned_duration_ns=self._config.planned_duration_ns,
            remaining_planned_seconds=_ceil_seconds(remaining_ns),
            remaining_planned_ns=remaining_ns,
            planned_focus_seconds=_floor_seconds(self._planned_focus_ns),
            planned_focus_ns=self._planned_focus_ns,
            overtime_seconds=_floor_seconds(self._overtime_ns),
            overtime_ns=self._overtime_ns,
            total_focus_seconds=_floor_seconds(total_focus_ns),
            total_focus_ns=total_focus_ns,
            total_pause_seconds=_floor_seconds(self._pause_ns),
            total_pause_ns=self._pause_ns,
            wall_elapsed_seconds=_floor_seconds(wall_elapsed_ns),
            wall_elapsed_ns=wall_elapsed_ns,
            planned_complete=self._planned_focus_ns == self._config.planned_duration_ns,
            can_pause=self._state in {TimerState.RUNNING, TimerState.OVERTIME},
            can_resume=self._state is TimerState.PAUSED,
            can_stop=self._state
            in {
                TimerState.RUNNING,
                TimerState.PAUSED,
                TimerState.COMPLETED,
                TimerState.OVERTIME,
            },
            can_start_overtime=(
                self._state is TimerState.COMPLETED and self._config.overtime_enabled
            ),
            pause_grace_seconds=self._config.pause_grace_seconds,
            pause_count=self._pause_count,
            short_pause_count=self._short_pause_count,
            long_pause_count=self._long_pause_count,
            continuous_blocks=blocks,
            continuous_block_count=len(blocks),
            longest_continuous_seconds=_floor_seconds(longest_ns),
            longest_continuous_ns=longest_ns,
            average_continuous_seconds=_floor_seconds(average_ns),
            average_continuous_ns=average_ns,
            median_continuous_seconds=_floor_seconds(median_ns),
            median_continuous_ns=median_ns,
            current_continuous_seconds=_floor_seconds(current_ns),
            current_continuous_ns=current_ns,
            current_block_active=current_active,
            completion_emitted=self._completion_emitted,
            version=0,
        )

    def _invalid(self, operation: str) -> None:
        raise InvalidTimerTransitionError(
            f"cannot {operation} while timer state is {self._state.value}"
        )


def _floor_seconds(nanoseconds: int) -> int:
    return nanoseconds // NANOSECONDS_PER_SECOND


def _ceil_seconds(nanoseconds: int) -> int:
    return (nanoseconds + NANOSECONDS_PER_SECOND - 1) // NANOSECONDS_PER_SECOND
