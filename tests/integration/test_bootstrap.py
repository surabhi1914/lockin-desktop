import csv
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.bootstrap import main, run_phase0_bootstrap
from app.core.paths import PathConfig
from app.portability.csv_contracts import header_for


def _row_count(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.reader(handle)) - 1


def test_fresh_and_second_bootstrap_are_idempotent(isolated_config: PathConfig) -> None:
    first = run_phase0_bootstrap(config=isolated_config)
    assert first.success, first.errors
    categories = isolated_config.portable_root / "categories.csv"
    quotes = isolated_config.portable_root / "quotes.csv"
    original_categories = categories.read_bytes()
    original_quotes = quotes.read_bytes()
    assert _row_count(categories) == 9
    assert _row_count(quotes) >= 40

    second = run_phase0_bootstrap(config=isolated_config)
    assert second.success, second.errors
    assert categories.read_bytes() == original_categories
    assert quotes.read_bytes() == original_quotes


def test_check_only_does_not_write(isolated_config: PathConfig) -> None:
    result = run_phase0_bootstrap(config=isolated_config, check_only=True)
    assert not result.success
    assert not isolated_config.runtime_root.exists()
    assert not isolated_config.portable_root.exists()

    assert run_phase0_bootstrap(config=isolated_config).success
    before = {
        path.relative_to(isolated_config.repository_root): path.stat().st_mtime_ns
        for path in isolated_config.repository_root.rglob("*")
        if path.is_file()
    }
    result = run_phase0_bootstrap(config=isolated_config, check_only=True)
    after = {
        path.relative_to(isolated_config.repository_root): path.stat().st_mtime_ns
        for path in isolated_config.repository_root.rglob("*")
        if path.is_file()
    }
    assert result.success, result.errors
    assert after == before


def test_populated_categories_and_quotes_are_preserved(isolated_config: PathConfig) -> None:
    assert run_phase0_bootstrap(config=isolated_config).success
    categories = isolated_config.portable_root / "categories.csv"
    quotes = isolated_config.portable_root / "quotes.csv"
    with categories.open("a", encoding="utf-8", newline="") as handle:
        csv.writer(handle, lineterminator="\n").writerow(
            [
                "1",
                "550e8400-e29b-41d4-a716-446655440000",
                "Personal Category",
                "",
                "true",
                "2026-07-16T12:00:00Z",
                "2026-07-16T12:00:00Z",
            ]
        )
    with quotes.open("a", encoding="utf-8", newline="") as handle:
        csv.writer(handle, lineterminator="\n").writerow(
            ["personal", "My personal focus line", "", "", "true", "true"]
        )
    category_bytes = categories.read_bytes()
    quote_bytes = quotes.read_bytes()
    result = run_phase0_bootstrap(config=isolated_config)
    assert result.success, result.errors
    assert categories.read_bytes() == category_bytes
    assert quotes.read_bytes() == quote_bytes


def test_invalid_portable_data_fails_without_overwrite(isolated_config: PathConfig) -> None:
    isolated_config.portable_root.mkdir(parents=True)
    categories = isolated_config.portable_root / "categories.csv"
    categories.write_text("bad,header\npersonal,data\n", encoding="utf-8")
    original = categories.read_bytes()
    result = run_phase0_bootstrap(config=isolated_config)
    assert not result.success
    assert "header" in " ".join(result.errors)
    assert categories.read_bytes() == original
    assert not isolated_config.database_path.exists()


def test_header_only_files_are_seeded(isolated_config: PathConfig) -> None:
    root = isolated_config.portable_root
    root.mkdir(parents=True)
    for entity in ("categories", "quotes"):
        with (root / f"{entity}.csv").open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle, lineterminator="\n").writerow(header_for(entity))
    result = run_phase0_bootstrap(config=isolated_config)
    assert result.success, result.errors
    assert _row_count(root / "categories.csv") == 9
    assert _row_count(root / "quotes.csv") == 40


def test_valid_default_quotes_are_imported_and_source_preserved(
    isolated_config: PathConfig,
) -> None:
    source = isolated_config.repository_root / "default_quotes.csv"
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(
            ("quote_id", "quote_text", "author", "category", "is_active", "is_favorite")
        )
        writer.writerow(("custom", "Unicode clarity é", "", "", "true", "false"))
    original = source.read_bytes()
    result = run_phase0_bootstrap(config=isolated_config)
    assert result.success, result.errors
    assert source.read_bytes() == original
    assert _row_count(isolated_config.portable_root / "quotes.csv") == 1


def test_invalid_default_quotes_fail_clearly(isolated_config: PathConfig) -> None:
    source = isolated_config.repository_root / "default_quotes.csv"
    source.write_text("bad,header\n", encoding="utf-8")
    result = run_phase0_bootstrap(config=isolated_config)
    assert not result.success
    assert "default_quotes.csv is invalid" in " ".join(result.errors)


def test_roots_must_remain_separate(tmp_path: Path) -> None:
    same = tmp_path / "same"
    config = PathConfig(tmp_path, same, same)
    result = run_phase0_bootstrap(config=config)
    assert not result.success
    assert "separate" in " ".join(result.errors).lower()


def test_inspection_script_reports_expected_values(isolated_config: PathConfig) -> None:
    assert run_phase0_bootstrap(config=isolated_config).success
    repository = Path(__file__).resolve().parents[2]
    environment = os.environ.copy()
    environment["LOCKIN_RUNTIME_ROOT"] = str(isolated_config.runtime_root)
    environment["LOCKIN_PORTABLE_ROOT"] = str(isolated_config.portable_root)
    completed = subprocess.run(
        [sys.executable, "scripts/inspect_phase0.py"],
        cwd=repository,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Database schema version: 4" in completed.stdout
    assert "Starter-category count: 9" in completed.stdout
    assert "Quote count: 40" in completed.stdout
    assert "temporary_intention_text" not in completed.stdout


def test_bootstrap_cli_reports_success_and_check_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("LOCKIN_RUNTIME_ROOT", str(tmp_path / "runtime"))
    monkeypatch.setenv("LOCKIN_PORTABLE_ROOT", str(tmp_path / "portable"))
    assert main([]) == 0
    success_output = capsys.readouterr().out
    assert "bootstrap: OK" in success_output
    (tmp_path / "portable" / "manifest.json").write_text("bad", encoding="utf-8")
    assert main(["--check-only"]) == 1
    failure_output = capsys.readouterr().out
    assert "FAILED" in failure_output
