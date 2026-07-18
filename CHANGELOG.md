# Changelog

## [1.0.1] - 2026-07-18

- Fixed transient native-window flicker during UI interaction by parenting category-row controls
  before their visibility is changed.
- Added disabled-by-default process-launch and Qt transient-window diagnostics plus regression tests.
- No feature, schema migration, or user-history change; v1.0.0 data remains fully compatible.

## [1.0.0] - 2026-07-17

- Hardened source/frozen resource and writable production-path separation.
- Added version/About identity, original multi-resolution icon, and non-GUI health diagnostics.
- Added sanitized starter-resource generation and release privacy validation.
- Added PyInstaller onedir, portable ZIP, unsigned per-user Inno Setup installer, checksums, and
  release build report.
- Added install/uninstall/reinstall acceptance, final release checker, Windows CI, security policy,
  release notes, and final project documentation.
- Completed the local-first focus, recovery, portable data, dashboard, statistics, and history
  feature set as LockIn 1.0.0.

## Unreleased - Phase 5

- Added eight configurable focus-window-only shortcuts with per-action enablement, reassignment,
  strict validation/conflicts, reset/apply/revert controls, and device-local QSettings storage.
- Added defensive dispatch for active focus/window, minimized/hidden, modal, text-editing, enabled,
  and timer-state context without global hooks.
- Added current shortcut help/hints plus immutable in-memory distraction markers, subtle feedback,
  summary count, and session-disposal reset.
- Added Phase 5 unit, Qt, integration, scope, settings-recovery, and no-persistence tests/docs.
- Did not add global shortcuts, sound, quote rotation, session/distraction persistence or CSV sync,
  sleep/crash recovery, statistics/history, Spotify, packaging, or installation behavior.

## Phase 4

- Added a dedicated theme-independent black focus view with ritual, temporary intention, countdown,
  responsive timer, static validated quote, mouse-revealed controls, and cursor auto-hide.
- Added current-monitor full screen with geometry restoration and primary-screen recovery when a
  monitor disappears.
- Added minimize/tray continuity and active timer tooltip status without tray timer actions.
- Added exactly-once completion, explicit overtime, stop confirmation, temporary summary, and an
  unsaved active-session exit guard.
- Added Phase 4 UI, integration, monitor, tray, exit-guard, and no-persistence tests.
- Did not add shortcuts, sounds, rotating quotes, session persistence/synchronization, sleep/crash
  recovery, statistics/history, Spotify, packaging, or installation behavior.

## Phase 3

- Added validated focus setup with searchable active categories, temporary intention, duration, and
  session options.
- Added permanent category create, rename, archive, and restore with protected `Other`, coordinated
  SQLite/CSV writes, backups, rollback, and startup consistency checks.
- Added an in-memory focus-session coordinator and an unsaved preview backed by the Phase 2 engine.
- Added Phase 3 domain, persistence, integration, and Qt tests plus acceptance documentation.
- Did not add session/segment persistence, session CSV synchronization, a final focus screen,
  full-screen behavior, shortcuts, sound, quote rotation, statistics, Spotify, or packaging.

## Phase 2

- Added the GUI-independent monotonic timer engine, exact ManualClock tests, immutable snapshots,
  ordered events, validated transitions, pause/resume, early stop, completion, and explicit overtime.
- Added exact ten-second continuity calculations and a thin Qt polling adapter.
- Added a developer-only Start Focus preview that is explicitly not saved.
- Added Phase 2 unit, integration, system-clock-independence, UI, and no-persistence tests and docs.
- Did not add session persistence, CSV synchronization, final focus setup, focus mode, shortcuts,
  sound, statistics, Spotify, packaging, or installation behavior.

## 0.2.0 - 2026-07-16

- Added the Phase 1 PySide6 desktop shell with seven reusable pages and a collapsible sidebar.
- Added five persistent QSS themes, isolated QSettings preferences, geometry/page restoration, and
  system-tray foundations.
- Added read-only validated categories/quotes previews and pytest-qt coverage.
- Preserved all Phase 0 data contracts; no timer, tracking, or synchronization was added.

## 0.1.0 - 2026-07-16

- Added the Phase 0 repository foundation and data contract.
- Added SQLite schema version 1, portable manifest/CSV contracts, validators, and partition naming.
- Added safe bootstrap, inspection utilities, documentation, and automated tests.
- No timer or GUI functionality is included.
