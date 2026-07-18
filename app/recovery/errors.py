"""Typed recovery failures."""


class RecoveryError(RuntimeError):
    """Base recovery error."""


class RecoveryIntegrityError(RecoveryError):
    """Persisted structures cannot be recovered safely."""


class RecoveryAlreadyResolvedError(RecoveryError):
    """The unresolved state was already handled."""
