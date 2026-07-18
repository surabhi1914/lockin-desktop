# Phase 3 acceptance checklist

- [x] Every Phase 0, Phase 1, and Phase 2 entry gate and desktop launch passed before editing.
- [x] No dependency was added; every command uses the workspace `.venv`.
- [x] Immutable category and focus-draft models enforce the Phase 3 contracts.
- [x] Category repository methods are parameterized and never hard-delete.
- [x] Portable categories use exact validation, stable sorting, backups, staging, and atomic replace.
- [x] Category service coordinates SQLite/CSV, rollback, recovery marker, and startup consistency.
- [x] Searchable active selection and explicit inline creation are implemented.
- [x] Rename, archive, restore, duplicate handling, and protected `Other` are implemented.
- [x] Duration allows 1 minute through 167 hours 59 minutes and defaults to 50 minutes.
- [x] Intention is temporary, limited to 240 characters, and is never persisted.
- [x] Safe session-option defaults are stored without adding later-phase effects.
- [x] The in-memory coordinator creates one fresh Phase 2 engine/adapter and clears its draft.
- [x] The setup preview supports pause/resume/stop/completion/overtime and is visibly unsaved.
- [x] Session, segment, and distraction rows/files remain unchanged after preview use.
- [x] Category mutations are the only Phase 3 portable-data writes and survive restart.
- [x] Navigation, themes, tray, bootstrap, validation, and Phase 2 timer regressions pass.
- [x] All tests, at least 90% coverage, Ruff, formatting, and strict mypy pass.
- [x] Phase 3 documentation and manual scenarios A-H are complete.
- [x] No final focus screen, full-screen behavior, shortcuts, sounds, quote rotation, session
  persistence/synchronization, statistics, Spotify, packaging, installer, commit, or push was added.
