# Phase 13 acceptance checklist

- [x] All Phase 0–12 tests, quality gates, integrity, sync, import, and analytics checks passed first.
- [x] Version 1.0.0 is consistent in Python, metadata, installer, docs, artifacts, and release notes.
- [x] Frozen resources are read-only and writable installed paths are outside the install directory.
- [x] Sanitized starter resources contain no device, goal, session, segment, or distraction rows.
- [x] Original deterministic PNG/multi-resolution ICO is used by the app and installer.
- [x] PyInstaller creates the reviewed windowed `dist\LockIn\LockIn.exe` onedir bundle.
- [x] `--version` and isolated `--health-check-output` succeed without a blocking GUI.
- [x] Portable ZIP contains the complete onedir folder plus `README_PORTABLE.txt`.
- [x] Per-user Inno installer creates shortcuts and Add/Remove Programs registration.
- [x] Install, health, uninstall retention, reinstall, and retained-data checks pass.
- [x] Binaries are truthfully documented as unsigned and SHA-256 checksums are published.
- [x] Final checker validates source, versions, resources, package, checksums, health, and privacy.
- [x] README, numbered docs, security, contributing, changelog, release notes, and CI are finalized.
- [x] `.gitignore` and scans exclude runtime data, personal portable history, output, and credentials.
- [x] The publication gate verifies the private GitHub repository, release commit, pushed tag, and the three approved release assets.
- [x] Project publication is complete when `scripts/final_release_check.py --post-publication` passes for `v1.0.0`.
