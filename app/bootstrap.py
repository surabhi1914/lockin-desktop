"""Idempotent Phase 0 repository and development-data bootstrap."""

import argparse
import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from app.core.constants import DATA_SCHEMA_VERSION, DATABASE_SCHEMA_VERSION
from app.core.errors import LockInError, ValidationError
from app.core.ids import starter_category_uuid
from app.core.paths import PathConfig, ensure_directory
from app.core.time_utils import format_utc, utc_now
from app.database.migrations import current_schema_version, initialize_database
from app.portability.csv_contracts import header_for
from app.portability.csv_validation import ValidationIssue, validate_csv
from app.portability.manifest import create_manifest_if_absent, load_manifest

ROOT_ENTITIES = ("devices", "categories", "quotes", "daily_goals")
STARTER_CATEGORIES = (
    "Machine Learning",
    "DSA",
    "Projects",
    "Research",
    "Job Applications",
    "Reading",
    "Interview Preparation",
    "Administrative",
    "Other",
)
STARTER_QUOTES = (
    "Begin with one clear step.",
    "Small progress still moves the work forward.",
    "Give this moment your full attention.",
    "Steady effort makes difficult work lighter.",
    "Choose the next useful action.",
    "Focus grows when distractions wait.",
    "A calm start can build strong momentum.",
    "Keep the task simple and the effort honest.",
    "One focused block can change the day.",
    "Make room for the work that matters.",
    "Return gently to the task.",
    "Clarity comes through patient effort.",
    "Protect this time for meaningful progress.",
    "Work at a pace you can sustain.",
    "Attention is a choice made again and again.",
    "Let the next step be enough.",
    "Consistency turns practice into skill.",
    "Stay curious when the work feels hard.",
    "A quiet mind can solve a noisy problem.",
    "Finish the thought before chasing another.",
    "Progress begins when preparation ends.",
    "Build momentum with a manageable action.",
    "Your effort now supports your future self.",
    "Pause, breathe, and choose the priority.",
    "Deep work rewards a patient beginning.",
    "Keep going until the idea becomes clear.",
    "Use this block with intention.",
    "Good work grows from undivided attention.",
    "Solve what is in front of you.",
    "Let steady practice do the heavy lifting.",
    "The important task deserves a real start.",
    "Make the next minute count.",
    "Direction matters more than speed.",
    "Stay with the question a little longer.",
    "Create space, then create progress.",
    "A focused hour is built one minute at a time.",
    "Trust the process of careful work.",
    "Turn attention into something useful.",
    "Complete one meaningful piece.",
    "End this block knowing you showed up.",
)


@dataclass(frozen=True)
class BootstrapResult:
    success: bool
    actions: tuple[str, ...]
    errors: tuple[str, ...]


def _format_issue(issue: ValidationIssue) -> str:
    location = str(issue.file_path)
    if issue.row_number is not None:
        location += f":{issue.row_number}"
    if issue.column:
        location += f" [{issue.column}]"
    return f"{location}: {issue.error_code}: {issue.message}"


def _csv_path(portable_root: Path, entity: str) -> Path:
    return portable_root / f"{entity}.csv"


def _validate_existing_portable(portable_root: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = portable_root / "manifest.json"
    if manifest_path.exists():
        try:
            load_manifest(manifest_path)
        except (OSError, ValidationError) as exc:
            errors.append(f"{manifest_path}: {exc}")
    for entity in ROOT_ENTITIES:
        path = _csv_path(portable_root, entity)
        if path.exists():
            errors.extend(_format_issue(issue) for issue in validate_csv(path, entity))
    for entity in ("sessions", "segments", "distractions"):
        directory = portable_root / entity
        if directory.is_dir():
            for path in sorted(directory.rglob("*.csv")):
                errors.extend(_format_issue(issue) for issue in validate_csv(path, entity))
    return errors


def _write_rows(path: Path, entity: str, rows: list[tuple[str, ...]]) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header_for(entity))
        writer.writerows(rows)


def _append_rows(path: Path, rows: list[tuple[str, ...]]) -> None:
    with path.open("a", encoding="utf-8", newline="") as handle:
        csv.writer(handle, lineterminator="\n").writerows(rows)


def _has_data_rows(path: Path) -> bool:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        return next(reader, None) is not None


def _category_rows(timestamp: str) -> list[tuple[str, ...]]:
    return [
        (
            str(DATA_SCHEMA_VERSION),
            starter_category_uuid(name),
            name,
            "",
            "true",
            timestamp,
            timestamp,
        )
        for name in STARTER_CATEGORIES
    ]


def _generated_quote_rows() -> list[tuple[str, ...]]:
    return [
        (f"q{number:03d}", text, "", "focus", "true", "false")
        for number, text in enumerate(STARTER_QUOTES, start=1)
    ]


def _quote_rows(repository: Path) -> list[tuple[str, ...]]:
    source = repository / "default_quotes.csv"
    if not source.exists():
        return _generated_quote_rows()
    issues = validate_csv(source, "quotes")
    if issues:
        details = "; ".join(_format_issue(issue) for issue in issues)
        raise ValidationError(f"default_quotes.csv is invalid: {details}")
    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader)
        return [tuple(row) for row in reader]


