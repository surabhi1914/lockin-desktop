"""Safe separation of runtime and portable storage roots."""

import os
from dataclasses import dataclass
from pathlib import Path

from app.core.constants import DATABASE_FILENAME
from app.core.errors import PathContractError
from app.core.runtime_environment import is_frozen, source_or_bundle_root


def repository_root() -> Path:
    return source_or_bundle_root()


def _documents_directory() -> Path:
    if os.name == "nt":
        try:
            import winreg

            key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                raw, _kind = winreg.QueryValueEx(key, "Personal")
            if isinstance(raw, str) and raw.strip():
                return Path(os.path.expandvars(raw)).expanduser().resolve()
        except OSError:
            pass
    return (Path.home() / "Documents").resolve()


def _installed_data_root() -> Path:
    raw = os.environ.get("LOCALAPPDATA")
    if raw:
        return (Path(raw).expanduser() / "LockIn").resolve()
    return (Path.home() / "AppData" / "Local" / "LockIn").resolve()


def _resolved_path(raw: str | Path, base: Path) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def ensure_directory(path: Path) -> None:
    """Create an application-owned directory, or validate an existing one."""
    if path.exists() and not path.is_dir():
        raise PathContractError(f"Expected a directory but found a file: {path}")
    path.mkdir(parents=True, exist_ok=True)


def validate_directory_candidate(path: Path) -> None:
    if path.exists() and not path.is_dir():
        raise PathContractError(f"Expected a directory but found a file: {path}")


def safe_child(root: Path, *parts: str) -> Path:
    """Create a resolved child path that cannot escape its root."""
    if not parts or any(not part or Path(part).is_absolute() for part in parts):
        raise PathContractError("Generated child path must use non-empty relative parts")
    if any(".." in Path(part).parts for part in parts):
        raise PathContractError("Path traversal is not allowed")
    resolved_root = root.resolve()
    child = resolved_root.joinpath(*parts).resolve()
    if child != resolved_root and resolved_root not in child.parents:
        raise PathContractError(f"Generated path escapes portable root: {child}")
    return child


@dataclass(frozen=True)
class PathConfig:
    repository_root: Path
    runtime_root: Path
    portable_root: Path

    @property
    def database_path(self) -> Path:
        return self.runtime_root / DATABASE_FILENAME

    @property
    def application_data_root(self) -> Path:
        return self.runtime_root.parent

    @property
    def logs_root(self) -> Path:
        return self.application_data_root / "logs"

    @property
    def backups_root(self) -> Path:
        return self.application_data_root / "backups"

    @property
    def diagnostics_root(self) -> Path:
        return self.application_data_root / "diagnostics"

    @classmethod
    def from_environment(
        cls,
        repo_root: Path | None = None,
        *,
        create_runtime: bool = False,
        create_portable: bool = False,
    ) -> "PathConfig":
        root = (repo_root or repository_root()).resolve()
        runtime_override = os.environ.get("LOCKIN_RUNTIME_ROOT")
        portable_override = os.environ.get("LOCKIN_PORTABLE_ROOT")
        if is_frozen():
            runtime = (
                _resolved_path(runtime_override, root)
                if runtime_override
                else _installed_data_root() / "runtime"
            )
            portable = (
                _resolved_path(portable_override, root)
                if portable_override
                else _documents_directory() / "LockIn" / "portable_data"
            )
        else:
            runtime = _resolved_path(runtime_override or ".local_data/runtime", root)
            portable = _resolved_path(portable_override or "portable_data", root)
        validate_directory_candidate(runtime)
        validate_directory_candidate(portable)
        if runtime == portable:
            raise PathContractError("Runtime and portable data roots must be separate")
        config = cls(root, runtime, portable)
        if create_runtime:
            ensure_directory(runtime)
        if create_portable:
            ensure_directory(portable)
        return config
