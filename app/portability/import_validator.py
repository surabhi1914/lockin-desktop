"""Complete read-only validation and logical reconstruction of portable history."""

import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from uuid import UUID, uuid5

from app.core.checksums import record_checksum
from app.core.constants import DATA_SCHEMA_VERSION, MANIFEST_SCHEMA_VERSION
from app.core.time_utils import parse_utc, validate_date
from app.models.category import category_uniqueness_key
from app.models.persisted_session import FINAL_SESSION_STATUSES, PersistedSession
from app.portability.csv_mapping import portable_row_checksum
from app.portability.csv_validation import ID_COLUMN, validate_csv
from app.portability.import_errors import (
    ImportValidationError,
    UnsupportedPortableSchemaError,
)
from app.portability.import_models import (
    EntityCounts,
    ImportConflict,
    ImportMode,
    ImportReadinessReport,
    ImportWarning,
    LogicalSegment,
    PortableImportBundle,
    PortableSourceRow,
    SourceLocation,
    SourceSummary,
)
from app.portability.manifest import PortableManifest, load_manifest
from app.services.data_location_service import resolve_portable_folder
from app.services.session_checksum_service import session_checksum

ROOT_ENTITIES = ("devices", "categories", "quotes", "daily_goals")
PARTITION_ENTITIES = ("sessions", "segments", "distractions")
FINAL_STATUSES = frozenset(FINAL_SESSION_STATUSES)
PARTITION_PATTERN = re.compile(
    r"^(sessions|segments|distractions)_(\d{4})-(\d{2})(?:_part(\d{3,}))?[.]csv$"
)
LEGACY_SEGMENT_NAMESPACE = UUID("3c37bafa-a2bd-57aa-bcdc-e0f505549f11")


