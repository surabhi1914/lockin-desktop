"""Read-only structured validation for Phase 0 portable CSV files."""

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from app.core.errors import ValidationError
from app.core.ids import canonicalize_uuid
from app.core.time_utils import parse_local, parse_utc, validate_date
from app.portability.csv_contracts import SESSIONS_V1_HEADER, header_for

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ValidationIssue:
    file_path: Path
    row_number: int | None
    column: str | None
    error_code: str
    message: str
    severity: str = "error"


ID_COLUMN = {
    "devices": "device_id",
    "categories": "category_id",
    "quotes": "quote_id",
    "daily_goals": "goal_id",
    "sessions": "session_id",
    "segments": "segment_id",
    "distractions": "distraction_id",
}
OPTIONAL_FIELDS = {
    "devices": {"device_label"},
    "categories": {"category_icon"},
    "quotes": {"author", "category"},
    "daily_goals": {"effective_to_date"},
    "sessions": {
        "ended_at_utc",
        "ended_at_local",
        "completion_reason",
        "manual_entry_created_at_utc",
        "manual_entry_updated_at_utc",
    },
    "segments": {
        "source_segment_id",
        "ended_at_utc",
        "ended_at_local",
        "continuity_group_id",
        "end_reason",
    },
    "distractions": {"segment_id", "optional_note"},
}
UUID_COLUMNS = {
    "device_id",
    "category_id",
    "goal_id",
    "session_id",
    "segment_id",
    "source_segment_id",
    "distraction_id",
    "continuity_group_id",
}
BOOLEAN_COLUMNS = {
    "is_active",
    "is_favorite",
    "completed_planned_timer",
    "overtime_enabled",
    "fullscreen_used",
    "quotes_enabled",
    "start_ritual_enabled",
    "counts_as_focus",
    "breaks_continuity",
    "crossed_midnight",
    "is_overtime",
}
INTEGER_COLUMNS = {
    "schema_version",
    "session_sequence",
    "utc_offset_started_minutes",
    "planned_focus_seconds",
    "actual_focus_seconds",
    "planned_focus_completed_seconds",
    "overtime_seconds",
    "total_pause_seconds",
    "wall_clock_seconds",
    "continuous_block_count",
    "longest_continuous_seconds",
    "average_continuous_seconds",
    "median_continuous_seconds",
    "pause_count",
    "short_pause_count",
    "long_pause_count",
    "distraction_count",
    "stopped_early_seconds",
    "segment_sequence",
    "midnight_part_number",
    "utc_offset_minutes",
    "duration_seconds",
    "pause_duration_seconds",
    "pause_grace_threshold_seconds",
    "elapsed_focus_seconds",
    "remaining_planned_seconds",
    "goal_seconds",
}
SIGNED_INTEGER_COLUMNS = {"utc_offset_started_minutes", "utc_offset_minutes"}
UTC_TIMESTAMP_COLUMNS = {
    "created_at_utc",
    "updated_at_utc",
    "started_at_utc",
    "ended_at_utc",
    "marked_at_utc",
    "exported_at_utc",
    "manual_entry_created_at_utc",
    "manual_entry_updated_at_utc",
}
LOCAL_TIMESTAMP_COLUMNS = {"started_at_local", "ended_at_local", "marked_at_local"}
DATE_COLUMNS = {"effective_from_date", "effective_to_date", "local_date_started", "local_date"}
ENUM_VALUES = {
    "status": {
        "running",
        "paused",
        "completed",
        "completed_with_overtime",
        "stopped_early",
        "recovered",
        "discarded",
    },
    "completion_reason": {
        "timer_completed",
        "manual_stop",
        "manual_entry",
        "app_close",
        "system_shutdown",
        "crash_recovery",
        "sleep_detected",
        "data_repair",
    },
    "entry_source": {"timer", "manual", "recovery", "imported"},
    "segment_type": {"focus", "pause"},
    "pause_classification": {"none", "short_grace_pause", "continuity_break", "system_sleep"},
    "focus_phase": {"planned", "overtime", "not_applicable"},
}


def _issue(
    path: Path, code: str, message: str, row: int | None = None, column: str | None = None
) -> ValidationIssue:
    return ValidationIssue(path, row, column, code, message)


