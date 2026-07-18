# Phase 4 acceptance checklist

- [x] Every Phase 0-3 entry test, quality gate, and native GUI launch passed before implementation.
- [x] No dependency was added and all commands use the workspace `.venv`.
- [x] Setup enters one dedicated black focus view in the existing main window.
- [x] Ritual shows breath, temporary intention, 3-2-1, fade, Cancel, and delayed engine start.
- [x] Disabled ritual starts immediately; shutdown/cancel clears intention.
- [x] Timer/category/state/static quote are responsive and snapshot-driven.
- [x] Controls and cursor reveal/hide safely with injectable inactivity timing.
- [x] Pause/resume/stop/minimize/full-screen/quote/finish/overtime actions obey engine state.
- [x] Full screen uses current-window screen selection and restores geometry/state.
- [x] Monitor removal recovers windowed on primary without engine/window duplication.
- [x] Minimize/hide/loss of focus never pauses or resets focus.
- [x] Tray status reflects running, paused, completed, and overtime without timer actions.
- [x] Completion overlay appears once, plays no sound, and waiting adds no focus.
- [x] Overtime is explicit and preserves quote/window mode.
- [x] Stop confirmation and temporary summary contain the required snapshot-derived values.
- [x] Window Close and tray Exit share the unsaved active-session guard.
- [x] Return restores shell/window state, clears intention, and disposes engine/adapter.
- [x] DB counts/history partitions/reference CSV hashes remain unchanged during focus use.
- [x] Phase 0-4 tests, 90% coverage, Ruff, formatting, mypy, docs, and manual scenarios pass.
- [x] No shortcuts, sound, hourly quote rotation, persistence/synchronization, sleep/crash recovery,
  statistics/history, Spotify, packaging, installer, commit, or push was added.
