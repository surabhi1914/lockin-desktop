"""Single-connection transactional unit of work for session lifecycle writes."""

import sqlite3
from types import TracebackType
from typing import Literal


class UnitOfWork:
    """Begin one immediate SQLite transaction and commit exactly once."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def __enter__(self) -> "UnitOfWork":
        if self.connection.in_transaction:
            raise RuntimeError("cannot nest a session unit of work")
        self.connection.execute("BEGIN IMMEDIATE")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        if exc_type is None:
            self.connection.commit()
        else:
            self.connection.rollback()
        return False
