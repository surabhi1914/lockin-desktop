import os
from pathlib import Path

import pytest

from app.core.paths import PathConfig

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def isolated_config(tmp_path: Path) -> PathConfig:
    return PathConfig(
        repository_root=tmp_path,
        runtime_root=tmp_path / "runtime data",
        portable_root=tmp_path / "portable data",
    )
