# Move to a new device

## Move to a new device with Phase 8

1. On the old device, finish the active session, choose **Settings > Sync now**, and run
   `scripts\verify_portable_sync.py` from the project virtual environment.
2. Close LockIn. Manually copy or privately clone/pull the complete repository containing
   `portable_data`; LockIn does not run Git commands.
3. Install the developer environment by following [08_DEVELOPMENT_SETUP.md](08_DEVELOPMENT_SETUP.md).
4. Launch LockIn. At the new-device prompt choose **Use existing portable data**, then select either
   the `portable_data` folder or its repository parent.
5. Review validation counts and warnings. Proceed only when readiness is safe. If conflicts are
   listed, abort or export the report; do not assume one side wins.
6. Approve reconstruction. LockIn builds and verifies a staging database, promotes it, preserves
   historical device IDs, and registers a different local device ID.
7. Open **History** and confirm recent sessions. Complete one small test session and sync it; the new
   row should use the new device while old history remains unchanged.

For a non-empty installation, use **Settings > Import Portable History**. LockIn backs up the live
database and stages the merge. Exact duplicates are skipped. Import is refused while a focus session
or unresolved runtime state exists. Portable files stay read-only throughout.

This workflow assumes one device is authoritative at a time. Cloud sync and concurrent multi-device
conflict resolution are future work.
