"""Canonical checksum contract for finalized SQLite sessions."""

from dataclasses import fields

from app.core.checksums import record_checksum
from app.models.persisted_session import PersistedSession


def session_checksum(session: PersistedSession) -> str:
    values = {field.name: getattr(session, field.name) for field in fields(session)}
    values.pop("record_checksum", None)
    return record_checksum(values)
