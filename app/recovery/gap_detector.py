"""Pure heartbeat/wall/monotonic gap classification."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GapAssessment:
    unexplained_gap_seconds: int
    recovery_required: bool


class GapDetector:
    def __init__(self, threshold_seconds: int = 15) -> None:
        if threshold_seconds < 1:
            raise ValueError("gap threshold must be positive")
        self.threshold_seconds = threshold_seconds

    def assess(
        self,
        *,
        wall_progress_seconds: int,
        monotonic_progress_seconds: int,
        heartbeat_age_seconds: int,
    ) -> GapAssessment:
        if min(wall_progress_seconds, monotonic_progress_seconds, heartbeat_age_seconds) < 0:
            raise ValueError("gap inputs cannot be negative")
        divergence = max(0, wall_progress_seconds - monotonic_progress_seconds)
        unexplained = max(divergence, heartbeat_age_seconds)
        return GapAssessment(unexplained, unexplained > self.threshold_seconds)
