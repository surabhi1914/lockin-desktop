# Packaging and release

LockIn 1.1.1 uses PyInstaller 6 onedir and Inno Setup 6. Packaging requires Python 3.12 and the
project `.venv`; Inno Setup is the only external compiler. Builds are unsigned.

```powershell
.\scripts\clean_build.ps1
.\scripts\build_windows.ps1
.\scripts\smoke_test_packaged.ps1
.\scripts\build_installer.ps1
.\.venv\Scripts\python.exe scripts\create_release_artifacts.py
.\.venv\Scripts\python.exe scripts\final_release_check.py --post-build
```

The build regenerates the deterministic icon and sanitized starter resources, validates zero
device/goal/history rows, embeds only explicit themes/migrations/audio/icon/templates, and creates
`dist\LockIn\LockIn.exe`. The smoke test uses Unicode paths with spaces and verifies frozen resource
resolution, SQLite migrations, Qt, writability, and absence of bundle-side data.

Inno Setup produces a per-user installer under `release`. The standard-library ZIP creator includes
the complete onedir `LockIn` folder and `README_PORTABLE.txt`. `SHA256SUMS.txt` contains lowercase
digests for the installer and ZIP. `release-build-report.json` records redacted tool/build evidence
but is not a GitHub Release asset.

Release binaries and `release/` are Git-ignored. The GitHub Release uploads exactly the installer,
portable ZIP, and checksums. A private repository, pushed release commit, annotated `v1.1.1`, stable
Release, and verified assets are mandatory before publication is complete. The v1.0.0 and v1.0.1
tags and Releases remain immutable historical release records.
