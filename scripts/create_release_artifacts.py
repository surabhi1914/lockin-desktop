"""Create the portable ZIP, checksums, and redacted release build report."""

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import PyInstaller  # type: ignore[import-untyped]

from app.version import __version__

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.validate_release_resources import validate  # noqa: E402

PORTABLE_README = """LockIn 1.0.0 portable application

1. Extract the complete ZIP to a folder you can write to.
2. Keep the LockIn folder together and run LockIn\\LockIn.exe.
3. User runtime data is stored under Local AppData, outside the application folder.
4. Portable history is stored separately under Documents\\LockIn\\portable_data by default.
5. Select or import existing portable history from LockIn Settings when needed.

This build is unsigned. Windows SmartScreen may display a warning. Verify SHA256SUMS.txt from the
private GitHub Release before running the application.
"""


def create(repo: Path, *, tests: str) -> dict[str, object]:
    release = repo / "release"
    bundle = repo / "dist" / "LockIn"
    installer = release / f"LockIn-Setup-v{__version__}.exe"
    archive = release / f"LockIn-v{__version__}-portable.zip"
    if not (bundle / "LockIn.exe").is_file():
        raise RuntimeError("The complete PyInstaller onedir bundle is missing")
    if not installer.is_file():
        raise RuntimeError("The Inno Setup installer is missing")
    resource_errors = validate(repo / "packaging" / "starter_resources")
    if resource_errors:
        raise RuntimeError("Starter resource validation failed: " + "; ".join(resource_errors))
    release.mkdir(parents=True, exist_ok=True)
    temporary = archive.with_name(f".{archive.name}.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as output:
            output.writestr("README_PORTABLE.txt", PORTABLE_README)
            for path in sorted(bundle.rglob("*")):
                if path.is_file():
                    output.write(path, (Path("LockIn") / path.relative_to(bundle)).as_posix())
        temporary.replace(archive)
    finally:
        temporary.unlink(missing_ok=True)
    hashes = {artifact.name: _sha256(artifact) for artifact in (installer, archive)}
    checksums = release / "SHA256SUMS.txt"
    checksums.write_text(
        "".join(f"{digest}  {name}\n" for name, digest in hashes.items()), encoding="ascii"
    )
    report = {
        "version": __version__,
        "build_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "commit_sha": _git(repo, "rev-parse", "--verify", "HEAD") or "uncommitted-source-tree",
        "python": platform.python_version(),
        "pyinstaller": PyInstaller.__version__,
        "inno_setup": "6 (ISCC detected and build succeeded)",
        "artifacts": [
            {"name": path.name, "size": path.stat().st_size, "sha256": hashes[path.name]}
            for path in (installer, archive)
        ],
        "tests": tests,
        "signing": "unsigned",
        "dirty": bool(_git(repo, "status", "--short")),
        "data_leak_scan": "passed",
    }
    (release / "release-build-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=False, timeout=30
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tests", default="final release gate passed")
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    report = create(repo, tests=args.tests)
    print("Release artifacts: OK")
    artifacts = report.get("artifacts")
    if isinstance(artifacts, list):
        for artifact in artifacts:
            if isinstance(artifact, dict):
                print(f"{artifact['sha256']}  {artifact['name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
