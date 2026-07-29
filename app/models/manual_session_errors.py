"""Typed failures for manual past-session logging."""

from app.models.manual_session import SessionOverlap


class ManualSessionError(Exception):
    """Base manual-session failure."""


class ManualSessionValidationError(ManualSessionError, ValueError):
    """Raised when a command cannot describe a valid historical session."""


class ManualSessionOverlapError(ManualSessionValidationError):
    """Raised when overlap blocks a save or needs explicit confirmation."""

    def __init__(self, message: str, overlap: SessionOverlap) -> None:
        super().__init__(message)
        self.overlap = overlap


class ManualSessionPersistenceError(ManualSessionError, RuntimeError):
    """Raised when the atomic local write fails."""


class ManualSessionSyncError(ManualSessionError, RuntimeError):
    """Represents a portable sync failure after the local commit."""


class ManualSessionEditNotAllowedError(ManualSessionError):
    """Raised when editing a source that is not safely editable."""
