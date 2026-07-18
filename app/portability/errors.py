"""Typed failures for safe portable-history synchronization."""


class PortableSyncError(RuntimeError):
    """Base portable synchronization failure."""


class PortableFileLockedError(PortableSyncError):
    """Raised when Windows or another application holds a CSV open."""


class PortableValidationError(PortableSyncError):
    """Raised when a portable file or mapped row violates its contract."""


class PortableChecksumMismatchError(PortableSyncError):
    """Raised when a SQLite or CSV checksum is missing or stale."""


class PortableDuplicateRecordError(PortableSyncError):
    """Raised when a record ID occurs more than once across partitions."""


class PortableLedgerConflictError(PortableSyncError):
    """Raised when a record exists in an unexpected portable partition."""


class PortablePartitionError(PortableSyncError):
    """Raised when a partition name, size, header, or path is unsafe."""


class PortableManifestError(PortableSyncError):
    """Raised when sync cannot safely update or validate the manifest."""
