"""Session-scoped distraction marker proposals committed after durable storage."""

from collections.abc import Callable

from app.models.category import Category
from app.models.distraction_marker import DistractionMarker
from app.shortcuts.errors import DistractionMarkerError
from app.timer.enums import TimerState
from app.timer.models import TimerSnapshot


class DistractionMarkerService:
    def __init__(self) -> None:
        self._markers: list[DistractionMarker] = []

    @property
    def markers(self) -> tuple[DistractionMarker, ...]:
        return tuple(self._markers)

    @property
    def count(self) -> int:
        return len(self._markers)

    def mark(
        self,
        snapshot: TimerSnapshot,
        category: Category,
        *,
        before_append: Callable[[DistractionMarker], None] | None = None,
    ) -> DistractionMarker:
        if snapshot.state not in {TimerState.RUNNING, TimerState.OVERTIME}:
            raise DistractionMarkerError("Distractions can be marked only while focus is active.")
        marker = DistractionMarker(
            marker_sequence=len(self._markers) + 1,
            monotonic_offset_ns=snapshot.wall_elapsed_ns,
            elapsed_focus_ns=snapshot.total_focus_ns,
            remaining_planned_ns=snapshot.remaining_planned_ns,
            is_overtime=snapshot.state is TimerState.OVERTIME,
            category_id=category.category_id,
            category_name_snapshot=category.category_name,
        )
        if before_append is not None:
            before_append(marker)
        self._markers.append(marker)
        return marker

    def clear(self) -> None:
        self._markers.clear()
