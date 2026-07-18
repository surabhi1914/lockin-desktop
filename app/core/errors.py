"""Domain-specific exceptions with user-facing messages."""


class LockInError(Exception):
    """Base exception for expected LockIn failures."""


class ValidationError(LockInError, ValueError):
    """Raised when data does not satisfy a Phase 0 contract."""


class PathContractError(LockInError, ValueError):
    """Raised when runtime or portable paths are unsafe."""


class DatabaseVersionError(LockInError):
    """Raised when a database schema is newer than this application supports."""
