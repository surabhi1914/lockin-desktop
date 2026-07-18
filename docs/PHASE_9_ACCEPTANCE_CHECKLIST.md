# Phase 9 acceptance checklist

- [x] Native Windows suspend/resume events use an isolated, testable Qt event-filter abstraction.
- [x] Suspend synchronizes the monotonic timer and persists a continuity-breaking system-sleep pause.
- [x] Resume remains an explicit Resume, Stop-and-Save, or stay-paused decision; no auto-resume.
- [x] Crash, paused, completed, overtime, sleep, and structure-warning analyses are typed.
- [x] Confirmed focus ends at the last trustworthy heartbeat/lifecycle boundary.
- [x] Unknown restart gaps are displayed and never counted as focus.
- [x] Save and discard are transactional, audited, idempotent, and remove the runtime block.
- [x] Recovered records recompute aggregates/checksum and use Phase 7 portable synchronization.
- [x] Recovery audit contains no temporary intention; runtime intention remains `NULL`.
- [x] Disposable fixture creation and privacy-safe read-only inspection scripts work.
- [x] Phase 0-8 regressions, integrity, portable sync, Ruff, formatting, and mypy pass.
- [x] No Git operation, global hook, service, polling loop, or automatic focus-time guess was added.
