# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

project = Path(SPECPATH).resolve().parent
metadata = project / "build" / "release_metadata" / "build_commit.txt"

datas = [
    (str(project / "app" / "themes"), "app/themes"),
    (str(project / "app" / "database" / "schema_v1.sql"), "app/database"),
    (str(project / "app" / "database" / "schema_v2.sql"), "app/database"),
    (str(project / "app" / "database" / "schema_v3.sql"), "app/database"),
    (str(project / "app" / "database" / "schema_v4.sql"), "app/database"),
    (str(project / "app" / "assets" / "lockin_completion.wav"), "app/assets"),
    (str(project / "app" / "assets" / "icons"), "app/assets/icons"),
    (str(project / "packaging" / "starter_resources"), "starter_resources"),
    (str(project / "LICENSE"), "."),
]
if metadata.is_file():
    datas.append((str(metadata), "."))

a = Analysis(
    [str(project / "main.py")],
    pathex=[str(project)],
    binaries=[],
    datas=datas,
    hiddenimports=["PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "zoneinfo"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "mypy", "ruff", "PyInstaller", "tkinter"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LockIn",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project / "app" / "assets" / "icons" / "lockin.ico"),
    version=str(project / "packaging" / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="LockIn",
)
