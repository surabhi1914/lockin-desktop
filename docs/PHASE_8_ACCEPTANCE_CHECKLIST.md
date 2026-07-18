# Phase 8 acceptance checklist

- [x] Phase 0–7 tests, database integrity, portable verification, Ruff, formatting, and mypy pass.
- [x] Folder selection accepts `portable_data` or its repository parent and persists only success.
- [x] Manifest version, exact headers, partitions, fields, relationships, formulas, and checksums are
  validated before staging; verify-only writes nothing.
- [x] Fresh reconstruction and existing-database merge use staging databases.
- [x] Existing SQLite is backed up and verified before atomic replacement.
- [x] Exact duplicates skip; same-ID and semantic conflicts are reported without silent overwrite.
- [x] Explicit skips also skip dependent records.
- [x] Historical devices remain historical and a new installation gets a new local device UUID.
- [x] Categories, goals, quotes, sessions, midnight segments, distractions, ledger, and import
  metadata reconstruct correctly.
- [x] Reimport is idempotent; active and unfinished sessions block import.
- [x] Portable source hashes are unchanged after verify, fresh, merge, and injected failure.
- [x] Phase 7 can export a new-device session after import without duplicating old history.
- [x] Automated tests meet 90% coverage and all static-quality gates pass.
- [x] Move/new-device documentation is complete and uses only manual Git transfer.
- [x] No automatic conflict overwrite, Git/cloud sync, concurrent merge resolution, recovery action,
  sleep detection, statistics, sounds, hourly quotes, Spotify, packaging, installer, commit, or push.
