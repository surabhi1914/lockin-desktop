"""Pure continuous-focus block calculations."""

from collections.abc import Sequence

from app.timer.clock import NANOSECONDS_PER_SECOND
from app.timer.enums import FocusPhase
from app.timer.models import ContinuousBlock, FocusInterval, PauseInterval


def calculate_continuous_blocks(
    focus_intervals: Sequence[FocusInterval],
    pause_intervals: Sequence[PauseInterval],
    grace_ns: int,
) -> tuple[ContinuousBlock, ...]:
    """Group ordered focus intervals across non-focus gaps within ``grace_ns``.

    Block duration is focus time only. Gaps joined for analytical continuity do
    not inflate focus. A short-pause count is added only for a finalized pause;
    completion-wait gaps may join but are not pauses.
    """
    if grace_ns < 0:
        raise ValueError("grace_ns cannot be negative")
    if not focus_intervals:
        return ()
    _validate_intervals(focus_intervals, pause_intervals)
    pause_gaps = {(pause.start_offset_ns, pause.end_offset_ns) for pause in pause_intervals}

    blocks: list[ContinuousBlock] = []
    block_start = focus_intervals[0].start_offset_ns
    block_duration = focus_intervals[0].duration_ns
    block_end = focus_intervals[0].end_offset_ns
    includes_planned = focus_intervals[0].phase is FocusPhase.PLANNED
    includes_overtime = focus_intervals[0].phase is FocusPhase.OVERTIME
    short_pause_count = 0
    block_active = focus_intervals[0].active

    for interval in focus_intervals[1:]:
        gap = interval.start_offset_ns - block_end
        if gap <= grace_ns:
            if (block_end, interval.start_offset_ns) in pause_gaps:
                short_pause_count += 1
            block_duration += interval.duration_ns
            block_end = interval.end_offset_ns
            includes_planned |= interval.phase is FocusPhase.PLANNED
            includes_overtime |= interval.phase is FocusPhase.OVERTIME
            block_active = interval.active
            continue
        blocks.append(
            _make_block(
                len(blocks) + 1,
                block_start,
                block_end,
                block_duration,
                includes_planned,
                includes_overtime,
                short_pause_count,
                block_active,
            )
        )
        block_start = interval.start_offset_ns
        block_duration = interval.duration_ns
        block_end = interval.end_offset_ns
        includes_planned = interval.phase is FocusPhase.PLANNED
        includes_overtime = interval.phase is FocusPhase.OVERTIME
        short_pause_count = 0
        block_active = interval.active

    blocks.append(
        _make_block(
            len(blocks) + 1,
            block_start,
            block_end,
            block_duration,
            includes_planned,
            includes_overtime,
            short_pause_count,
            block_active,
        )
    )
    return tuple(blocks)


def summarize_block_durations(
    blocks: Sequence[ContinuousBlock],
) -> tuple[int, int, int, int]:
    """Return longest, integer-average, integer-median, and current nanoseconds.

    Average and an even-sized median use floor division for deterministic output.
    """
    if not blocks:
        return 0, 0, 0, 0
    durations = [block.duration_ns for block in blocks]
    ordered = sorted(durations)
    count = len(ordered)
    average = sum(ordered) // count
    middle = count // 2
    median = ordered[middle] if count % 2 else (ordered[middle - 1] + ordered[middle]) // 2
    return max(ordered), average, median, durations[-1]


def _make_block(
    index: int,
    start: int,
    end: int,
    duration: int,
    planned: bool,
    overtime: bool,
    short_pauses: int,
    active: bool,
) -> ContinuousBlock:
    return ContinuousBlock(
        index=index,
        duration_ns=duration,
        duration_seconds=duration // NANOSECONDS_PER_SECOND,
        start_offset_ns=start,
        end_offset_ns=None if active else end,
        includes_planned=planned,
        includes_overtime=overtime,
        short_pause_count=short_pauses,
    )


def _validate_intervals(
    focus_intervals: Sequence[FocusInterval], pause_intervals: Sequence[PauseInterval]
) -> None:
    previous_end = -1
    active_seen = False
    for interval in focus_intervals:
        if interval.start_offset_ns < previous_end:
            raise ValueError("focus intervals cannot overlap or run backward")
        if active_seen:
            raise ValueError("an active focus interval must be last")
        active_seen = interval.active
        previous_end = interval.end_offset_ns
    previous_end = -1
    for pause in pause_intervals:
        if pause.start_offset_ns < previous_end:
            raise ValueError("pause intervals cannot overlap or run backward")
        previous_end = pause.end_offset_ns
