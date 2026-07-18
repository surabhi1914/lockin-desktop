from types import SimpleNamespace

import pytest

from app.services.distraction_marker_service import DistractionMarkerService
from app.shortcuts.errors import DistractionMarkerError
from app.timer import ManualClock, TimerConfig, TimerEngine


def test_markers_use_snapshot_values_sequence_overtime_and_clear() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(5), clock)
    category = SimpleNamespace(category_id="category-id", category_name="Projects")
    service = DistractionMarkerService()
    engine.start()
    clock.advance_seconds(2)
    first = service.mark(engine.snapshot(), category)
    assert first.marker_sequence == 1
    assert first.monotonic_offset_ns == 2_000_000_000
    assert first.elapsed_focus_ns == 2_000_000_000
    assert first.remaining_planned_ns == 3_000_000_000
    assert not first.is_overtime
    clock.advance_seconds(3)
    engine.snapshot()
    engine.start_overtime()
    clock.advance_seconds(1)
    second = service.mark(engine.snapshot(), category)
    assert second.marker_sequence == 2 and second.is_overtime
    assert engine.state.value == "overtime"
    service.clear()
    assert service.count == 0 and service.markers == ()


def test_paused_marker_is_rejected_without_changing_timer() -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(10), clock)
    engine.start()
    engine.pause()
    before = engine.snapshot()
    with pytest.raises(DistractionMarkerError):
        DistractionMarkerService().mark(
            before, SimpleNamespace(category_id="id", category_name="Other")
        )
    assert engine.snapshot() == before
