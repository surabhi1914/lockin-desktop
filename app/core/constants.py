"""Shared Phase 0 constants."""

from typing import Final

APPLICATION_NAME: Final = "LockIn"
DATA_SCHEMA_VERSION: Final = 1
DATABASE_SCHEMA_VERSION: Final = 4
MANIFEST_SCHEMA_VERSION: Final = 1
DEFAULT_TIMEZONE: Final = "America/Detroit"
DEFAULT_PARTITION_SIZE_BYTES: Final = 10 * 1024 * 1024
DEFAULT_PART_NUMBER_WIDTH: Final = 3
DATABASE_FILENAME: Final = "lockin.sqlite3"
