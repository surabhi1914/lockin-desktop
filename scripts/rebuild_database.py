"""Build a fresh SQLite database from portable history at an explicit output path."""

import argparse
from pathlib import Path

from app.portability.import_models import ImportMode
from app.portability.portable_import_service import PortableImportService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rebuild LockIn SQLite from portable data")
    parser.add_argument("--portable-root", required=True, type=Path)
    parser.add_argument("--output-db", required=True, type=Path)
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if args.output_db.exists() and not args.overwrite and not args.verify_only:
        print(f"ERROR: output exists; pass --overwrite explicitly: {args.output_db}")
        return 2
    mode = ImportMode.VERIFY if args.verify_only else ImportMode.FRESH
    result = PortableImportService().run(
        args.portable_root,
        args.output_db.parent,
        mode=mode,
        database_path=args.output_db,
        allow_replace=args.overwrite,
    )
    print(f"success: {str(result.success).lower()}")
    print(f"inserted: {result.inserted} skipped: {result.skipped}")
    print(f"database: {result.database_path or args.output_db}")
    for error in result.errors:
        print(f"ERROR: {error}")
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
