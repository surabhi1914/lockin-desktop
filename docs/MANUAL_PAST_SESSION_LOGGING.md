# Manual past-session logging

LockIn 1.1.1 can record focus that occurred in the past without pretending the timer tracked it.
Choose **Session History → + Add Past Session**, then provide the local date, start time, actual
focus duration, category, and optional different planned duration.

Dates may be today or earlier. Durations range from one minute through 24 hours and may cross at
most one local midnight. LockIn resolves the start using the configured IANA timezone. A
spring-forward time that did not exist is rejected; a repeated fall-back time requires an explicit
first/second occurrence. Duration is applied on the UTC timeline to derive the end safely.

The preview shows date, start/end, category, actual/planned focus, and the derived result. Equal
durations are completed; actual above plan is completed with overtime; actual below plan is stopped
early. Exact duplicates are blocked. Partial or containing overlaps require explicit confirmation,
and unresolved active/recovery state blocks creation.

Saving creates one finalized SQLite session and one planned focus segment, plus one overtime segment
when needed. It creates no timer run, temporary intention, pause, distraction, heartbeat, sleep, or
recovery record. The row is labelled **Manual** in History and participates in goals and analytics.

Portable session CSV schema v2 preserves manual provenance and timestamps. Synchronization runs
after the SQLite commit; if it fails, the local record remains safe and reports pending sync. Fresh
rebuild and merge preserve the Manual badge, segments, checksum, and device/category snapshots.
Legacy schema-v1 rows without provenance are classified as Imported, never guessed as Manual.

Editing and deletion are not available in v1.1.1. The portable contract has no deletion tombstone,
and shipping a local-only operation could cause a deleted record to return after import.

Manual logging stores only the selected historical timing/category and required integrity metadata.
It adds no notes or intentions.
