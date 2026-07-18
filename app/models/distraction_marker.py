"""Immutable, in-memory-only distraction marker."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DistractionMarker:
    marker_sequence: int
    monotonic_offset_ns: int
    elapsed_focus_ns: int
    remaining_planned_ns: int
    is_overtime: bool
    category_id: str
    category_name_snapshot: str
