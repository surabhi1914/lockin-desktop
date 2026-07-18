import json
import struct
import sys
from pathlib import Path

import pytest

import main as main_module
from app.core import paths, runtime_environment
from app.core.errors import PathContractError
from app.core.resources import ResourceError, ResourceLocator
from app.health import run_health_check
from app.version import __version__
from scripts.prepare_release_resources import prepare
from scripts.validate_release_resources import validate


def test_version_cli_uses_authoritative_release_identity(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main_module.main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == f"LockIn {__version__}"


def test_installed_paths_are_outside_bundle_and_support_overrides(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundle = tmp_path / "Program Files" / "LockIn" / "bundle"
    local = tmp_path / "Local App Data Ω"
    documents = tmp_path / "OneDrive" / "Documents Ω"
    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    monkeypatch.setattr(paths, "_documents_directory", lambda: documents)
    monkeypatch.setattr(paths, "_installed_data_root", lambda: local / "LockIn")
    config = paths.PathConfig.from_environment(repo_root=bundle)
    assert config.runtime_root == local / "LockIn" / "runtime"
    assert config.portable_root == documents / "LockIn" / "portable_data"
    assert bundle not in config.runtime_root.parents
    assert config.logs_root == local / "LockIn" / "logs"

    monkeypatch.setenv("LOCKIN_RUNTIME_ROOT", str(tmp_path / "override runtime"))
    monkeypatch.setenv("LOCKIN_PORTABLE_ROOT", str(tmp_path / "override portable"))
    overridden = paths.PathConfig.from_environment(repo_root=bundle)
    assert overridden.runtime_root.name == "override runtime"
    assert overridden.portable_root.name == "override portable"


def test_runtime_and_portable_collision_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LOCKIN_RUNTIME_ROOT", str(tmp_path / "same"))
    monkeypatch.setenv("LOCKIN_PORTABLE_ROOT", str(tmp_path / "same"))
    with pytest.raises(PathContractError, match="must be separate"):
        paths.PathConfig.from_environment(repo_root=tmp_path)


def test_resource_locator_is_rooted_read_only_and_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    root.mkdir()
    resource = root / "value.txt"
    resource.write_text("value", encoding="utf-8")
    locator = ResourceLocator(root)
    assert locator.required("value.txt") == resource
    assert locator.required_directory(".") == root
    assert locator.optional("missing.txt") is None
    with pytest.raises(ResourceError, match="missing"):
        locator.required("missing.txt")
    with pytest.raises(ResourceError, match="escapes"):
        locator.required("..", "outside.txt")
    with pytest.raises(ResourceError, match="relative"):
        locator.required(str(resource.resolve()))


def test_windows_known_folders_and_frozen_bundle_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert paths._documents_directory().is_absolute()
    assert paths._installed_data_root().name == "LockIn"
    bundle = tmp_path / "bundle Ω"
    bundle.mkdir()
    monkeypatch.setattr(runtime_environment, "is_frozen", lambda: True)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    assert runtime_environment.source_or_bundle_root() == bundle
    monkeypatch.delattr(sys, "_MEIPASS")
    with pytest.raises(RuntimeError, match="resource root"):
        runtime_environment.source_or_bundle_root()


def test_sanitized_starter_resources_reject_history_rows(tmp_path: Path) -> None:
    root = tmp_path / "starter"
    prepare(root)
    assert validate(root) == ()
    with (root / "templates" / "sessions.csv").open("a", encoding="utf-8") as handle:
        handle.write("unexpected,row\n")
    assert any("only its header" in error for error in validate(root))


def test_health_check_is_noninteractive_and_uses_isolated_paths(
    qapp: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("LOCKIN_RUNTIME_ROOT", str(tmp_path / "runtime space Ω"))
    monkeypatch.setenv("LOCKIN_PORTABLE_ROOT", str(tmp_path / "portable space Ω"))
    output = tmp_path / "diagnostics" / "health.json"
    assert run_health_check(output) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["version"] == "1.0.0"
    assert report["result"] == "ok"
    assert report["database"] == {"integrity": "ok", "schema_version": 4, "available": True}
    assert "intention" not in output.read_text(encoding="utf-8").casefold()


def test_generated_icon_has_png_and_seven_ico_images() -> None:
    root = Path(__file__).resolve().parents[2] / "app" / "assets" / "icons"
    assert (root / "lockin.png").read_bytes().startswith(b"\x89PNG")
    reserved, kind, count = struct.unpack("<HHH", (root / "lockin.ico").read_bytes()[:6])
    assert (reserved, kind, count) == (0, 1, 7)
