"""Explicit verify/fresh/merge portable import command."""

import argparse
import tempfile
from pathlib import Path
from uuid import uuid4

from app.portability.import_models import ImportMode
from app.portability.portable_import_service import PortableImportService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify or import LockIn portable history")
    parser.add_argument("--portable-root", required=True, type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument(
        "--mode", choices=tuple(item.value for item in ImportMode), default="verify"
    )
    parser.add_argument("--skip-conflicts", action="store_true")
    parser.add_argument("--yes", action="store_true", help="confirm destructive database promotion")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    mode = ImportMode(args.mode)
    if mode != ImportMode.VERIFY and args.runtime_root is None:
        parser.error("--runtime-root is required for fresh and merge modes")
    runtime_root = args.runtime_root or (
        Path(tempfile.gettempdir()) / f"lockin-phase8-verify-{uuid4()}"
    )
    if mode != ImportMode.VERIFY and not args.yes:
        answer = input(f"Promote a staged {mode.value} database into {runtime_root}? [y/N] ")
        if answer.strip().casefold() not in {"y", "yes"}:
            print("Import cancelled; no database was changed.")
            return 2
    result = PortableImportService().run(
        args.portable_root,
        runtime_root,
        mode=mode,
        skip_conflicts=args.skip_conflicts,
        allow_replace=args.yes,
    )
    print(f"mode: {mode.value}")
    print(f"success: {str(result.success).lower()}")
    print(f"inserted: {result.inserted}")
    print(f"skipped: {result.skipped}")
    print(f"conflicts: {len(result.conflicts)}")
    print(f"database: {result.database_path or '-'}")
    print(f"backup: {result.backup_path or '-'}")
    print(f"new_local_device_id: {result.local_device_id or '-'}")
    if result.conflict_report_path:
        print(f"conflict_report: {result.conflict_report_path}")
    for warning in result.warnings:
        print(f"WARNING: {warning}")
    for error in result.errors:
        print(f"ERROR: {error}")
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
