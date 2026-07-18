"""Read-only resource lookup for source, tests, and frozen bundles."""

from dataclasses import dataclass
from pathlib import Path

from app.core.runtime_environment import source_or_bundle_root


class ResourceError(RuntimeError):
    """Raised when a required immutable application resource is unavailable."""


@dataclass(frozen=True, slots=True)
class ResourceLocator:
    root: Path

    @classmethod
    def standard(cls) -> "ResourceLocator":
        return cls(source_or_bundle_root())

    def required(self, *parts: str) -> Path:
        path = self._resolve(parts)
        if not path.is_file():
            raise ResourceError(f"Required LockIn resource is missing: {'/'.join(parts)}")
        return path

    def required_directory(self, *parts: str) -> Path:
        path = self._resolve(parts)
        if not path.is_dir():
            raise ResourceError(f"Required LockIn resource directory is missing: {'/'.join(parts)}")
        return path

    def optional(self, *parts: str) -> Path | None:
        path = self._resolve(parts)
        return path if path.is_file() else None

    def _resolve(self, parts: tuple[str, ...]) -> Path:
        if not parts or any(not part or Path(part).is_absolute() for part in parts):
            raise ResourceError("Resource paths must use non-empty relative components")
        candidate = self.root.joinpath(*parts).resolve()
        root = self.root.resolve()
        if candidate != root and root not in candidate.parents:
            raise ResourceError("Resource path escapes the immutable bundle root")
        return candidate
