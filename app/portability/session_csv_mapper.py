"""Pure finalized-session-to-portable-row mapping."""

from dataclasses import fields

from app.models.persisted_session import FINAL_SESSION_STATUSES, PersistedSession
from app.models.portable_sync import PortableRow
from app.portability.csv_contracts import SESSIONS_HEADER
from app.portability.csv_mapping import csv_bool, ordered_row
from app.portability.errors import PortableChecksumMismatchError, PortableValidationError
from app.services.session_checksum_service import session_checksum


def map_session(session: PersistedSession, exported_at_utc: str) -> PortableRow:
    if session.ended_at_utc is None or session.ended_at_local is None:
        raise PortableValidationError(f"session is not finalized: {session.session_id}")
    if session.status not in FINAL_SESSION_STATUSES:
        raise PortableValidationError(f"session has an ineligible status: {session.session_id}")
    expected_checksum = session_checksum(session)
    if session.record_checksum != expected_checksum:
        raise PortableChecksumMismatchError(
            f"session checksum is missing or invalid: {session.session_id}"
        )
    values = ordered_row(
        SESSIONS_HEADER,
        {
            **{
                field: getattr(session, field)
                for field in (item.name for item in fields(session))
                if field != "record_checksum"
            },
            "completed_planned_timer": csv_bool(session.completed_planned_timer),
            "overtime_enabled": csv_bool(session.overtime_enabled),
            "fullscreen_used": csv_bool(session.fullscreen_used),
            "quotes_enabled": csv_bool(session.quotes_enabled),
            "start_ritual_enabled": csv_bool(session.start_ritual_enabled),
            "exported_at_utc": exported_at_utc,
            "record_checksum": expected_checksum,
        },
    )
    return PortableRow(
        "sessions",
        "session",
        session.session_id,
        expected_checksum,
        session.local_date_started,
        values,
        (
            session.started_at_local,
            session.started_at_utc,
            session.device_id,
            session.session_sequence,
            session.session_id,
        ),
    )
