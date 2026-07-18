from datetime import UTC, datetime, timedelta

import pytest

from app.core.errors import ValidationError
from app.core.time_utils import (
    format_local,
    format_utc,
    parse_local,
    parse_utc,
    split_at_local_midnights,
    to_timezone,
    utc_now,
    validate_date,
)


def test_utc_format_parse_and_now() -> None:
    value = datetime(2026, 7, 16, 17, 30, tzinfo=UTC)
    assert format_utc(value) == "2026-07-16T17:30:00Z"
    assert parse_utc(format_utc(value)) == value
    assert utc_now().utcoffset() == timedelta(0)


def test_local_format_parse_and_conversion() -> None:
    local = to_timezone(datetime(2026, 1, 1, 12, tzinfo=UTC), "America/Detroit")
    rendered = format_local(local)
    assert rendered.endswith("-05:00")
    assert parse_local(rendered).utcoffset() == timedelta(hours=-5)


@pytest.mark.parametrize("operation", [format_utc, format_local])
def test_naive_datetime_rejected(operation: object) -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        operation(datetime(2026, 1, 1))  # type: ignore[operator]


@pytest.mark.parametrize("value", ["2026-01-01T00:00:00+00:00", "badZ"])
def test_invalid_utc_string_rejected(value: str) -> None:
    with pytest.raises(ValidationError):
        parse_utc(value)


def test_naive_local_string_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_local("2026-01-01T00:00:00")


def test_normal_interval_and_local_midnight_split() -> None:
    start = datetime(2026, 1, 1, 15, tzinfo=UTC)
    end = start + timedelta(hours=2)
    part = split_at_local_midnights(start, end, "America/Detroit")[0]
    assert part.duration_seconds == 7200
    assert part.part_number == 1
    assert part.local_date == "2026-01-01"
    assert part.utc_offset_minutes == -300


def test_session_crossing_local_midnight() -> None:
    start = datetime(2026, 1, 2, 4, 30, tzinfo=UTC)
    end = start + timedelta(hours=2)
    parts = split_at_local_midnights(start, end, "America/Detroit")
    assert [part.duration_seconds for part in parts] == [1800, 5400]
    assert [part.local_date for part in parts] == ["2026-01-01", "2026-01-02"]
    assert sum(part.duration_seconds for part in parts) == 7200


def test_dst_transition_preserves_real_duration() -> None:
    start = datetime(2025, 3, 9, 5, tzinfo=UTC)  # local midnight before spring-forward
    end = datetime(2025, 3, 10, 4, tzinfo=UTC)  # next local midnight
    parts = split_at_local_midnights(start, end, "America/Detroit")
    assert len(parts) == 1
    assert parts[0].duration_seconds == 23 * 3600
    assert sum(part.duration_seconds for part in parts) == int((end - start).total_seconds())


def test_end_before_start_and_equal_interval() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(ValidationError, match="before"):
        split_at_local_midnights(start, start - timedelta(seconds=1), "America/Detroit")
    assert split_at_local_midnights(start, start, "America/Detroit") == ()


def test_invalid_timezone_and_date() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        to_timezone(datetime(2026, 1, 1, tzinfo=UTC), "Mars/Olympus")
    with pytest.raises(ValidationError, match="Date"):
        validate_date("2026-2-3")
    with pytest.raises(ValidationError, match="Invalid date"):
        validate_date("2026-02-30")
    assert validate_date("2026-02-03").isoformat() == "2026-02-03"
