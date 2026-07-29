"""Canonical portable-to-SQLite field conversion shared by planning and import."""

from app.models.persisted_session import PersistedSession
from app.portability.import_models import LogicalSegment, PortableImportBundle, PortableSourceRow


def device_values(row: PortableSourceRow) -> dict[str, object]:
    values = row.values
    return {
        "device_id": values["device_id"],
        "device_label": values["device_label"] or None,
        "created_at_utc": values["created_at_utc"],
        "updated_at_utc": values["updated_at_utc"],
    }


def category_values(row: PortableSourceRow) -> dict[str, object]:
    values = row.values
    return {
        "category_id": values["category_id"],
        "category_name": values["category_name"],
        "category_icon": values["category_icon"] or None,
        "is_active": int(values["is_active"] == "true"),
        "created_at_utc": values["created_at_utc"],
        "updated_at_utc": values["updated_at_utc"],
    }


def goal_values(row: PortableSourceRow) -> dict[str, object]:
    values = row.values
    return {
        "goal_id": values["goal_id"],
        "effective_from_date": values["effective_from_date"],
        "effective_to_date": values["effective_to_date"] or None,
        "goal_seconds": int(values["goal_seconds"]),
        "created_at_utc": values["created_at_utc"],
        "updated_at_utc": values["updated_at_utc"],
    }


def session_values(row: PortableSourceRow) -> dict[str, object]:
    values = row.values
    integer_fields = {
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
    }
    boolean_fields = {
        "completed_planned_timer",
        "overtime_enabled",
        "fullscreen_used",
        "quotes_enabled",
        "start_ritual_enabled",
    }
    optional_fields = {
        "ended_at_utc",
        "ended_at_local",
        "completion_reason",
        "manual_entry_created_at_utc",
        "manual_entry_updated_at_utc",
    }
    result: dict[str, object] = {}
    for field_name in PersistedSession.__dataclass_fields__:
        if field_name == "entry_source" and field_name not in values:
            result[field_name] = "imported"
            continue
        if (
            field_name
            in {
                "manual_entry_created_at_utc",
                "manual_entry_updated_at_utc",
            }
            and field_name not in values
        ):
            result[field_name] = None
            continue
        value = values[field_name]
        if field_name in integer_fields:
            result[field_name] = int(value)
        elif field_name in boolean_fields:
            result[field_name] = int(value == "true")
        elif field_name in optional_fields:
            result[field_name] = value or None
        else:
            result[field_name] = value
    return result


def segment_values(segment: LogicalSegment) -> dict[str, object]:
    return dict(segment.values)


def distraction_values(row: PortableSourceRow, bundle: PortableImportBundle) -> dict[str, object]:
    values = row.values
    portable_segment = values["segment_id"]
    return {
        "distraction_id": values["distraction_id"],
        "schema_version": int(values["schema_version"]),
        "session_id": values["session_id"],
        "segment_id": bundle.segment_id_map.get(portable_segment) if portable_segment else None,
        "device_id": values["device_id"],
        "marked_at_utc": values["marked_at_utc"],
        "marked_at_local": values["marked_at_local"],
        "local_date": values["local_date"],
        "timezone_name": values["timezone_name"],
        "category_id": values["category_id"],
        "category_name_snapshot": values["category_name_snapshot"],
        "elapsed_focus_seconds": int(values["elapsed_focus_seconds"]),
        "remaining_planned_seconds": int(values["remaining_planned_seconds"]),
        "is_overtime": int(values["is_overtime"] == "true"),
        "optional_note": values["optional_note"] or None,
        "created_at_utc": values["created_at_utc"],
    }


def canonical_database_row(values: dict[str, object], *, entity: str) -> dict[str, object]:
    result = dict(values)
    if entity == "segments":
        result.pop("updated_at_utc", None)
    return result
