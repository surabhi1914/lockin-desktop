"""Pure DST-safe SQLite segment splitting and portable-row mapping."""

from datetime import datetime
from uuid import UUID, uuid5

from app.core.time_utils import (
    format_local,
    format_utc,
    get_timezone,
    parse_utc,
    split_at_local_midnights,
)
from app.models.persisted_segment import PersistedSegment
from app.models.portable_sync import PortableRow
from app.portability.csv_contracts import SEGMENTS_HEADER
from app.portability.csv_mapping import csv_bool, ordered_row, portable_row_checksum
from app.portability.errors import PortableValidationError


def map_segment(
    segment: PersistedSegment,
    exported_at_utc: str,
    *,
    parent_started_at_utc: str,
) -> tuple[PortableRow, ...]:
    if segment.ended_at_utc is None:
        raise PortableValidationError(f"segment is not finalized: {segment.segment_id}")
    start = parse_utc(segment.started_at_utc)
    end = parse_utc(segment.ended_at_utc)
    if end < start:
        raise PortableValidationError(f"segment ends before it starts: {segment.segment_id}")
    zone = get_timezone(segment.timezone_name)
    split = split_at_local_midnights(start, end, segment.timezone_name)
    if split:
        boundaries = tuple(
            (
                part.utc_start,
                part.utc_end,
                part.local_start,
                part.local_end,
                part.local_date,
                part.utc_offset_minutes,
                part.duration_seconds,
            )
            for part in split
        )
    else:
        local_start = start.astimezone(zone)
        local_end = end.astimezone(zone)
        utc_offset = local_start.utcoffset()
        if utc_offset is None:
            raise PortableValidationError("segment timezone has no UTC offset")
        boundaries = (
            (
                start,
                end,
                local_start,
                local_end,
                local_start.date().isoformat(),
                int(utc_offset.total_seconds() // 60),
                0,
            ),
        )
    durations = _allocate_durations(segment.duration_seconds, boundaries)
    crossed = len(boundaries) > 1
    rows: list[PortableRow] = []
    for index, (boundary, duration) in enumerate(zip(boundaries, durations, strict=True), start=1):
        utc_start, utc_end, local_start, local_end, local_date, offset_minutes, _weight = boundary
        portable_id = (
            segment.segment_id
            if not crossed
            else str(
                uuid5(
                    UUID(segment.segment_id),
                    f"portable:{index}:{format_utc(utc_start)}:{format_utc(utc_end)}",
                )
            )
        )
        values = ordered_row(
            SEGMENTS_HEADER,
            {
                "schema_version": segment.schema_version,
                "segment_id": portable_id,
                "source_segment_id": segment.segment_id,
                "session_id": segment.session_id,
                "device_id": segment.device_id,
                "segment_sequence": segment.segment_sequence,
                "midnight_part_number": index,
                "segment_type": segment.segment_type,
                "started_at_utc": format_utc(utc_start),
                "ended_at_utc": format_utc(utc_end),
                "started_at_local": format_local(local_start),
                "ended_at_local": format_local(local_end),
                "local_date": local_date,
                "timezone_name": segment.timezone_name,
                "utc_offset_minutes": offset_minutes,
                "duration_seconds": duration,
                "counts_as_focus": csv_bool(segment.counts_as_focus),
                "pause_duration_seconds": duration if segment.segment_type == "pause" else 0,
                "pause_classification": segment.pause_classification,
                "breaks_continuity": csv_bool(segment.breaks_continuity),
                "continuity_group_id": segment.continuity_group_id,
                "pause_grace_threshold_seconds": segment.pause_grace_threshold_seconds,
                "focus_phase": segment.focus_phase,
                "crossed_midnight": csv_bool(crossed),
                "end_reason": segment.end_reason,
                "created_at_utc": segment.created_at_utc,
                "exported_at_utc": exported_at_utc,
            },
        )
        checksum = portable_row_checksum(values)
        values["record_checksum"] = checksum
        rows.append(
            PortableRow(
                "segments",
                "segment",
                portable_id,
                checksum,
                str(local_date),
                values,
                (parent_started_at_utc, segment.session_id, segment.segment_sequence, index),
            )
        )
    return tuple(rows)


def _allocate_durations(
    total_seconds: int,
    boundaries: tuple[tuple[datetime, datetime, datetime, datetime, str, int, int], ...],
) -> tuple[int, ...]:
    weights = [item[6] for item in boundaries]
    total_weight = sum(weights)
    if len(weights) == 1 or total_weight <= 0:
        return (total_seconds,)
    allocated: list[int] = []
    used = 0
    for weight in weights[:-1]:
        value = total_seconds * weight // total_weight
        allocated.append(value)
        used += value
    allocated.append(total_seconds - used)
    return tuple(allocated)