def validate_csv(
    path: Path,
    entity: str,
    *,
    data_schema_version: int | None = None,
) -> tuple[ValidationIssue, ...]:
    """Validate one CSV without changing it."""
    current = header_for(entity)
    issues: list[ValidationIssue] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
    except FileNotFoundError:
        return (_issue(path, "file_missing", "CSV file does not exist"),)
    except UnicodeDecodeError as exc:
        return (_issue(path, "invalid_utf8", f"File is not valid UTF-8: {exc}"),)
    except OSError as exc:
        return (_issue(path, "file_read_error", f"Could not read CSV: {exc}"),)
    if not rows:
        return (_issue(path, "missing_header", "CSV is empty and has no header"),)

    actual = tuple(rows[0])
    accepted = (
        (current, SESSIONS_V1_HEADER)
        if entity == "sessions" and data_schema_version in (None, 1)
        else (current,)
    )
    expected = actual if actual in accepted else current
    duplicates = sorted({name for name in actual if actual.count(name) > 1})
    missing = [name for name in expected if name not in actual]
    unexpected = [name for name in actual if name not in expected]
    if duplicates:
        issues.append(_issue(path, "duplicate_header", f"Duplicate headers: {duplicates}"))
    if missing:
        issues.append(_issue(path, "missing_header", f"Missing headers: {missing}"))
    if unexpected:
        issues.append(_issue(path, "unexpected_header", f"Unexpected headers: {unexpected}"))
    if actual != expected and not (duplicates or missing or unexpected):
        issues.append(_issue(path, "header_order", "CSV headers are not in the required order"))
    if actual != expected:
        return tuple(issues)

    seen_ids: set[str] = set()
    id_column = ID_COLUMN[entity]
    optional = OPTIONAL_FIELDS[entity]
    for row_number, values in enumerate(rows[1:], start=2):
        if len(values) != len(expected):
            issues.append(
                _issue(
                    path,
                    "row_width",
                    f"Expected {len(expected)} fields, found {len(values)}",
                    row_number,
                )
            )
            continue
        row = dict(zip(expected, values, strict=True))
        for column, value in row.items():
            if not value and column not in optional:
                issues.append(
                    _issue(path, "empty_required", "Required field is empty", row_number, column)
                )
                continue
            if not value:
                continue
            try:
                if column in UUID_COLUMNS:
                    canonical = canonicalize_uuid(value)
                    if canonical != value:
                        raise ValidationError("UUID is not canonical lowercase form")
                if column in BOOLEAN_COLUMNS and value not in {"true", "false"}:
                    raise ValidationError("Boolean must be lowercase true or false")
                if column in INTEGER_COLUMNS:
                    parsed_integer = int(value)
                    if str(parsed_integer) != value:
                        raise ValidationError("Integer must use canonical base-10 encoding")
                    if column not in SIGNED_INTEGER_COLUMNS and parsed_integer < 0:
                        raise ValidationError("Integer duration/count cannot be negative")
                if column in UTC_TIMESTAMP_COLUMNS:
                    parse_utc(value)
                if column in LOCAL_TIMESTAMP_COLUMNS:
                    parse_local(value)
                if column in DATE_COLUMNS:
                    validate_date(value)
                if column == "record_checksum" and not SHA256_PATTERN.fullmatch(value):
                    raise ValidationError("Checksum must be 64 lowercase SHA-256 hex characters")
                if column in ENUM_VALUES and value not in ENUM_VALUES[column]:
                    raise ValidationError(f"Value must be one of {sorted(ENUM_VALUES[column])}")
            except (ValidationError, ValueError) as exc:
                code = "invalid_value"
                if column in BOOLEAN_COLUMNS:
                    code = "invalid_boolean"
                elif column in INTEGER_COLUMNS:
                    code = "invalid_integer"
                elif column in UUID_COLUMNS:
                    code = "invalid_uuid"
                elif column in UTC_TIMESTAMP_COLUMNS or column in LOCAL_TIMESTAMP_COLUMNS:
                    code = "invalid_timestamp"
                elif column in DATE_COLUMNS:
                    code = "invalid_date"
                elif column == "record_checksum":
                    code = "invalid_checksum"
                elif column in ENUM_VALUES:
                    code = "invalid_enum"
                issues.append(_issue(path, code, str(exc), row_number, column))

        record_id = row[id_column]
        if record_id:
            if record_id in seen_ids:
                issues.append(
                    _issue(
                        path,
                        "duplicate_record_id",
                        f"Duplicate {id_column}: {record_id}",
                        row_number,
                        id_column,
                    )
                )
            seen_ids.add(record_id)
    return tuple(issues)
