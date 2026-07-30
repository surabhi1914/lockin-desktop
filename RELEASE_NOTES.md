# LockIn v1.1.1

LockIn v1.1.1 is a focused corrective release for manual past-session logging.

## Fixed

- Manual sessions are committed locally and revealed in Session History before portable
  synchronization runs.
- Saving clears incompatible History filters and selects the newly added Manual row.
- Changing the past-session start time now immediately revalidates the preview and Save button.
- Unresolved timer/recovery state blocks a manual entry only when its confirmed UTC interval
  actually intersects the proposed interval.
- Adjacent half-open intervals no longer produce overlap warnings.
- Overlap warnings identify each conflicting date, time, category, source, status, and shortened
  session ID.
- History count and row queries now use identical predicates and tolerate absent optional device
  labels.
- Disabled-by-default manual-session tracing and a read-only diagnostic command report save stages
  and canonical database paths without logging temporary intentions.

## Data safety and compatibility

There is no database or portable-schema migration in v1.1.1. Existing v1.1.0 SQLite databases,
portable CSV data, settings, backups, logs, and personal history remain compatible. A failed
portable sync never removes the committed local manual session.

Install `LockIn-Setup-v1.1.1.exe` over v1.1.0. The per-user installer preserves application data
under Local AppData and portable history in the user-selected portable folder.

The release contains only:

- `LockIn-Setup-v1.1.1.exe`
- `LockIn-v1.1.1-portable.zip`
- `SHA256SUMS.txt`

The binaries are unsigned and may trigger Windows SmartScreen. Verify both downloads against
`SHA256SUMS.txt` from the private GitHub Release.