class PortableImportValidator:
    def reconstruct_segments(
        self, rows: tuple[PortableSourceRow, ...]
    ) -> tuple[tuple[LogicalSegment, ...], dict[str, str]]:
        return self._reconstruct_segments(list(rows))

    def validate(
        self, selection: Path, *, runtime_root: Path | None = None
    ) -> tuple[ImportReadinessReport, PortableImportBundle | None]:
        try:
            root = resolve_portable_folder(selection, runtime_root=runtime_root)
            manifest = self._load_compatible_manifest(root / "manifest.json")
            rows, files = self._read_all(root, manifest)
            conflicts: list[ImportConflict] = []
            warnings: list[ImportWarning] = []
            logical, segment_map = self._validate_relationships(rows, conflicts, warnings)
            summary = self._summary(root, rows, logical, files)
            hashes = {path.relative_to(root).as_posix(): _sha256_file(path) for path in files}
            bundle = PortableImportBundle(
                root,
                manifest,
                {entity: tuple(values) for entity, values in rows.items()},
                logical,
                segment_map,
                summary,
                tuple(warnings),
                hashes,
            )
            report = ImportReadinessReport(
                safe=not conflicts,
                summary=summary,
                warnings=tuple(warnings),
                conflicts=tuple(conflicts),
                recommended_mode=ImportMode.FRESH,
            )
            return report, bundle
        except (ImportValidationError, OSError, ValueError) as exc:
            return ImportReadinessReport(False, None, errors=(str(exc),)), None

    def require(self, selection: Path, *, runtime_root: Path | None = None) -> PortableImportBundle:
        report, bundle = self.validate(selection, runtime_root=runtime_root)
        if bundle is None or not report.safe:
            details = (*report.errors, *(item.reason for item in report.conflicts))
            raise ImportValidationError("; ".join(details) or "portable data is not import-ready")
        return bundle

    def _load_compatible_manifest(self, path: Path) -> PortableManifest:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ImportValidationError(f"manifest cannot be read: {exc}") from exc
        if not isinstance(raw, dict):
            raise ImportValidationError("manifest root must be an object")
        manifest_version = raw.get("manifest_schema_version")
        data_version = raw.get("data_schema_version")
        if isinstance(manifest_version, int) and manifest_version > MANIFEST_SCHEMA_VERSION:
            raise UnsupportedPortableSchemaError(
                f"portable manifest schema {manifest_version} is newer than supported "
                f"schema {MANIFEST_SCHEMA_VERSION}"
            )
        if isinstance(data_version, int) and data_version > DATA_SCHEMA_VERSION:
            raise UnsupportedPortableSchemaError(
                f"portable data schema {data_version} is newer than supported "
                f"schema {DATA_SCHEMA_VERSION}"
            )
        try:
            return load_manifest(path)
        except (OSError, ValueError) as exc:
            raise ImportValidationError(f"manifest is invalid: {exc}") from exc

    def _read_all(
        self, root: Path, manifest: PortableManifest
    ) -> tuple[dict[str, list[PortableSourceRow]], tuple[Path, ...]]:
        result: dict[str, list[PortableSourceRow]] = {
            entity: [] for entity in (*ROOT_ENTITIES, *PARTITION_ENTITIES)
        }
        files: list[Path] = [root / "manifest.json"]
        for entity in ROOT_ENTITIES:
            path = root / f"{entity}.csv"
            result[entity].extend(self._read_csv(path, entity, manifest.data_schema_version))
            files.append(path)
        for entity in PARTITION_ENTITIES:
            entity_files = sorted((root / entity).glob("*/*.csv"))
            self._validate_partition_set(root, entity, entity_files)
            for path in entity_files:
                result[entity].extend(self._read_csv(path, entity, manifest.data_schema_version))
                files.append(path)
        self._reject_cross_file_duplicates(result)
        return result, tuple(files)

    def _read_csv(
        self, path: Path, entity: str, data_schema_version: int
    ) -> tuple[PortableSourceRow, ...]:
        issues = validate_csv(path, entity, data_schema_version=data_schema_version)
        if issues:
            detail = "; ".join(
                f"{issue.error_code} row={issue.row_number}: {issue.message}" for issue in issues
            )
            raise ImportValidationError(f"invalid {entity} CSV {path}: {detail}")
        rows: list[PortableSourceRow] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row_number, values in enumerate(csv.DictReader(handle), start=2):
                record_id = values[ID_COLUMN[entity]]
                checksum = self._portable_checksum(entity, values)
                if entity in {"sessions", "segments", "distractions"}:
                    supplied = values["record_checksum"]
                    if supplied != checksum:
                        raise ImportValidationError(
                            f"checksum mismatch in {path}:{row_number} for {record_id}"
                        )
                rows.append(
                    PortableSourceRow(
                        entity,
                        record_id,
                        dict(values),
                        SourceLocation(path, row_number),
                        checksum,
                    )
                )
        return tuple(rows)

    def _portable_checksum(self, entity: str, values: dict[str, str]) -> str:
        if entity == "sessions":
            session = _session_from_csv(values)
            return session_checksum(session)
        if entity in {"segments", "distractions"}:
            return portable_row_checksum(values)
        return record_checksum(values)

    def _validate_partition_set(self, root: Path, entity: str, paths: list[Path]) -> None:
        parts: dict[str, set[int]] = defaultdict(set)
        for path in paths:
            relative = path.relative_to(root)
            if len(relative.parts) != 3 or relative.parts[0] != entity:
                raise ImportValidationError(f"invalid partition location: {relative}")
            match = PARTITION_PATTERN.fullmatch(path.name)
            if match is None or match.group(1) != entity:
                raise ImportValidationError(f"invalid partition filename: {relative}")
            year, month = match.group(2), match.group(3)
            if relative.parts[1] != year or not 1 <= int(month) <= 12:
                raise ImportValidationError(
                    f"partition year/month placement is invalid: {relative}"
                )
            part = 1 if match.group(4) is None else int(match.group(4))
            if part != 1 and part < 2:
                raise ImportValidationError(f"partition number is invalid: {relative}")
            parts[f"{year}-{month}"].add(part)
        for month, numbers in parts.items():
            if numbers != set(range(1, max(numbers) + 1)):
                raise ImportValidationError(
                    f"{entity} partition numbers are not contiguous for {month}: {sorted(numbers)}"
                )

    def _reject_cross_file_duplicates(self, rows: dict[str, list[PortableSourceRow]]) -> None:
        for entity, items in rows.items():
            seen: dict[str, SourceLocation] = {}
            for item in items:
                if item.record_id in seen:
                    first = seen[item.record_id]
                    raise ImportValidationError(
                        f"duplicate {entity} ID across files: {item.record_id}; "
                        f"{first.path}:{first.row_number} and "
                        f"{item.location.path}:{item.location.row_number}"
                    )
                seen[item.record_id] = item.location

    def _validate_relationships(
        self,
        rows: dict[str, list[PortableSourceRow]],
        conflicts: list[ImportConflict],
        warnings: list[ImportWarning],
    ) -> tuple[tuple[LogicalSegment, ...], dict[str, str]]:
        devices = {row.record_id for row in rows["devices"]}
        categories = {row.record_id for row in rows["categories"]}
        sessions = {row.record_id for row in rows["sessions"]}
        self._validate_categories(rows["categories"], conflicts)
        self._validate_goals(rows["daily_goals"], conflicts)
        sequence_keys: set[tuple[str, int]] = set()
        session_by_id = {row.record_id: row for row in rows["sessions"]}
        for row in rows["sessions"]:
            values = row.values
            self._require_reference("session device", values["device_id"], devices, row)
            self._require_reference("session category", values["category_id"], categories, row)
            key = (values["device_id"], int(values["session_sequence"]))
            if key in sequence_keys:
                raise ImportValidationError(f"duplicate per-device session sequence: {key}")
            sequence_keys.add(key)
            self._validate_session(row)
            date_value = values["local_date_started"]
            if f"sessions_{date_value[:7]}" not in row.location.path.name:
                raise ImportValidationError(
                    f"session is in the wrong monthly partition: {row.record_id}"
                )
        logical, segment_map = self._reconstruct_segments(rows["segments"])
        for segment in logical:
            if segment.session_id not in sessions or segment.device_id not in devices:
                raise ImportValidationError(
                    f"segment {segment.segment_id} has an unknown session or device"
                )
        distraction_counts: dict[str, int] = defaultdict(int)
        for row in rows["distractions"]:
            values = row.values
            self._require_reference("distraction session", values["session_id"], sessions, row)
            self._require_reference("distraction device", values["device_id"], devices, row)
            self._require_reference("distraction category", values["category_id"], categories, row)
            if values["segment_id"] and values["segment_id"] not in segment_map:
                raise ImportValidationError(
                    f"distraction references unknown segment: {row.record_id}"
                )
            if f"distractions_{values['local_date'][:7]}" not in row.location.path.name:
                raise ImportValidationError(
                    f"distraction is in the wrong monthly partition: {row.record_id}"
                )
            distraction_counts[values["session_id"]] += 1
        self._validate_aggregates(session_by_id, logical, distraction_counts)
        if not rows["quotes"]:
            warnings.append(ImportWarning("no_quotes", "quotes.csv contains no active source rows"))
        return logical, segment_map

    def _validate_categories(
        self, rows: list[PortableSourceRow], conflicts: list[ImportConflict]
    ) -> None:
        names: dict[str, PortableSourceRow] = {}
        for row in rows:
            key = category_uniqueness_key(row.values["category_name"])
            if key in names and names[key].record_id != row.record_id:
                conflicts.append(
                    ImportConflict(
                        "categories",
                        row.record_id,
                        "normalized-equivalent category name uses a different ID",
                        row.location,
                        dict(names[key].values),
                        dict(row.values),
                    )
                )
            names[key] = row

    def _validate_goals(
        self, rows: list[PortableSourceRow], conflicts: list[ImportConflict]
    ) -> None:
        ordered = sorted(rows, key=lambda row: row.values["effective_from_date"])
        previous: PortableSourceRow | None = None
        for row in ordered:
            start = validate_date(row.values["effective_from_date"])
            end_text = row.values["effective_to_date"]
            end = validate_date(end_text) if end_text else None
            if end is not None and end < start:
                raise ImportValidationError(f"daily goal range is backwards: {row.record_id}")
            if previous is not None:
                prior_end_text = previous.values["effective_to_date"]
                prior_end = validate_date(prior_end_text) if prior_end_text else None
                if prior_end is None or start <= prior_end:
                    conflicts.append(
                        ImportConflict(
                            "daily_goals",
                            row.record_id,
                            "daily goal effective ranges overlap",
                            row.location,
                            dict(previous.values),
                            dict(row.values),
                        )
                    )
            previous = row

    def _validate_session(self, row: PortableSourceRow) -> None:
        values = row.values
        if values["status"] not in FINAL_STATUSES:
            raise ImportValidationError(f"portable session is not finalized: {row.record_id}")
        if not values["ended_at_utc"] or not values["ended_at_local"]:
            raise ImportValidationError(f"portable session has no end timestamp: {row.record_id}")
        planned = int(values["planned_focus_seconds"])
        completed = int(values["planned_focus_completed_seconds"])
        overtime = int(values["overtime_seconds"])
        actual = int(values["actual_focus_seconds"])
        if actual != completed + overtime:
            raise ImportValidationError(
                f"session focus formula does not reconcile: {row.record_id}"
            )
        expected_stopped = max(0, planned - completed)
        if int(values["stopped_early_seconds"]) != expected_stopped:
            raise ImportValidationError(
                f"session stopped-early formula is invalid: {row.record_id}"
            )
        complete_flag = values["completed_planned_timer"] == "true"
        if complete_flag != (completed == planned):
            raise ImportValidationError(f"session completion flag is invalid: {row.record_id}")
        source = values.get("entry_source")
        if source == "manual":
            if values.get("completion_reason") != "manual_entry":
                raise ImportValidationError(
                    f"manual session has an invalid completion reason: {row.record_id}"
                )
            if not values.get("manual_entry_created_at_utc"):
                raise ImportValidationError(
                    f"manual session has no creation timestamp: {row.record_id}"
                )
        elif source is not None and (
            values.get("completion_reason") == "manual_entry"
            or values.get("manual_entry_created_at_utc")
            or values.get("manual_entry_updated_at_utc")
        ):
            raise ImportValidationError(
                f"non-manual session contains manual metadata: {row.record_id}"
            )

    def _reconstruct_segments(
        self, rows: list[PortableSourceRow]
    ) -> tuple[tuple[LogicalSegment, ...], dict[str, str]]:
        groups: dict[tuple[str, str], list[PortableSourceRow]] = defaultdict(list)
        for row in rows:
            values = row.values
            if not values["ended_at_utc"]:
                raise ImportValidationError(f"portable segment is open: {row.record_id}")
            if f"segments_{values['local_date'][:7]}" not in row.location.path.name:
                raise ImportValidationError(f"segment is in the wrong partition: {row.record_id}")
            source_id = values["source_segment_id"] or str(
                uuid5(
                    LEGACY_SEGMENT_NAMESPACE,
                    f"{values['session_id']}:{row.record_id}:{values['started_at_utc']}",
                )
            )
            groups[(values["session_id"], source_id)].append(row)
        logical: list[LogicalSegment] = []
        id_map: dict[str, str] = {}
        consistency = (
            "session_id",
            "device_id",
            "segment_sequence",
            "segment_type",
            "timezone_name",
            "counts_as_focus",
            "pause_classification",
            "breaks_continuity",
            "continuity_group_id",
            "pause_grace_threshold_seconds",
            "focus_phase",
            "end_reason",
            "created_at_utc",
        )
        for (session_id, source_id), parts in groups.items():
            parts.sort(key=lambda item: int(item.values["midnight_part_number"]))
            numbers = [int(item.values["midnight_part_number"]) for item in parts]
            if numbers != list(range(1, len(parts) + 1)):
                raise ImportValidationError(f"midnight parts are not contiguous: {source_id}")
            first = parts[0].values
            total = 0
            previous_end: str | None = None
            for part in parts:
                values = part.values
                if any(values[field] != first[field] for field in consistency):
                    raise ImportValidationError(f"midnight part fields conflict: {source_id}")
                if previous_end is not None and values["started_at_utc"] != previous_end:
                    raise ImportValidationError(
                        f"midnight part boundaries are not adjacent: {source_id}"
                    )
                if parse_utc(values["ended_at_utc"]) < parse_utc(values["started_at_utc"]):
                    raise ImportValidationError(f"segment part is backwards: {part.record_id}")
                previous_end = values["ended_at_utc"]
                total += int(values["duration_seconds"])
                id_map[part.record_id] = source_id
            values_out: dict[str, object] = {
                "segment_id": source_id,
                "schema_version": int(first["schema_version"]),
                "session_id": session_id,
                "device_id": first["device_id"],
                "segment_sequence": int(first["segment_sequence"]),
                "segment_type": first["segment_type"],
                "started_at_utc": first["started_at_utc"],
                "ended_at_utc": parts[-1].values["ended_at_utc"],
                "timezone_name": first["timezone_name"],
                "utc_offset_started_minutes": int(first["utc_offset_minutes"]),
                "duration_seconds": total,
                "counts_as_focus": int(first["counts_as_focus"] == "true"),
                "pause_classification": first["pause_classification"],
                "breaks_continuity": int(first["breaks_continuity"] == "true"),
                "continuity_group_id": first["continuity_group_id"] or None,
                "pause_grace_threshold_seconds": int(first["pause_grace_threshold_seconds"]),
                "focus_phase": first["focus_phase"],
                "end_reason": first["end_reason"] or None,
                "created_at_utc": first["created_at_utc"],
                "updated_at_utc": parts[-1].values["ended_at_utc"],
            }
            logical.append(
                LogicalSegment(
                    source_id,
                    session_id,
                    first["device_id"],
                    values_out,
                    tuple(parts),
                )
            )
        logical.sort(
            key=lambda item: (item.session_id, _int_value(item.values["segment_sequence"]))
        )
        by_session: dict[str, list[LogicalSegment]] = defaultdict(list)
        for item in logical:
            by_session[item.session_id].append(item)
        for session_id, items in by_session.items():
            sequences = [_int_value(item.values["segment_sequence"]) for item in items]
            if sequences != list(range(1, len(items) + 1)):
                raise ImportValidationError(
                    f"logical segment sequences are not contiguous: {session_id}"
                )
            logical_previous_end: str | None = None
            for item in items:
                start = str(item.values["started_at_utc"])
                if logical_previous_end is not None and start < logical_previous_end:
                    raise ImportValidationError(f"logical segments overlap: {session_id}")
                logical_previous_end = str(item.values["ended_at_utc"])
        return tuple(logical), id_map

    def _validate_aggregates(
        self,
        sessions: dict[str, PortableSourceRow],
        segments: tuple[LogicalSegment, ...],
        distraction_counts: dict[str, int],
    ) -> None:
        totals: dict[str, dict[str, int]] = defaultdict(
            lambda: {"planned": 0, "overtime": 0, "pause": 0}
        )
        for segment in segments:
            segment_values = segment.values
            if segment_values["segment_type"] == "pause":
                totals[segment.session_id]["pause"] += _int_value(
                    segment_values["duration_seconds"]
                )
            elif segment_values["focus_phase"] == "overtime":
                totals[segment.session_id]["overtime"] += _int_value(
                    segment_values["duration_seconds"]
                )
            else:
                totals[segment.session_id]["planned"] += _int_value(
                    segment_values["duration_seconds"]
                )
        for session_id, row in sessions.items():
            session_values = row.values
            found = totals[session_id]
            expected = (
                int(session_values["planned_focus_completed_seconds"]),
                int(session_values["overtime_seconds"]),
                int(session_values["total_pause_seconds"]),
                int(session_values["distraction_count"]),
            )
            actual = (
                found["planned"],
                found["overtime"],
                found["pause"],
                distraction_counts[session_id],
            )
            if actual != expected:
                raise ImportValidationError(
                    f"session aggregate mismatch: {session_id}; expected={expected}, found={actual}"
                )

    def _require_reference(
        self, label: str, value: str, known: set[str], row: PortableSourceRow
    ) -> None:
        if value not in known:
            raise ImportValidationError(
                f"{label} is missing for {row.record_id} at "
                f"{row.location.path}:{row.location.row_number}: {value}"
            )

    def _summary(
        self,
        root: Path,
        rows: dict[str, list[PortableSourceRow]],
        logical: tuple[LogicalSegment, ...],
        files: tuple[Path, ...],
    ) -> SourceSummary:
        dates = sorted(row.values["local_date_started"] for row in rows["sessions"])
        labels = tuple(
            f"{row.values['device_label'] or 'Unnamed device'} ({row.record_id[:8]})"
            for row in rows["devices"]
        )
        return SourceSummary(
            root,
            EntityCounts(
                devices=len(rows["devices"]),
                categories=len(rows["categories"]),
                quotes=len(rows["quotes"]),
                goals=len(rows["daily_goals"]),
                sessions=len(rows["sessions"]),
                segment_rows=len(rows["segments"]),
                logical_segments=len(logical),
                distractions=len(rows["distractions"]),
            ),
            dates[0] if dates else None,
            dates[-1] if dates else None,
            labels,
            len(files),
        )


