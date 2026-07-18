"""Fail closed when release starter resources contain personal or runtime data."""

import argparse
import csv
from pathlib import Path

from app.bootstrap import STARTER_CATEGORIES, STARTER_QUOTES
from app.portability.csv_contracts import header_for
from app.portability.manifest import load_manifest

EXPECTED_FILES = frozenset(
    {
        "manifest.json",
        "devices.csv",
        "daily_goals.csv",
        "categories.csv",
        "quotes.csv",
        "templates/sessions.csv",
        "templates/segments.csv",
        "templates/distractions.csv",
    }
)
PROHIBITED_SUFFIXES = (".db", ".sqlite", ".sqlite3", ".db-wal", ".db-shm", ".log", ".bak")


def validate(root: Path) -> tuple[str, ...]:
    root = root.resolve()
    errors: list[str] = []
    files = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    extra = sorted(files - EXPECTED_FILES)
    missing = sorted(EXPECTED_FILES - files)
    if extra:
        errors.append("unexpected starter files: " + ", ".join(extra))
    if missing:
        errors.append("missing starter files: " + ", ".join(missing))
    if any(path.lower().endswith(PROHIBITED_SUFFIXES) for path in files):
        errors.append("runtime database, log, or backup file found")
    try:
        load_manifest(root / "manifest.json")
    except (OSError, ValueError) as exc:
        errors.append(f"manifest invalid: {exc}")
    for relative, entity in (
        ("devices.csv", "devices"),
        ("daily_goals.csv", "daily_goals"),
        ("templates/sessions.csv", "sessions"),
        ("templates/segments.csv", "segments"),
        ("templates/distractions.csv", "distractions"),
    ):
        errors.extend(_empty_contract(root / relative, entity))
    category_rows = _rows(root / "categories.csv", "categories", errors)
    quote_rows = _rows(root / "quotes.csv", "quotes", errors)
    if [row.get("category_name") for row in category_rows] != list(STARTER_CATEGORIES):
        errors.append("categories.csv is not the deterministic starter category set")
    if [row.get("quote_text") for row in quote_rows] != list(STARTER_QUOTES):
        errors.append("quotes.csv is not the deterministic starter quote set")
    lowered = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in root.rglob("*")
        if path.is_file()
    ).casefold()
    for phrase in ("temporary_intention", "ghp_", "github_pat_", "begin private key"):
        if phrase in lowered:
            errors.append(f"prohibited content in starter resources: {phrase}")
    return tuple(errors)


def _empty_contract(path: Path, entity: str) -> list[str]:
    errors: list[str] = []
    rows = _rows(path, entity, errors)
    if rows:
        errors.append(f"{path.name} must contain only its header")
    return errors


def _rows(path: Path, entity: str, errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != header_for(entity):
                errors.append(f"{path.name} header does not match {entity}")
            return list(reader)
    except OSError as exc:
        errors.append(f"cannot read {path}: {exc}")
        return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "packaging" / "starter_resources",
    )
    args = parser.parse_args(argv)
    errors = validate(args.root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Sanitized starter resources: OK")
    print("devices=0 goals=0 sessions=0 segments=0 distractions=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
