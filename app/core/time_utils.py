"""Timezone-aware parsing, formatting, and local-midnight splitting."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.errors import ValidationError


@dataclass(frozen=True)
class MidnightSplitPart:
    utc_start: datetime
    utc_end: datetime
    local_start: datetime
    local_end: datetime
    local_date: str
    timezone_name: str
    utc_offset_minutes: int
    part_number: int
    duration_seconds: int


def utc_now() -> datetime:
    """Return the current aware UTC timestamp."""
    return datetime.now(UTC)


def _require_aware(value: datetime, label: str = "datetime") -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValidationError(f"{label} must be timezone-aware")


def get_timezone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValidationError(f"Unknown IANA timezone: {timezone_name!r}") from exc


def format_utc(value: datetime) -> str:
    _require_aware(value)
    utc_value = value.astimezone(UTC)
    return utc_value.isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValidationError("UTC timestamp must end in 'Z'")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValidationError(f"Invalid UTC timestamp: {value!r}") from exc
    _require_aware(parsed)
    if parsed.utcoffset() != timedelta(0):
        raise ValidationError("UTC timestamp must have a zero offset")
    return parsed.astimezone(UTC)


def format_local(value: datetime) -> str:
    _require_aware(value)
    return value.isoformat(timespec="seconds")


def parse_local(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"Invalid local timestamp: {value!r}") from exc
    _require_aware(parsed, "Local timestamp")
    return parsed


def to_timezone(value: datetime, timezone_name: str) -> datetime:
    _require_aware(value)
    return value.astimezone(get_timezone(timezone_name))


def validate_date(value: str) -> date:
    if not isinstance(value, str) or len(value) != 10:
        raise ValidationError("Date must use YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"Invalid date: {value!r}") from exc
    if parsed.isoformat() != value:
        raise ValidationError("Date must use canonical YYYY-MM-DD")
    return parsed


def split_at_local_midnights(
    utc_start: datetime, utc_end: datetime, timezone_name: str
) -> tuple[MidnightSplitPart, ...]:
    """Split a UTC interval at each midnight in the requested local timezone."""
    _require_aware(utc_start, "Start")
    _require_aware(utc_end, "End")
    start = utc_start.astimezone(UTC)
    end = utc_end.astimezone(UTC)
    if end < start:
        raise ValidationError("End time cannot be before start time")
    if end == start:
        return ()

    zone = get_timezone(timezone_name)
    cursor = start
    parts: list[MidnightSplitPart] = []
    while cursor < end:
        local_start = cursor.astimezone(zone)
        next_date = local_start.date() + timedelta(days=1)
        next_midnight = datetime.combine(next_date, time.min, tzinfo=zone).astimezone(UTC)
        part_end = min(end, next_midnight)
        local_end = part_end.astimezone(zone)
        offset = local_start.utcoffset()
        if offset is None:  # pragma: no cover - ZoneInfo always supplies an offset
            raise ValidationError("Timezone did not provide a UTC offset")
        duration = int((part_end - cursor).total_seconds())
        parts.append(
            MidnightSplitPart(
                utc_start=cursor,
                utc_end=part_end,
                local_start=local_start,
                local_end=local_end,
                local_date=local_start.date().isoformat(),
                timezone_name=timezone_name,
                utc_offset_minutes=int(offset.total_seconds() // 60),
                part_number=len(parts) + 1,
                duration_seconds=duration,
            )
        )
        cursor = part_end
    return tuple(parts)