def _session_from_csv(values: dict[str, str]) -> PersistedSession:
    integer_fields = {
        "schema_version",
        "session_sequence",
        "utc_offset_started_minutes",
        "planned_focus_seconds",
        "actual_focus_seconds",
        "planned_focus_completed_seconds",
        "overtime_seconds",
        "total_pause_seconds",
        "wall_clock_seconds",
        "continuous_block_count",
        "longest_continuous_seconds",
        "average_continuous_seconds",
        "median_continuous_seconds",
        "pause_count",
        "short_pause_count",
        "long_pause_count",
        "distraction_count",
        "stopped_early_seconds",
    }
    boolean_fields = {
        "completed_planned_timer",
        "overtime_enabled",
        "fullscreen_used",
        "quotes_enabled",
        "start_ritual_enabled",
    }
    optional_fields = {
        "ended_at_utc",
        "ended_at_local",
        "completion_reason",
        "manual_entry_created_at_utc",
        "manual_entry_updated_at_utc",
    }
    fields = PersistedSession.__dataclass_fields__
    converted: dict[str, object] = {}
    for name in fields:
        if name == "record_checksum":
            converted[name] = values.get(name) or None
        elif name == "entry_source" and name not in values:
            converted[name] = "imported"
        elif (
            name
            in {
                "manual_entry_created_at_utc",
                "manual_entry_updated_at_utc",
            }
            and name not in values
        ):
            converted[name] = None
        elif name in integer_fields:
            converted[name] = int(values[name])
        elif name in boolean_fields:
            converted[name] = values[name] == "true"
        elif name in optional_fields:
            converted[name] = values[name] or None
        else:
            converted[name] = values[name]
    return PersistedSession(**converted)  # type: ignore[arg-type]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _int_value(value: object) -> int:
    if not isinstance(value, (str, int)):
        raise ImportValidationError(
            f"expected integer-compatible value, found {type(value).__name__}"
        )
    return int(value)
