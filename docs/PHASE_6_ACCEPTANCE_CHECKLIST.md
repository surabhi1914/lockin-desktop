# Phase 6 acceptance checklist

## Automated gates

- [x] All Phase 0–5 entry-gate commands passed before editing.
- [x] Full pytest suite passes.
- [x] Required coverage command passes at 90% or higher.
- [x] Ruff lint and formatting checks pass.
- [x] mypy passes for `app` and `scripts`.
- [x] Read-only database integrity and inspection scripts pass.

## Persistence contract

- [x] Migration v2 upgrades v1/fresh databases transactionally without portable schema changes.
- [x] Stable device identity is reused and missing device rows are restored.
- [x] Start atomically creates session, planned-focus segment, and intention-free runtime row.
- [x] Pause/resume and ten-second continuity classifications reconcile exact segment totals.
- [x] Planned completion has no open segment; overtime is explicit and separately totaled.
- [x] Distractions commit with session/segment/category/device context and duplicate safety.
- [x] Finalization atomically writes aggregates/checksum and deletes runtime state.
- [x] Heartbeat writes only newer versions and never mutates segments.
- [x] Unfinished detection is read-only and blocks new focus without recovery actions.
- [x] Final summary and latest-20 recent-session view load from SQLite.

## Manual scenarios A–K

- [x] A — complete a short session, restart, and verify summary/history.
- [x] B — stop early, restart, and verify values/status.
- [x] C — verify short- and long-pause classification/continuity.
- [x] D — verify planned plus overtime separation and total.
- [x] E — mark three distractions and verify after restart.
- [x] F — minimize/hide, restore, finish, and verify persistence.
- [x] G — End Session and Exit stores `app_close`.
- [x] H — injected failure leaves no partial rows or unsaved continuation.
- [x] I — unfinished runtime state warns, blocks start, and is not mutated.
- [x] J — a unique intention is absent from SQLite, QSettings, CSV, and logs.
- [x] K — portable CSV tree is unchanged by session lifecycle actions.
