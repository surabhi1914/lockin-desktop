# Phase 2 acceptance checklist

- [x] Phase 0 and Phase 1 entry tests, Ruff, formatting, mypy, and desktop launch pass.
- [x] No dependency was added; all commands use the existing workspace `.venv`.
- [x] Immutable timer configuration validates duration, seven-day cap, grace, bools, and floats.
- [x] Production monotonic and deterministic manual clocks use integer nanoseconds.
- [x] Countdown remains accurate under sub-second, irregular, repeated, and delayed polling.
- [x] Pause, resume, early stop, completion, and explicit overtime transitions are implemented.
- [x] The inclusive default ten-second continuity grace uses exact nanoseconds.
- [x] Short pauses join blocks; long pauses split blocks and emit continuity events.
- [x] Completion-wait gaps join or split by the same grace without becoming focus.
- [x] Immutable snapshots/events, once-only events, versions, and test-visible invariants pass.
- [x] The thin Qt adapter polls only, emits on change, and disposes cleanly.
- [x] Start Focus is clearly labeled as a developer preview that is not saved.
- [x] Timer demo tests prove session, segment, and distraction SQLite counts do not change.
- [x] Timer demo tests prove portable partition lists and existing file hashes do not change.
- [x] Phase 1 theme, navigation, tray, read-only preview, and startup regressions pass.
- [x] Tests, at least 90% coverage, Ruff, formatting, and strict mypy pass.
- [x] README, focus guide, architecture, testing, modification, roadmap, and decisions are updated.
- [x] No commit or push was performed.

Manual scenarios A–F and the final quality commands are recorded in the Phase 2 implementation
report. Phase 3 is explicitly out of scope.