def _check_only(config: PathConfig) -> BootstrapResult:
    errors: list[str] = []
    if not config.runtime_root.is_dir():
        errors.append(f"Runtime directory is missing: {config.runtime_root}")
    if not config.portable_root.is_dir():
        errors.append(f"Portable directory is missing: {config.portable_root}")
    else:
        errors.extend(_validate_existing_portable(config.portable_root))
        if not (config.portable_root / "manifest.json").exists():
            errors.append("Portable manifest is missing")
        for entity in ROOT_ENTITIES:
            if not _csv_path(config.portable_root, entity).exists():
                errors.append(f"Portable root CSV is missing: {entity}.csv")
    if not config.database_path.is_file():
        errors.append(f"Runtime database is missing: {config.database_path}")
    else:
        uri = f"file:{config.database_path.as_posix()}?mode=ro&immutable=1"
        with sqlite3.connect(uri, uri=True) as connection:
            version = current_schema_version(connection)
        if version != DATABASE_SCHEMA_VERSION:
            errors.append(
                f"Database schema version is {version}; expected {DATABASE_SCHEMA_VERSION}"
            )
    return BootstrapResult(
        not errors, ("Check-only validation completed; no files changed",), tuple(errors)
    )


def run_phase0_bootstrap(
    *, config: PathConfig | None = None, check_only: bool = False
) -> BootstrapResult:
    """Run or validate the complete Phase 0 foundation."""
    try:
        resolved = config or PathConfig.from_environment()
    except LockInError as exc:
        return BootstrapResult(False, (), (str(exc),))
    if resolved.runtime_root.resolve() == resolved.portable_root.resolve():
        return BootstrapResult(False, (), ("Runtime and portable data roots must be separate",))
    if check_only:
        try:
            return _check_only(resolved)
        except (OSError, sqlite3.Error, LockInError) as exc:
            return BootstrapResult(False, (), (str(exc),))

    actions: list[str] = []
    try:
        if resolved.portable_root.exists():
            existing_errors = _validate_existing_portable(resolved.portable_root)
            if existing_errors:
                return BootstrapResult(False, (), tuple(existing_errors))

        ensure_directory(resolved.runtime_root)
        actions.append(f"Runtime directory ready: {resolved.runtime_root}")
        connection = initialize_database(resolved.database_path)
        connection.close()
        actions.append(f"SQLite schema v{DATABASE_SCHEMA_VERSION} ready: {resolved.database_path}")

        ensure_directory(resolved.portable_root)
        for entity in ("sessions", "segments", "distractions"):
            ensure_directory(resolved.portable_root / entity)
        manifest, created = create_manifest_if_absent(resolved.portable_root / "manifest.json")
        actions.append(
            f"Portable manifest {'created' if created else 'validated'} "
            f"(schema v{manifest.manifest_schema_version})"
        )

        timestamp = format_utc(utc_now())
        for entity in ("devices", "daily_goals"):
            path = _csv_path(resolved.portable_root, entity)
            if not path.exists():
                _write_rows(path, entity, [])
                actions.append(f"Created {path.name}")
            else:
                actions.append(f"Validated {path.name}")

        categories_path = _csv_path(resolved.portable_root, "categories")
        category_rows = _category_rows(timestamp)
        if not categories_path.exists():
            _write_rows(categories_path, "categories", category_rows)
            actions.append(f"Created categories.csv with {len(category_rows)} starter records")
        elif not _has_data_rows(categories_path):
            _append_rows(categories_path, category_rows)
            actions.append(f"Seeded {len(category_rows)} starter categories")
        else:
            actions.append("Preserved populated categories.csv")

        quotes_path = _csv_path(resolved.portable_root, "quotes")
        quote_rows = _quote_rows(resolved.repository_root)
        if not quotes_path.exists():
            _write_rows(quotes_path, "quotes", quote_rows)
            actions.append(f"Created quotes.csv with {len(quote_rows)} starter records")
        elif not _has_data_rows(quotes_path):
            _append_rows(quotes_path, quote_rows)
            actions.append(f"Seeded {len(quote_rows)} starter quotes")
        else:
            actions.append("Preserved populated quotes.csv")

        final_errors = _validate_existing_portable(resolved.portable_root)
        if final_errors:
            return BootstrapResult(False, tuple(actions), tuple(final_errors))
        return BootstrapResult(True, tuple(actions), ())
    except (OSError, sqlite3.Error, LockInError) as exc:
        return BootstrapResult(False, tuple(actions), (str(exc),))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap the LockIn Phase 0 data foundation")
    parser.add_argument("--phase0-bootstrap", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--check-only", action="store_true", help="validate without writing")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = run_phase0_bootstrap(check_only=args.check_only)
    print("LockIn Phase 0 bootstrap: " + ("OK" if result.success else "FAILED"))
    for action in result.actions:
        print(f"  - {action}")
    for error in result.errors:
        print(f"  ERROR: {error}")
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
