# Testing and validation

Run from the repository root with the isolated interpreter:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest --cov=app.core --cov=app.database --cov=app.portability --cov=app.bootstrap --cov=app.application --cov=app.ui --cov=app.services --cov=app.models --cov=app.themes --cov=app.timer --cov=app.shortcuts --cov-report=term-missing --cov-fail-under=90
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy app scripts
.\.venv\Scripts\python.exe scripts\validate_portable_data.py
.\.venv\Scripts\python.exe main.py --phase0-bootstrap --check-only
.\.venv\Scripts\python.exe scripts\inspect_phase0.py
```

Success means all Phase 0-5 tests pass, combined coverage is at least 90%, Ruff reports no lint or
formatting differences, mypy reports no type errors, portable validation reports zero errors,
check-only performs no writes, and inspection reports schema version 1 with expected starter data.

Tests use temporary directories, SQLite databases, QSettings INI files, and offscreen Qt widgets.
Timer authority comes from `ManualClock`: tests advance exact integer nanoseconds or Decimal-safe
seconds without sleeping. This makes sub-second rounding, irregular polling, overshoot, pause
boundaries, completion, overtime, exact grace classification, events, and continuous-block summaries
deterministic. A system-clock-independence test guards against wall-time and refresh-count timing.

The no-persistence UI test records session/segment/distraction row counts, partition file lists, and
SHA-256 hashes of every existing portable file before exercising start, completion, overtime, stop,
and reset. All values must remain identical afterward.

Phase 3 tests cover category/draft validation, repository semantics, strict/atomic portable storage,
coordinated commit and rollback, startup conflicts, permanent restart behavior, setup-to-engine
handoff, Qt form/dialog/category management, and proof that intention and preview state are unsaved.

Phase 4 adds deterministic tests for ritual ordering and delayed engine start, black responsive
canvas/time formats, static quote selection, control/cursor inactivity, current-screen selection,
geometry restore, monitor removal, minimize/tray continuity, completion/overtime, summary status,
every active close-guard state, and tray Exit reuse. Full-flow hashing proves focus use changes no
session-related table, partition list, `categories.csv`, `quotes.csv`, goals, or manifest.

Phase 5 tests cover registry ordering/defaults, portable validation and conflicts, atomic QSettings
save/recovery, manager lifecycle/local context, every editable control, active-window/minimized/tray
scope, every action and disabled guarantee, current-mapping help/hints, marker values/reset/summary,
and proof that shortcut/marker use writes no session-related SQLite or portable file.

## Manual Phase 5 scenarios

- A: Space pauses/resumes; activating another application blocks it.
- B: disable Space; visible Pause still works.
- C: reassign pause to Ctrl+P and verify current hints/help.
- D: stage an F11 conflict, see Apply blocked, then resolve it.
- E: type Space/D/Q in intention, category, settings, and shortcut capture without focus actions.
- F: F11 toggles full screen, Esc exits only, and disabled Esc does nothing.
- G: Ctrl+Shift+S opens only one existing stop confirmation.
- H: mark three distractions, see 3 in summary, and verify the next session starts at zero.
- I: Q hides/restores the same quote; C reveals controls/cursor.
- J: help shows enabled current custom mappings only.
- K: minimized/hidden shortcuts do nothing and work again after restore.
- L: SQLite counts and portable session/distraction file lists remain unchanged; only QSettings keys
  store shortcut preferences.

## Manual Phase 4 scenarios

- A: ritual with intention, then stop; intention clears.
- B: windowed resize, pause/resume, and control/cursor hide/reveal.
- C: current extended-monitor full screen, other-monitor use, and uninterrupted exit full screen.
- D: minimize for at least 10 seconds; restore to accurately advanced time.
- E: hide/show through tray and verify tooltip/status.
- F: completion overlay once, no sound, and waiting adds no focus.
- G: explicit overtime, pause/resume, and split planned/overtime summary.
- H: cancel Stop once, then Stop and Review.
- I: Keep Focusing, Minimize to Tray, and End Session and Exit guard choices.
- J: no DB/CSV/reference mutation and no intention leakage.

## Manual Phase 3 scenarios

- A: select Machine Learning, enter an intention, start/stop, and confirm the intention clears.
- B: create Portfolio Work inline, confirm selection, restart, and confirm SQLite/CSV persistence.
- C: try ` machine   learning ` and confirm duplicate rejection with no row.
- D: rename to Portfolio Projects and confirm the identifier is unchanged and CSV has one row.
- E: archive/restore and confirm disappearance/reappearance in focus setup.
- F: confirm `Other` rename/archive protection.
- G: verify 0h0m blocked, 0h1m allowed, invalid category blocked, and >240 intention blocked.
- H: use the preview and confirm no session/segment rows, history files, or persisted intention.

## Phase 2 timer regression scenarios

Launch `main.py`, open **Start Focus**, and verify:

- A: a 10-second countdown completes once and remains at zero.
- B: pausing after about 3 seconds freezes focus while pause grows; Resume continues focus.
- C: stopping a 20-second timer after about 5 seconds freezes every value.
- D: after completion, Start Overtime counts upward and total focus equals planned plus overtime.
- E: a pause below grace resumes in one continuous block.
- F: a pause above grace resumes in a second block and logs one `continuity_broken` event.

## Phase 6 required validation

Run `pytest -q`, the documented coverage command with `--fail-under=90`, `ruff check .`,
`ruff format --check .`, `mypy app scripts`, `python scripts/verify_session_integrity.py`, and
`python scripts/inspect_sessions.py` from `.venv`. The read-only integrity command checks foreign
keys, open/finalized segments, sequence/overlap, aggregate sums, distractions, runtime ownership,
and final checksums. Manual scenarios A–K are in `PHASE_6_ACCEPTANCE_CHECKLIST.md`.

Manual real-time values are approximate; ManualClock tests are authoritative. Also review navigation,
all five themes, tray fallback, minimum-size scrolling, button states, text clipping, and the visible
“not saved” warning.
## Phase 7 verification commands

Run `python scripts/sync_portable_data.py --verify-only`,
`python scripts/verify_portable_sync.py`, and `python scripts/inspect_portable_data.py` from the
project virtual environment. Write-path tests must use isolated `LOCKIN_RUNTIME_ROOT` and
`LOCKIN_PORTABLE_ROOT` values. The acceptance suite covers rotation, checksum/ledger repair,
atomic failure preservation, cross-midnight splitting, and repeat-sync idempotency.

## Phase 8 acceptance

Run the full quality suite plus:

```powershell
.\.venv\Scripts\python.exe scripts\inspect_import_readiness.py --portable-root .\portable_data
.\.venv\Scripts\python.exe scripts\import_portable_data.py --portable-root .\portable_data --mode verify
```

Fresh/merge, staging-failure, conflict, and reimport tests must use temporary portable copies and
runtime roots. Assert source hashes before and after every destructive scenario. Required coverage
includes fresh reconstruction, merge/idempotency, backup and atomic failure, semantic conflicts,
historical/new devices, category/goal reconciliation, midnight segments, distractions, ledger
rebuild, active/unfinished blocks, onboarding, and successful Phase 7 export after import.

## Phase 9 acceptance

Recovery tests cover crash-running, paused and overtime interruption, confirmed/unknown separation,
discard, transaction rollback, idempotency, portable export, sleep pause classification, new
continuity groups, native-event isolation, and event deduplication. The two recovery fixture scripts
default to disposable runtime roots; inspection opens SQLite read-only and never prints intention.

## Phases 10–12 acceptance

Quote/audio tests use deterministic selectors and a fake backend. Goal/dashboard fixtures cover
historical ranges, local-midnight allocation, streaks, records, and cache invalidation. Analytics
fixtures cover every metric family, presets, DST, filters, history pagination/detail, export
boundaries, heatmap/theme smoke tests, and intention absence. The performance script creates a
temporary five-year 10,000-session/50,000-segment/20,000-distraction database and prints query plans.
The final coverage gate includes recovery, quotes, audio, and analytics and requires at least 90%.

## Phase 13 release acceptance

Release tests cover frozen/default/override paths, Unicode and spaces, resource traversal/missing
failure, version CLI, noninteractive health JSON, starter-resource contamination, deterministic icon,
and About identity/privacy. Packaged acceptance runs health against disposable roots, scans the
onedir/ZIP, reviews PyInstaller warnings, and validates executable metadata. Installer acceptance
tests install, shortcuts, health/launch, uninstall retention, reinstall, and retained data. The final
checker scans the intended Git tree, package, checksums, repository visibility, tag, and exact release
assets.
