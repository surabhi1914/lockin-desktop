import csv
from pathlib import Path

from app.bootstrap import run_phase0_bootstrap
from app.core.paths import PathConfig
from app.services.portable_sync_service import PortableSyncService
from app.services.portable_verification_service import PortableVerificationService
from tests.integration.test_phase6_session_persistence import Harness


def _finalized_harness(tmp_path: Path) -> tuple[Harness, PathConfig, str]:
    harness = Harness(tmp_path)
    config = PathConfig(tmp_path, tmp_path, tmp_path / "portable")
    assert run_phase0_bootstrap(config=config).success
    context = harness.start()
    harness.advance(5)
    harness.service.finalize(harness.engine.stop(), "manual_stop")
    return harness, config, context.session_id


def test_first_sync_repeat_sync_and_read_only_verification(tmp_path: Path) -> None:
    harness, config, session_id = _finalized_harness(tmp_path)
    service = PortableSyncService(
        harness.connection, config.portable_root, tmp_path / "portable_backups"
    )
    first = service.sync_session(session_id)
    assert first.success
    assert first.counts.sessions == 1
    assert first.counts.segments == 1
    session_file = next((config.portable_root / "sessions").rglob("*.csv"))
    before = session_file.read_bytes()
    second = service.sync_session(session_id)
    assert second.success
    assert second.counts.skipped == 3
    assert session_file.read_bytes() == before
    assert harness.connection.execute("SELECT COUNT(*) FROM sync_ledger").fetchone()[0] == 3
    report = PortableVerificationService(
        harness.connection, config.portable_root, tmp_path / "portable_backups"
    ).verify()
    assert report.healthy


def test_missing_ledger_is_reconciled_without_duplicate(tmp_path: Path) -> None:
    harness, config, session_id = _finalized_harness(tmp_path)
    service = PortableSyncService(harness.connection, config.portable_root, tmp_path / "backups")
    assert service.sync_all().success
    harness.connection.execute(
        "DELETE FROM sync_ledger WHERE record_type = 'session' AND record_id = ?", (session_id,)
    )
    harness.connection.commit()
    result = service.sync_all()
    assert result.success and result.counts.repaired == 1
    path = next((config.portable_root / "sessions").rglob("*.csv"))
    with path.open(encoding="utf-8", newline="") as handle:
        assert len(list(csv.DictReader(handle))) == 1


def test_stale_csv_checksum_is_backed_up_and_repaired(tmp_path: Path) -> None:
    harness, config, _session_id = _finalized_harness(tmp_path)
    service = PortableSyncService(harness.connection, config.portable_root, tmp_path / "backups")
    assert service.sync_all().success
    path = next((config.portable_root / "segments").rglob("*.csv"))
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = reader.fieldnames
    assert fieldnames is not None
    rows[0]["record_checksum"] = "0" * 64
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    result = service.sync_all()
    assert result.success and result.counts.repaired >= 1
    assert list((tmp_path / "backups" / "segments").iterdir())


def test_unfinished_session_is_not_exported(tmp_path: Path) -> None:
    harness = Harness(tmp_path)
    config = PathConfig(tmp_path, tmp_path, tmp_path / "portable")
    assert run_phase0_bootstrap(config=config).success
    harness.start()
    service = PortableSyncService(harness.connection, config.portable_root, tmp_path / "backups")
    result = service.sync_all()
    assert result.success and result.counts.sessions == 0
    assert not list((config.portable_root / "sessions").rglob("*.csv"))
