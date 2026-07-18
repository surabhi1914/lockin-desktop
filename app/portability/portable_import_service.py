"""Verification-first orchestration for fresh and merge portable imports."""

from dataclasses import replace
from pathlib import Path

from app.core.ids import new_uuid4
from app.core.time_utils import format_utc, utc_now
from app.portability.database_rebuilder import DatabaseRebuilder
from app.portability.import_conflict_detector import ImportConflictDetector
from app.portability.import_errors import PortableImportError
from app.portability.import_manifest_service import write_conflict_report
from app.portability.import_models import (
    ImportConflict,
    ImportMode,
    ImportPlan,
    ImportResult,
    PlannedOperation,
)
from app.portability.import_validator import PortableImportValidator


class PortableImportService:
    def __init__(self, *, validator: PortableImportValidator | None = None) -> None:
        self._validator = validator or PortableImportValidator()
        self._detector = ImportConflictDetector()

    def run(
        self,
        portable_root: Path,
        runtime_root: Path,
        *,
        mode: ImportMode = ImportMode.VERIFY,
        database_path: Path | None = None,
        skip_conflicts: bool = False,
        allow_replace: bool = False,
        local_device_id: str | None = None,
        local_device_label: str = "This device",
        failure_injector: object | None = None,
    ) -> ImportResult:
        import_id = new_uuid4()
        target = (database_path or runtime_root / "lockin.sqlite3").resolve()
        report, bundle = self._validator.validate(portable_root, runtime_root=runtime_root)
        if bundle is None:
            return ImportResult(
                False,
                import_id,
                mode,
                errors=report.errors or ("portable validation failed",),
                database_path=target,
            )
        plan_path = target if mode in {ImportMode.MERGE, ImportMode.VERIFY} else None
        effective_mode = mode
        if mode == ImportMode.VERIFY:
            effective_mode = ImportMode.MERGE if target.is_file() else ImportMode.FRESH
        plan = self._detector.plan(bundle, plan_path, mode=effective_mode)
        plan = self._include_source_conflicts(plan, report.conflicts)
        if mode == ImportMode.VERIFY:
            return ImportResult(
                not plan.conflicts and not report.errors,
                import_id,
                mode,
                inserted=plan.inserts,
                skipped=plan.skips,
                conflicts=plan.conflicts,
                warnings=tuple(item.message for item in plan.warnings),
                errors=report.errors,
                database_path=target,
                operations=plan.operations,
            )
        conflict_report: Path | None = None
        if plan.conflicts:
            conflict_report = write_conflict_report(
                runtime_root / "import_diagnostics",
                import_id=import_id,
                source_root=bundle.root,
                timestamp=format_utc(utc_now()),
                conflicts=plan.conflicts,
            )
            if not skip_conflicts:
                return ImportResult(
                    False,
                    import_id,
                    mode,
                    conflicts=plan.conflicts,
                    warnings=tuple(item.message for item in plan.warnings),
                    errors=("unresolved conflicts prevent import",),
                    database_path=target,
                    conflict_report_path=conflict_report,
                    operations=plan.operations,
                )
        before_hashes = dict(bundle.file_hashes)

        def assert_source_unchanged() -> None:
            if self._validator.require(bundle.root).file_hashes != before_hashes:
                raise PortableImportError("portable files changed during import")

        try:
            injector = failure_injector if callable(failure_injector) else None
            inserted, skipped, device_id, backup, staging = DatabaseRebuilder(
                runtime_root,
                failure_injector=injector,
                source_guard=assert_source_unchanged,
            ).promote(
                bundle,
                plan,
                target,
                import_id=import_id,
                mode=mode,
                skip_conflicts=skip_conflicts,
                local_device_id=local_device_id,
                local_device_label=local_device_label,
                allow_replace=allow_replace,
            )
            assert_source_unchanged()
            return ImportResult(
                True,
                import_id,
                mode,
                inserted,
                skipped,
                plan.conflicts,
                tuple(item.message for item in plan.warnings),
                (),
                backup,
                None if not staging.exists() else staging,
                target,
                device_id,
                conflict_report,
                plan.operations,
            )
        except (PortableImportError, OSError, RuntimeError, ValueError) as exc:
            staging = target.with_name(f".{target.stem}.import-{import_id}.sqlite3")
            return ImportResult(
                False,
                import_id,
                mode,
                conflicts=plan.conflicts,
                warnings=tuple(item.message for item in plan.warnings),
                errors=(str(exc),),
                staging_path=staging if staging.exists() else None,
                database_path=target,
                conflict_report_path=conflict_report,
                operations=plan.operations,
            )

    def _include_source_conflicts(
        self, plan: ImportPlan, source_conflicts: tuple[ImportConflict, ...]
    ) -> ImportPlan:
        if not source_conflicts:
            return plan
        conflicts = tuple(source_conflicts)
        conflict_keys = {(item.entity, item.record_id) for item in conflicts}
        operations = tuple(
            replace(item, action="conflict")
            if (item.entity, item.record_id) in conflict_keys
            else item
            for item in plan.operations
        )
        known = {(item.entity, item.record_id) for item in operations}
        operations += tuple(
            PlannedOperation(item.entity, item.record_id, "conflict")
            for item in conflicts
            if (item.entity, item.record_id) not in known
        )
        return replace(plan, operations=operations, conflicts=(*plan.conflicts, *conflicts))
