from dataclasses import FrozenInstanceError

import pytest

from app.timer.errors import InvalidTimerConfigurationError
from app.timer.models import MAX_PLANNED_DURATION_SECONDS, TimerConfig


def test_valid_config_is_immutable_and_exposes_exact_ns() -> None:
    config = TimerConfig(60, pause_grace_seconds=0, overtime_enabled=False)
    assert config.planned_duration_ns == 60_000_000_000
    assert config.pause_grace_ns == 0
    with pytest.raises(FrozenInstanceError):
        config.planned_duration_seconds = 10  # type: ignore[misc]


@pytest.mark.parametrize("duration", [0, -1, True, 1.0])
def test_invalid_duration_is_rejected(duration: object) -> None:
    with pytest.raises(InvalidTimerConfigurationError):
        TimerConfig(duration)  # type: ignore[arg-type]


def test_seven_day_duration_limit_is_inclusive() -> None:
    assert TimerConfig(MAX_PLANNED_DURATION_SECONDS).planned_duration_seconds == 604_800
    with pytest.raises(InvalidTimerConfigurationError):
        TimerConfig(MAX_PLANNED_DURATION_SECONDS + 1)


@pytest.mark.parametrize("grace", [-1, True, 1.5])
def test_invalid_grace_is_rejected(grace: object) -> None:
    with pytest.raises(InvalidTimerConfigurationError):
        TimerConfig(1, pause_grace_seconds=grace)  # type: ignore[arg-type]


def test_overtime_flag_must_be_bool() -> None:
    with pytest.raises(InvalidTimerConfigurationError):
        TimerConfig(1, overtime_enabled=1)  # type: ignore[arg-type]
