# LockIn v1.1.0 acceptance checklist

- [x] Entry gate passes before implementation.
- [x] Schema v5 upgrades fresh and populated v4 databases without loss.
- [x] Manual command validates date, duration, category, timezone, DST, and midnight boundaries.
- [x] Duplicate/unresolved overlaps block and partial/full overlaps require confirmation.
- [x] Transaction creates exact finalized aggregates and one/two focus-only segments.
- [x] No runtime, heartbeat, recovery, pause, distraction, sleep, or intention data is created.
- [x] History action, dialog, badge, filter, details, restart, sorting, and paging pass.
- [x] Dashboard, goals, streaks, heatmap, records, and statistics include manual focus.
- [x] Portable schema v2 migration, backups, sync, checksums, idempotency, import, and rebuild pass.
- [x] Editing and deletion remain omitted because safe propagation is unavailable.
- [x] Full tests, coverage, Ruff, formatting, mypy, integrity, sync, analytics, and manual verifier pass.
- [x] Manual scenarios A–L pass without subprocess or transient-window flicker.
- [x] Packaged, portable, installer, upgrade, uninstall, and reinstall checks pass.
- [ ] Private v1.1.0 commit, tag, Release, assets, and checksums are verified.

## Recorded evidence

- 429 tests passed; combined branch coverage was 90.13%.
- Ruff check, Ruff formatting, strict mypy, SQLite integrity, portable verification, analytics,
  dashboard, import readiness, and manual-session verification all passed.
- A populated installed v1.0.1 database upgraded to schema v5 with all common table rows preserved,
  zero foreign-key errors, and 80 non-database data files unchanged.
- Development, PyInstaller, and installed UI inspection found only the LockIn main window plus
  intentionally parented modal dialogs, with zero interaction-time child processes.
- Silent upgrade, uninstall retention, reinstall, frozen health, Start Menu shortcut, and
  Add/Remove Programs registration passed; release publication remains the final open gate.
