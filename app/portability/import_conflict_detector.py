"""Read-only exact-duplicate and conflict planning against an optional SQLite database."""

import sqlite3
from pathlib import Path

from app.core.checksums import record_checksum
from app.models.category import category_uniqueness_key
from app.portability.import_mapping import (
    canonical_database_row,
    category_values,
    device_values,
    distraction_values,
    goal_values,
    segment_values,
    session_values,
)
from app.portability.import_models import (
    ImportConflict,
    ImportMode,
    ImportPlan,
    ImportWarning,
    PlannedOperation,
    PortableImportBundle,
    PortableSourceRow,
    SourceLocation,
)


class ImportConflictDetector:
    def plan(
        self,
        bundle: PortableImportBundle,
        database_path: Path | None,
        *,
        mode: ImportMode,
    ) -> ImportPlan:
        operations: list[PlannedOperation] = []
        conflicts: list[ImportConflict] = []
        warnings = list(bundle.warnings)
        connection = self._open_existing(database_path)
        try:
            self._plan_rows(
                connection,
                "devices",
                "devices",
                bundle.rows["devices"],
                device_values,
                operations,
                conflicts,
            )
            self._plan_categories(connection, bundle, operations, conflicts)
            self._plan_goals(connection, bundle, operations, conflicts)
            self._plan_sessions(connection, bundle, operations, conflicts)
            for segment in bundle.logical_segments:
                incoming = segment_values(segment)
                self._plan_one(
                    connection,
                    "segments",
                    "segments",
                    segment.segment_id,
                    incoming,
                    segment.portable_rows[0].location,
                    operations,
                    conflicts,
                )
            self._plan_rows(
                connection,
                "distractions",
                "distractions",
                bundle.rows["distractions"],
                lambda row: distraction_values(row, bundle),
                operations,
                conflicts,
            )
            self._device_label_warnings(connection, bundle, warnings)
        finally:
            if connection is not None:
                connection.close()
        return ImportPlan(
            mode, bundle.summary, tuple(operations), tuple(conflicts), tuple(warnings)
        )

    def _open_existing(self, path: Path | None) -> sqlite3.Connection | None:
        if path is None or not path.is_file() or path.stat().st_size == 0:
            return None
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _plan_rows(
        self,
        connection: sqlite3.Connection | None,
        entity: str,
        table: str,
        rows: tuple[PortableSourceRow, ...],
        mapper: object,
        operations: list[PlannedOperation],
        conflicts: list[ImportConflict],
        *,
        checksum_field: str | None = None,
    ) -> None:
        for row in rows:
            incoming = mapper(row)  # type: ignore[operator]
            self._plan_one(
                connection,
                entity,
                table,
                row.record_id,
                incoming,
                row.location,
                operations,
                conflicts,
                checksum_field=checksum_field,
            )

    def _plan_categories(
        self,
        connection: sqlite3.Connection | None,
        bundle: PortableImportBundle,
        operations: list[PlannedOperation],
        conflicts: list[ImportConflict],
    ) -> None:
        existing_names: dict[str, sqlite3.Row] = {}
        if connection is not None:
            existing_names = {
                category_uniqueness_key(str(row["category_name"])): row
                for row in connection.execute("SELECT * FROM categories")
            }
        for row in bundle.rows["categories"]:
            incoming = category_values(row)
            normalized = category_uniqueness_key(str(incoming["category_name"]))
            semantic = existing_names.get(normalized)
            if semantic is not None and str(semantic["category_id"]) != row.record_id:
                conflicts.append(
                    ImportConflict(
                        "categories",
                        row.record_id,
                        "normalized category name already exists under another ID",
                        row.location,
                        dict(semantic),
                        incoming,
                    )
                )
                operations.append(PlannedOperation("categories", row.record_id, "conflict"))
                continue
            self._plan_one(
                connection,
                "categories",
                "categories",
                row.record_id,
                incoming,
                row.location,
                operations,
                conflicts,
            )

    def _plan_goals(
        self,
        connection: sqlite3.Connection | None,
        bundle: PortableImportBundle,
        operations: list[PlannedOperation],
        conflicts: list[ImportConflict],
    ) -> None:
        for row in bundle.rows["daily_goals"]:
            incoming = goal_values(row)
            if connection is not None:
                overlap = connection.execute(
                    """
                    SELECT * FROM daily_goals
                    WHERE goal_id != ?
                      AND (effective_to_date IS NULL OR effective_to_date >= ?)
                      AND (? IS NULL OR effective_from_date <= ?)
                    LIMIT 1
                    """,
                    (
                        row.record_id,
                        incoming["effective_from_date"],
                        incoming["effective_to_date"],
                        incoming["effective_to_date"],
                    ),
                ).fetchone()
                if overlap is not None:
                    conflicts.append(
                        ImportConflict(
                            "daily_goals",
                            row.record_id,
                            "effective range overlaps an existing goal with another ID",
                            row.location,
                            dict(overlap),
                            incoming,
                        )
                    )
                    operations.append(PlannedOperation("daily_goals", row.record_id, "conflict"))
                    continue
            self._plan_one(
                connection,
                "daily_goals",
                "daily_goals",
                row.record_id,
                incoming,
                row.location,
                operations,
                conflicts,
            )

    def _plan_sessions(
        self,
        connection: sqlite3.Connection | None,
        bundle: PortableImportBundle,
        operations: list[PlannedOperation],
        conflicts: list[ImportConflict],
    ) -> None:
        for row in bundle.rows["sessions"]:
            incoming = session_values(row)
            if connection is not None:
                sequence = connection.execute(
                    """
                    SELECT * FROM sessions
                    WHERE session_id != ? AND device_id = ? AND session_sequence = ?
                    LIMIT 1
                    """,
                    (
                        row.record_id,
                        incoming["device_id"],
                        incoming["session_sequence"],
                    ),
                ).fetchone()
                if sequence is not None:
                    conflicts.append(
                        ImportConflict(
                            "sessions",
                            row.record_id,
                            "device/session sequence already belongs to another session ID",
                            row.location,
                            dict(sequence),
                            incoming,
                        )
                    )
                    operations.append(PlannedOperation("sessions", row.record_id, "conflict"))
                    continue
            self._plan_one(
                connection,
                "sessions",
                "sessions",
                row.record_id,
                incoming,
                row.location,
                operations,
                conflicts,
                checksum_field="record_checksum",
            )

    def _plan_one(
        self,
        connection: sqlite3.Connection | None,
        entity: str,
        table: str,
        record_id: str,
        incoming: dict[str, object],
        location: SourceLocation,
        operations: list[PlannedOperation],
        conflicts: list[ImportConflict],
        *,
        checksum_field: str | None = None,
    ) -> None:
        existing = None
        if connection is not None:
            id_column = {
                "devices": "device_id",
                "categories": "category_id",
                "daily_goals": "goal_id",
                "sessions": "session_id",
                "segments": "segment_id",
                "distractions": "distraction_id",
            }[table]
            existing = connection.execute(
                f"SELECT * FROM {table} WHERE {id_column} = ?", (record_id,)
            ).fetchone()
        if existing is None:
            operations.append(PlannedOperation(entity, record_id, "insert"))
            return
        existing_values = dict(existing)
        if checksum_field is not None:
            same = existing_values.get(checksum_field) == incoming.get(checksum_field)
        else:
            same = record_checksum(
                canonical_database_row(existing_values, entity=entity)
            ) == record_checksum(canonical_database_row(incoming, entity=entity))
        if same:
            operations.append(PlannedOperation(entity, record_id, "skip_exact"))
            return
        conflicts.append(
            ImportConflict(
                entity,
                record_id,
                "same ID has different canonical content",
                location,
                existing_values,
                incoming,
            )
        )
        operations.append(PlannedOperation(entity, record_id, "conflict"))

    def _device_label_warnings(
        self,
        connection: sqlite3.Connection | None,
        bundle: PortableImportBundle,
        warnings: list[ImportWarning],
    ) -> None:
        labels: dict[str, str] = {}
        if connection is not None:
            labels.update(
                {
                    str(row["device_label"] or "").casefold(): str(row["device_id"])
                    for row in connection.execute("SELECT * FROM devices")
                    if row["device_label"]
                }
            )
        for row in bundle.rows["devices"]:
            label = row.values["device_label"].casefold()
            if label and label in labels and labels[label] != row.record_id:
                warnings.append(
                    ImportWarning(
                        "device_label_collision",
                        "device label is shared by distinct historical IDs; IDs are preserved",
                        row.location,
                    )
                )
            labels[label] = row.record_id
