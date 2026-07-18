"""Read-only validation of all existing portable data files."""

from app.bootstrap import ROOT_ENTITIES
from app.core.errors import ValidationError
from app.core.paths import PathConfig
from app.portability.csv_validation import ValidationIssue, validate_csv
from app.portability.manifest import load_manifest


def _print_issue(issue: ValidationIssue) -> None:
    row = f" row {issue.row_number}" if issue.row_number else ""
    column = f" column {issue.column}" if issue.column else ""
    print(f"ERROR {issue.file_path}{row}{column}: {issue.error_code}: {issue.message}")


def main() -> int:
    config = PathConfig.from_environment()
    root = config.portable_root
    error_count = 0
    checked = 0
    try:
        load_manifest(root / "manifest.json")
        print(f"OK manifest: {root / 'manifest.json'}")
        checked += 1
    except (OSError, ValidationError) as exc:
        print(f"ERROR manifest: {exc}")
        error_count += 1
    for entity in ROOT_ENTITIES:
        path = root / f"{entity}.csv"
        issues = validate_csv(path, entity)
        checked += 1
        for issue in issues:
            _print_issue(issue)
        error_count += len(issues)
    for entity in ("sessions", "segments", "distractions"):
        for path in sorted((root / entity).rglob("*.csv")) if (root / entity).is_dir() else ():
            issues = validate_csv(path, entity)
            checked += 1
            for issue in issues:
                _print_issue(issue)
            error_count += len(issues)
    print(f"Validated {checked} portable files; {error_count} error(s)")
    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
