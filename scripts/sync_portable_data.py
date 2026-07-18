"""Manual Phase 7 portable synchronization and verification command."""

import argparse

from app.bootstrap import run_phase0_bootstrap
from app.core.paths import PathConfig
from app.database.connection import connect_database
from app.models.portable_sync import PortableVerificationReport
from app.services.portable_sync_service import PortableSyncService
from app.services.portable_verification_service import PortableVerificationService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Synchronize finalized LockIn data to CSV")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true", help="sync all eligible finalized sessions")
    group.add_argument("--session-id", help="sync one eligible finalized session")
    group.add_argument("--verify-only", action="store_true", help="verify without changing files")
    parser.add_argument("--repair", action="store_true", help="repair missing or stale exports")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = PathConfig.from_environment()
    bootstrap = run_phase0_bootstrap(config=config)
    if not bootstrap.success:
        for error in bootstrap.errors:
            print(f"ERROR: {error}")
        return 1
    connection = connect_database(config.database_path)
    try:
        verifier = PortableVerificationService(
            connection, config.portable_root, config.runtime_root / "portable_backups"
        )
        if args.verify_only and not args.repair:
            report = verifier.verify()
            _print_verification(report)
            return 0 if report.healthy else 1
        service = PortableSyncService(
            connection, config.portable_root, config.runtime_root / "portable_backups"
        )
        result = service.sync_session(args.session_id) if args.session_id else service.sync_all()
        print(result.message)
        print(
            f"devices={result.counts.devices} sessions={result.counts.sessions} "
            f"segments={result.counts.segments} distractions={result.counts.distractions} "
            f"skipped={result.counts.skipped} repaired={result.counts.repaired}"
        )
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        if not result.success:
            return 1
        report = verifier.verify()
        _print_verification(report)
        return 0 if report.healthy else 1
    finally:
        connection.close()


def _print_verification(report: PortableVerificationReport) -> None:
    print(f"Portable verification: {'OK' if report.healthy else 'FAILED'}")
    print(f"pending={report.pending} stale={report.stale}")
    for error in report.errors:
        print(f"ERROR: {error}")


if __name__ == "__main__":
    raise SystemExit(main())
