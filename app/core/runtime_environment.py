"""Runtime facts isolated from writable application paths."""

import sys
from pathlib import Path


def is_frozen() -> bool:
    """Return whether the process is running from a frozen application bundle."""
    return bool(getattr(sys, "frozen", False))


def source_or_bundle_root() -> Path:
    """Resolve the immutable source or PyInstaller extraction root."""
    if is_frozen():
        raw = getattr(sys, "_MEIPASS", None)
        if not isinstance(raw, str) or not raw:
            raise RuntimeError("The frozen application resource root is unavailable")
        return Path(raw).resolve()
    return Path(__file__).resolve().parents[2]
