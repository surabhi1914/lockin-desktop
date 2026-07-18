from pathlib import Path

import pytest

from app.core.errors import PathContractError
from app.core.paths import PathConfig, ensure_directory, safe_child


def test_default_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("LOCKIN_RUNTIME_ROOT", raising=False)
    monkeypatch.delenv("LOCKIN_PORTABLE_ROOT", raising=False)
    config = PathConfig.from_environment(tmp_path)
    assert config.runtime_root == (tmp_path / ".local_data/runtime").resolve()
    assert config.portable_root == (tmp_path / "portable_data").resolve()
    assert config.database_path.name == "lockin.sqlite3"
    assert not config.runtime_root.exists()


def test_environment_overrides_spaces_and_unicode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LOCKIN_RUNTIME_ROOT", "run time/数据")
    monkeypatch.setenv("LOCKIN_PORTABLE_ROOT", "portable space/é")
    config = PathConfig.from_environment(tmp_path, create_runtime=True, create_portable=True)
    assert config.runtime_root.is_dir()
    assert config.portable_root.is_dir()


def test_path_collision_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCKIN_RUNTIME_ROOT", "same")
    monkeypatch.setenv("LOCKIN_PORTABLE_ROOT", "same")
    with pytest.raises(PathContractError, match="separate"):
        PathConfig.from_environment(tmp_path)


def test_file_instead_of_directory_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    file_path = tmp_path / "file"
    file_path.write_text("personal", encoding="utf-8")
    monkeypatch.setenv("LOCKIN_RUNTIME_ROOT", str(file_path))
    with pytest.raises(PathContractError, match="file"):
        PathConfig.from_environment(tmp_path)
    with pytest.raises(PathContractError):
        ensure_directory(file_path)
    assert file_path.read_text(encoding="utf-8") == "personal"


def test_safe_child_rejects_escape_and_absolute(tmp_path: Path) -> None:
    with pytest.raises(PathContractError, match="traversal"):
        safe_child(tmp_path, "..", "escape.csv")
    with pytest.raises(PathContractError, match="relative"):
        safe_child(tmp_path, str((tmp_path / "absolute").resolve()))
    assert safe_child(tmp_path, "目录", "file.csv").parent.name == "目录"


def test_existing_personal_directory_is_preserved(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runtime = tmp_path / "existing"
    runtime.mkdir()
    marker = runtime / "personal.txt"
    marker.write_text("keep", encoding="utf-8")
    monkeypatch.setenv("LOCKIN_RUNTIME_ROOT", str(runtime))
    monkeypatch.setenv("LOCKIN_PORTABLE_ROOT", str(tmp_path / "portable"))
    PathConfig.from_environment(tmp_path, create_runtime=True)
    assert marker.read_text(encoding="utf-8") == "keep"
