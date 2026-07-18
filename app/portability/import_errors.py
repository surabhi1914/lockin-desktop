"""Typed failures for portable validation and database reconstruction."""


class PortableImportError(RuntimeError):
    """Base class for safe Phase 8 import failures."""


class ImportValidationError(PortableImportError):
    pass


class UnsupportedPortableSchemaError(ImportValidationError):
    pass


class ImportConflictError(PortableImportError):
    pass


class DatabaseRebuildError(PortableImportError):
    pass


class DatabaseReplacementError(DatabaseRebuildError):
    pass


class ImportBackupError(DatabaseRebuildError):
    pass


class ImportIntegrityError(DatabaseRebuildError):
    pass


class ImportInProgressError(PortableImportError):
    pass


class ActiveSessionBlocksImportError(PortableImportError):
    pass
