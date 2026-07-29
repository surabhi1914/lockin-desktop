# LockIn v1.1.0

LockIn v1.1.0 adds one focused feature: finalized manual logging for a focus session completed in the
past but not tracked by the timer.

## Add Past Session

Open **Session History** and select **+ Add Past Session**. Enter a local date and start time, actual
focus duration, category, and optionally a different planned duration. The live preview shows the
derived end and whether the historical result is completed, completed with overtime, or stopped
early.

Manual records are clearly labelled **Manual** in History. Source filters are available in History
and Statistics. Manual focus counts toward dashboard goals, streaks, heatmaps, personal records,
category/device totals, planned completion, overtime, and stopped-early analysis.

## Safety and data compatibility

Schema v5 adds explicit session provenance and manual creation metadata. A manual save is one SQLite
transaction containing a finalized aggregate and one or two closed focus segments. It does not
simulate the timer and creates no temporary intention, pause, distraction, heartbeat, sleep,
runtime, or recovery record.

Date/time validation is IANA-timezone aware. Nonexistent spring-forward times are rejected and
ambiguous fall-back times require an explicit first/second occurrence. Exact duplicates are blocked;
partial or containing overlaps require confirmation; unresolved active/recovery state blocks entry.

Portable data schema v2 carries the new source fields. Existing schema-v1 folders remain readable
and are upgraded atomically with backups. Fresh rebuild and safe merge preserve manual provenance,
segments, checksums, historical devices, and categories. Older rows with no reliable source are
classified as Imported, never guessed as Manual.

Editing and deletion are intentionally unavailable in v1.1.0. The existing portable format has no
safe deletion tombstone, so a local-only delete could return during re-import.

The separately reported completion-sound regression is also corrected: the Start Focus option is
available again, and enabled sessions play the bundled local sound when planned focus completes.

## Installation and privacy

Install `LockIn-Setup-v1.1.0.exe` over v1.0.0 or v1.0.1. The per-user upgrade preserves runtime
SQLite data, portable CSV history, settings, logs, backups, and diagnostics. The portable ZIP must
be fully extracted before running `LockIn\LockIn.exe`.

LockIn remains local-first with no telemetry, cloud account, Spotify integration, global keyboard
hook, background service, or automatic update. Release artifacts contain sanitized starter
resources and no runtime database, logs, backups, intentions, personal history, portable data, or
credentials.

This unsigned Windows 10/11 x64 release may trigger SmartScreen. Verify downloads against
`SHA256SUMS.txt`. The v1.0.0 and v1.0.1 tags, Releases, and assets remain unchanged.
