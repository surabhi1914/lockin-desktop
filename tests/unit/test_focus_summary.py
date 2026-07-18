from app.models.focus_summary import FocusSummary, FocusSummaryStatus
from app.timer import ManualClock, TimerConfig, TimerEngine


def test_summary_statuses_and_values_are_snapshot_derived() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(10, overtime_enabled=True), clock)
    engine.start()
    clock.advance_seconds(10)
    completed = engine.snapshot()
    summary = FocusSummary.from_snapshot("Projects", completed)
    assert summary.status is FocusSummaryStatus.COMPLETED
    assert summary.planned_focus_seconds == 10
    engine.start_overtime()
    clock.advance_seconds(4)
    overtime = FocusSummary.from_snapshot("Projects", engine.stop())
    assert overtime.status is FocusSummaryStatus.COMPLETED_WITH_OVERTIME
    assert overtime.overtime_seconds == 4
    assert overtime.total_focus_seconds == 14


def test_stopped_early_summary() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(60), clock)
    engine.start()
    clock.advance_seconds(7)
    summary = FocusSummary.from_snapshot("Reading", engine.stop())
    assert summary.status is FocusSummaryStatus.STOPPED_EARLY
    assert summary.total_focus_seconds == 7
