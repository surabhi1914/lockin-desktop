# Development setup

## Prerequisites

- Windows 10 or 11
- Python 3.12 available through the `py` launcher
- Visual Studio Code with the recommended Microsoft Python and Ruff extensions
- PowerShell opened at the repository root

No Conda, Poetry, Docker, Node.js, Qt Designer, SQLite server, or global package installation is
required. PySide6 is the GUI dependency and pytest-qt is installed through `.[dev]`.

## Create and install the environment

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

VS Code settings select `.venv\Scripts\python.exe`. If necessary, run **Python: Select
Interpreter** and choose that file. Dependencies are installed only inside `.venv`.

## Initialize Phase 0

```powershell
.\.venv\Scripts\python.exe main.py --phase0-bootstrap
.\.venv\Scripts\python.exe main.py --phase0-bootstrap --check-only
```

The first command creates ignored development runtime data and validates or safely creates portable
starter files. The second command is read-only. Both may be rerun; populated portable CSV files are
never erased. Environment variables can override defaults:

```powershell
$env:LOCKIN_RUNTIME_ROOT = "C:\path with spaces\runtime"
$env:LOCKIN_PORTABLE_ROOT = "C:\path with spaces\portable"
```

The roots must differ. Unset overrides with `Remove-Item Env:LOCKIN_RUNTIME_ROOT` and the equivalent
portable variable.

## Launch LockIn 1.0.0

```powershell
.\.venv\Scripts\python.exe main.py
```

The normal Windows title bar and system tray require a graphical desktop session. Automated Qt tests
set `QT_QPA_PLATFORM=offscreen` through the test configuration and isolate QSettings in temporary
INI files; they never use personal registry settings.

Release tooling is installed only in `.venv` through `.[dev]`. Inno Setup 6 must be installed
explicitly; scripts never download it. See [13_PACKAGING_AND_RELEASE.md](13_PACKAGING_AND_RELEASE.md).

## Verify

Run every command in [12_TESTING.md](12_TESTING.md). Equivalent VS Code tasks are available under
**Terminal → Run Task**. The default launch configuration starts the Phase 1 GUI; a separate launch
configuration preserves the Phase 0 bootstrap.

## Phase 8 import tools

Use only the project virtual environment:

```powershell
.\.venv\Scripts\python.exe scripts\inspect_import_readiness.py --portable-root .\portable_data
.\.venv\Scripts\python.exe scripts\import_portable_data.py --portable-root .\portable_data --mode verify
```

Fresh/merge experiments must provide a disposable `--runtime-root`; never point destructive tests
at personal runtime data. `scripts\rebuild_database.py` is the explicit fresh-rebuild wrapper and
`scripts\compare_database_to_portable.py` verifies a reconstructed result.
