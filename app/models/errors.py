"""Typed Phase 3 model, category, and session-coordinator errors."""


class CategoryError(Exception):
    """Base category-domain failure."""


class CategoryNotFoundError(CategoryError):
    """Raised when a requested category ID does not exist."""


class DuplicateCategoryError(CategoryError):
    """Raised when normalized category names collide."""


class ProtectedCategoryError(CategoryError):
    """Raised when changing the protected Other category is attempted."""


class CategoryPersistenceError(CategoryError):
    """Raised when SQLite and portable category state cannot be kept consistent."""


class InvalidFocusSessionDraftError(ValueError):
    """Raised when focus setup values cannot form a valid draft."""


class FocusSessionAlreadyActiveError(RuntimeError):
    """Raised when a second in-memory preview is requested."""


class NoActiveFocusSessionError(RuntimeError):
    """Raised when a preview operation has no active session."""


class SessionPersistenceError(RuntimeError):
    """Base failure for a transactional session lifecycle write."""


class SessionIntegrityError(SessionPersistenceError):
    """Raised when stored lifecycle state violates a session invariant."""


class SessionWriteConflictError(SessionPersistenceError):
    """Raised when a lifecycle action overlaps or targets stale state."""


class SessionPersistenceBlockedError(SessionPersistenceError):
    """Raised after timer and database state may have diverged."""


class UnfinishedSessionError(SessionPersistenceError):
    """Raised when unresolved runtime state blocks a new session."""


class InvalidWallClockError(SessionPersistenceError):
    """Raised when a persistence timestamp is not timezone-aware UTC."""
