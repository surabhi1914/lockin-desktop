"""Read-only Phase 6 database integrity checks."""

import sqlite3
from dataclasses import dataclass

from app.models.persisted_session import PersistedSession
from app.services.session_checksum_service import session_checksum


@dataclass(frozen=True, slots=True)
class IntegrityReport:
    errors: tuple[str, ...]

    @property
    def healthy(self) -> bool:
        return not self.errors


def verify_session_integrity(connection: sqlite3.Connection) -> IntegrityReport:
    errors: list[str] = []
    for row in connection.execute("PRAGMA foreign_key_check"):
        errors.append(f"foreign-key violation: {tuple(row)}")
    for row in connection.execute(
        """
        SELECT session_id, COUNT(*) AS count FROM segments
        WHERE ended_at_utc IS NULL GROUP BY session_id HAVING COUNT(*) > 1
        """
    ):
        errors.append(f"session {row[0]} has {row[1]} open segments")
    for row in connection.execute(
        """
        SELECT s.session_id FROM sessions s JOIN segments g ON g.session_id = s.session_id
        WHERE s.ended_at_utc IS NOT NULL AND g.ended_at_utc IS NULL
        """
    ):
        errors.append(f"finalized session {row[0]} has an open segment")
    for row in connection.execute(
        """
        SELECT r.session_id FROM runtime_session_state r JOIN sessions s USING(session_id)
        WHERE s.ended_at_utc IS NOT NULL
        """
    ):
        errors.append(f"finalized session {row[0]} retains runtime state")

    sessions = connection.execute("SELECT * FROM sessions ORDER BY session_id").fetchall()
    for row in sessions:
        session = PersistedSession.from_row(row)
        segments = connection.execute(
            "SELECT * FROM segments WHERE session_id = ? ORDER BY segment_sequence",
            (session.session_id,),
        ).fetchall()
        sequences = [int(segment["segment_sequence"]) for segment in segments]
        if sequences != list(range(1, len(sequences) + 1)):
            errors.append(f"session {session.session_id} has non-contiguous segment sequences")
        previous_end: str | None = None
        for segment in segments:
            start = str(segment["started_at_utc"])
            end = segment["ended_at_utc"]
            if previous_end is not None and start < previous_end:
                errors.append(f"session {session.session_id} has overlapping segments")
            if end is not None:
                if str(end) < start:
                    errors.append(f"session {session.session_id} has a backward segment")
                previous_end = str(end)
        distraction_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM distractions WHERE session_id = ?",
                (session.session_id,),
            ).fetchone()[0]
        )
        if distraction_count != session.distraction_count:
            errors.append(f"session {session.session_id} distraction aggregate does not match")
        if session.ended_at_utc is None:
            continue
        planned = sum(
            int(segment["duration_seconds"])
            for segment in segments
            if segment["segment_type"] == "focus" and segment["focus_phase"] == "planned"
        )
        overtime = sum(
            int(segment["duration_seconds"])
            for segment in segments
            if segment["segment_type"] == "focus" and segment["focus_phase"] == "overtime"
        )
        paused = sum(
            int(segment["duration_seconds"])
            for segment in segments
            if segment["segment_type"] == "pause"
        )
        if planned != session.planned_focus_completed_seconds:
            errors.append(f"session {session.session_id} planned segment total does not match")
        if overtime != session.overtime_seconds:
            errors.append(f"session {session.session_id} overtime segment total does not match")
        if planned + overtime != session.actual_focus_seconds:
            errors.append(f"session {session.session_id} actual focus total does not match")
        if paused != session.total_pause_seconds:
            errors.append(f"session {session.session_id} pause segment total does not match")
        if session.entry_source not in {"timer", "manual", "recovery", "imported"}:
            errors.append(f"session {session.session_id} has an invalid entry source")
        if session.entry_source == "manual":
            recovery_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM recovery_events WHERE session_id = ?",
                    (session.session_id,),
                ).fetchone()[0]
            )
            groups = {
                str(segment["continuity_group_id"])
                for segment in segments
                if segment["counts_as_focus"]
            }
            if (
                session.completion_reason != "manual_entry"
                or session.manual_entry_created_at_utc is None
            ):
                errors.append(f"manual session {session.session_id} has invalid provenance")
            if session.manual_entry_updated_at_utc is not None:
                errors.append(f"manual session {session.session_id} was unexpectedly edited")
            if recovery_count:
                errors.append(f"manual session {session.session_id} has recovery audit rows")
            if session.distraction_count or distraction_count:
                errors.append(f"manual session {session.session_id} has distractions")
            if paused or any(segment["segment_type"] != "focus" for segment in segments):
                errors.append(f"manual session {session.session_id} has non-focus segments")
            if session.continuous_block_count != 1 or len(groups) != 1:
                errors.append(
                    f"manual session {session.session_id} does not have one continuous block"
                )
        elif (
            session.manual_entry_created_at_utc is not None
            or session.manual_entry_updated_at_utc is not None
            or session.completion_reason == "manual_entry"
        ):
            errors.append(f"non-manual session {session.session_id} has manual metadata")
        if session.record_checksum is None or session_checksum(session) != session.record_checksum:
            errors.append(f"session {session.session_id} checksum does not match")
    return IntegrityReport(tuple(errors))
