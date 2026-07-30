"""Fail-closed Phase 13 source, package, privacy, and publication validator."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from app.version import __version__

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.validate_release_resources import validate  # noqa: E402

SECRET_PATTERNS = (
    "ghp_",
    "github_pat_",
    "sk-",
    "AKIA",
    "BEGIN PRIVATE KEY",
    "BEGIN OPENSSH PRIVATE KEY",
    "password=",
    "token=",
    "secret=",
)
RUNTIME_SUFFIXES = (
    ".db",
    ".sqlite",
    ".sqlite3",
    ".db-wal",
    ".db-shm",
    ".log",
    ".bak",
)
REQUIRED_DOCS = (
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "RELEASE_NOTES.md",
    "CHANGELOG.md",
    "docs/PHASE_13_ACCEPTANCE_CHECKLIST.md",
    "docs/FINAL_PROJECT_ACCEPTANCE.md",
    "docs/HOTFIX_1_0_1_ACCEPTANCE.md",
    "docs/MANUAL_PAST_SESSION_LOGGING.md",
    "docs/V1_1_0_ACCEPTANCE_CHECKLIST.md",
    "docs/V1_1_1_ACCEPTANCE_CHECKLIST.md",
)
V1_0_0_COMMIT = "0a05c9619eea749bedfa3475359441935c819688"
V1_0_0_ASSETS = {
    "LockIn-Setup-v1.0.0.exe": (
        40_912_144,
        "sha256:02a3783dff8a53f4d506b635f971bc17ab6188296a2bcaafff2aee12ea8bf52a",
    ),
    "LockIn-v1.0.0-portable.zip": (
        56_842_513,
        "sha256:88d3389dc6f29366fc3f211876b00842153ca3123a35725a4a156bf5790a2621",
    ),
    "SHA256SUMS.txt": (
        185,
        "sha256:5366c19295183bc5eb9aa1d3aad6aca6fa54649086e2d4c40d86a9f3a2bf9287",
    ),
}
V1_0_1_COMMIT = "b64793c0834b844a9b5ffe5087092d9e1bcc63b9"
V1_0_1_ASSETS = {
    "LockIn-Setup-v1.0.1.exe": (
        40_913_041,
        "sha256:0ed3a10382c5b0b130f2c8eb577daf254613814e74967c8a9539ae7477e98a7b",
    ),
    "LockIn-v1.0.1-portable.zip": (
        56_850_710,
        "sha256:71b0a0369e9d93338141d049464c4a4dac90a8fdf43f01c781d83c40de3f072c",
    ),
    "SHA256SUMS.txt": (
        185,
        "sha256:a67c471eb692f05e5999d70488704f9bc3541085d1b7f9e1db7c2bf63648308a",
    ),
}
V1_1_0_COMMIT = "4181632c7a7d39e836bb7629cfcd3edde1b704aa"
V1_1_0_ASSETS = {
    "LockIn-Setup-v1.1.0.exe": (
        40_944_063,
        "sha256:44eee1b629c6702c64b43e4e9ee58382ad506455fd5868884a503c909a52cc88",
    ),
    "LockIn-v1.1.0-portable.zip": (
        56_874_654,
        "sha256:c914f12e85eb9b768afef4df97276a1b62ee1822970f3dabd023d9d6710a3e86",
    ),
    "SHA256SUMS.txt": (
        185,
        "sha256:dc731caad5ef3fac736a7c32250f099a9a250d5922be249aee0b117f9ca80301",
    ),
}


def check(repo: Path, mode: str) -> tuple[str, ...]:
    errors: list[str] = []
    candidates = _source_candidates(repo)
    for relative in candidates:
        lowered = relative.casefold()
        parts = Path(relative).parts
        is_runtime_directory = any(
            part in {".local_data", "logs", "backups", "diagnostics"} for part in parts
        ) and parts[:2] != ("app", "diagnostics")
        if lowered.endswith(RUNTIME_SUFFIXES) or is_runtime_directory:
            errors.append(f"runtime or backup file would be tracked: {relative}")
    errors.extend(_scan_secrets(repo, candidates))
    for required in REQUIRED_DOCS:
        if not (repo / required).is_file():
            errors.append(f"required release document missing: {required}")
    errors.extend(_version_errors(repo))
    errors.extend(validate(repo / "packaging" / "starter_resources"))
    if mode in {"post-build", "post-publication"}:
        errors.extend(_artifact_errors(repo))
        errors.extend(_bundle_errors(repo))
        errors.extend(_health_errors(repo))
    errors.extend(_repository_visibility_errors(repo, required=mode == "post-publication"))
    errors.extend(
        _prior_release_preservation_errors(
            repo,
            version="1.0.0",
            expected_commit=V1_0_0_COMMIT,
            expected_assets=V1_0_0_ASSETS,
            required=mode == "post-publication",
        )
    )
    errors.extend(
        _prior_release_preservation_errors(
            repo,
            version="1.1.0",
            expected_commit=V1_1_0_COMMIT,
            expected_assets=V1_1_0_ASSETS,
            required=mode == "post-publication",
        )
    )
    errors.extend(
        _prior_release_preservation_errors(
            repo,
            version="1.0.1",
            expected_commit=V1_0_1_COMMIT,
            expected_assets=V1_0_1_ASSETS,
            required=mode == "post-publication",
        )
    )
    if mode == "post-publication":
        errors.extend(_publication_errors(repo))
    return tuple(errors)


def _source_candidates(repo: Path) -> tuple[str, ...]:
    result = _run(
        repo,
        "git",
        "ls-files",
        "--cached",
        "--others",
        "--exclude-standard",
        "-z",
    )
    return tuple(value for value in result.stdout.split("\0") if value)


def _scan_secrets(repo: Path, candidates: tuple[str, ...]) -> list[str]:
    errors: list[str] = []
    # These two validators contain the literal detection signatures by design.
    allowlisted = {
        "scripts/final_release_check.py",
        "scripts/validate_release_resources.py",
    }
    for relative in candidates:
        if relative in allowlisted:
            continue
        path = repo / relative
        if not path.is_file() or path.stat().st_size > 10 * 1024 * 1024:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern in SECRET_PATTERNS:
            found = (
                re.search(r"(?<![A-Za-z])sk-[A-Za-z0-9]", text, re.IGNORECASE) is not None
                if pattern == "sk-"
                else pattern.casefold() in text.casefold()
            )
            if found:
                errors.append(f"possible credential pattern {pattern!r} in {relative}")
    return errors


def _version_errors(repo: Path) -> list[str]:
    errors: list[str] = []
    required = {
        "pyproject.toml": f'version = "{__version__}"',
        "installer/LockIn.iss": f'#define MyAppVersion "{__version__}"',
        "packaging/version_info.txt": f"ProductVersion', u'{__version__}",
        "RELEASE_NOTES.md": f"LockIn v{__version__}",
        "CHANGELOG.md": f"[{__version__}]",
    }
    for relative, marker in required.items():
        path = repo / relative
        if not path.is_file() or marker not in path.read_text(encoding="utf-8"):
            errors.append(f"version {__version__} missing or inconsistent in {relative}")
    return errors


def _artifact_errors(repo: Path) -> list[str]:
    release = repo / "release"
    installer = release / f"LockIn-Setup-v{__version__}.exe"
    archive = release / f"LockIn-v{__version__}-portable.zip"
    checksums = release / "SHA256SUMS.txt"
    report = release / "release-build-report.json"
    errors = [
        f"release artifact missing: {path.name}"
        for path in (installer, archive, checksums, report)
        if not path.is_file()
    ]
    if errors:
        return errors
    expected: dict[str, str] = {}
    for line in checksums.read_text(encoding="ascii").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match:
            expected[match.group(2)] = match.group(1)
    for artifact in (installer, archive):
        actual = _sha256(artifact)
        if expected.get(artifact.name) != actual:
            errors.append(f"checksum mismatch: {artifact.name}")
    try:
        with zipfile.ZipFile(archive) as portable:
            names = portable.namelist()
            if "README_PORTABLE.txt" not in names or "LockIn/LockIn.exe" not in names:
                errors.append("portable ZIP does not contain the documented complete layout")
            for name in names:
                lowered = name.casefold()
                if lowered.endswith(RUNTIME_SUFFIXES) or "portable_data/" in lowered:
                    errors.append(f"personal/runtime data path in portable ZIP: {name}")
    except (OSError, zipfile.BadZipFile) as exc:
        errors.append(f"portable ZIP is invalid: {exc}")
    return errors


def _bundle_errors(repo: Path) -> list[str]:
    bundle = repo / "dist" / "LockIn"
    errors: list[str] = []
    if not (bundle / "LockIn.exe").is_file():
        return ["dist/LockIn/LockIn.exe is missing"]
    for path in bundle.rglob("*"):
        if path.is_file() and path.name.casefold().endswith(RUNTIME_SUFFIXES):
            errors.append(f"runtime data embedded in bundle: {path.relative_to(bundle)}")
    warning = repo / "build" / "LockIn" / "warn-LockIn.txt"
    if not warning.is_file():
        errors.append("PyInstaller warning report is missing")
    elif "ERROR:" in warning.read_text(encoding="utf-8", errors="replace"):
        errors.append("fatal PyInstaller warning marker found")
    return errors


def _health_errors(repo: Path) -> list[str]:
    exe = repo / "dist" / "LockIn" / "LockIn.exe"
    if not exe.is_file():
        return []
    with tempfile.TemporaryDirectory(prefix="lockin-final-health-") as temporary:
        root = Path(temporary)
        output = root / "health.json"
        environment = os.environ.copy()
        environment.update(
            {
                "LOCKIN_RUNTIME_ROOT": str(root / "runtime Ω"),
                "LOCKIN_PORTABLE_ROOT": str(root / "portable Ω"),
                "LOCKIN_SETTINGS_PATH": str(root / "settings.ini"),
            }
        )
        result = subprocess.run(
            [str(exe), "--health-check-output", str(output)],
            env=environment,
            check=False,
            timeout=60,
        )
        if result.returncode != 0 or not output.is_file():
            return ["packaged health check failed"]
        report = json.loads(output.read_text(encoding="utf-8"))
        if report.get("result") != "ok" or report.get("version") != __version__:
            return ["packaged health report is unhealthy or has the wrong version"]
    return []


def _repository_visibility_errors(repo: Path, *, required: bool) -> list[str]:
    if not _run(repo, "git", "remote", "get-url", "origin").stdout.strip():
        return ["private origin remote is missing"] if required else []
    result = _run(repo, "gh", "repo", "view", "--json", "visibility,nameWithOwner")
    if result.returncode != 0:
        return ["private repository visibility could not be verified"] if required else []
    data = json.loads(result.stdout)
    return [] if data.get("visibility") == "PRIVATE" else ["GitHub repository is not private"]


def _publication_errors(repo: Path) -> list[str]:
    errors: list[str] = []
    head = _run(repo, "git", "rev-parse", "HEAD").stdout.strip()
    tag = _run(repo, "git", "rev-list", "-n", "1", f"v{__version__}").stdout.strip()
    if not head or tag != head:
        errors.append(f"v{__version__} does not point at HEAD")
    release = _run(repo, "gh", "release", "view", f"v{__version__}", "--json", "assets,tagName")
    if release.returncode != 0:
        return [*errors, "GitHub Release could not be verified"]
    data = json.loads(release.stdout)
    names = {item["name"] for item in data.get("assets", [])}
    expected = {
        f"LockIn-Setup-v{__version__}.exe",
        f"LockIn-v{__version__}-portable.zip",
        "SHA256SUMS.txt",
    }
    if names != expected:
        errors.append("GitHub Release assets do not exactly match the approved set")
    return errors


def _prior_release_preservation_errors(
    repo: Path,
    *,
    version: str,
    expected_commit: str,
    expected_assets: dict[str, tuple[int, str]],
    required: bool,
) -> list[str]:
    errors: list[str] = []
    tag_name = f"v{version}"
    tag_commit = _run(repo, "git", "rev-list", "-n", "1", tag_name).stdout.strip()
    if tag_commit != expected_commit:
        errors.append(f"{tag_name} tag no longer resolves to the original release commit")
    release = _run(
        repo,
        "gh",
        "release",
        "view",
        tag_name,
        "--json",
        "assets,tagName,isDraft,isPrerelease",
    )
    if release.returncode != 0:
        if required:
            errors.append(f"{tag_name} GitHub Release could not be verified")
        return errors
    data = json.loads(release.stdout)
    if data.get("tagName") != tag_name or data.get("isDraft") or data.get("isPrerelease"):
        errors.append(f"{tag_name} GitHub Release identity or stability changed")
    assets = {
        item.get("name"): (item.get("size"), item.get("digest")) for item in data.get("assets", [])
    }
    if assets != expected_assets:
        errors.append(f"{tag_name} GitHub Release assets changed from the recorded size/digest set")
    return errors


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(repo: Path, *command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, cwd=repo, capture_output=True, text=True, check=False, timeout=60
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--pre-build", action="store_true")
    group.add_argument("--post-build", action="store_true")
    group.add_argument("--post-publication", action="store_true")
    args = parser.parse_args(argv)
    mode = (
        "pre-build" if args.pre_build else "post-build" if args.post_build else "post-publication"
    )
    errors = check(Path(__file__).resolve().parents[1], mode)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Final release check ({mode}): OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
