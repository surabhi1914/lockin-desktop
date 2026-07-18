# Phase 7 acceptance checklist

## Scope

- [x] SQLite remains operational truth; portable CSV contains finalized history only.
- [x] Devices, sessions, segments, and distractions use exact Phase 0 headers.
- [x] Open/unresolved sessions and open segments are excluded.
- [x] CSV import, reconstruction, conflict resolution, and all later features are absent.

## Mapping and partitioning

- [x] Canonical UUID, UTC/local timestamp, integer-second, optional, and boolean encodings.
- [x] Session checksum matches the finalized SQLite aggregate.
- [x] Segment/distraction checksums are stable across export timestamps.
- [x] Local-midnight splits retain stable source/portable IDs and exact duration sums.
- [x] Base, `_part002`, and later partitions honor encoded incoming-row size.
- [x] Invalid existing partitions block mutation; single oversized rows produce a warning.

## Write and ledger safety

- [x] Same-directory staging, flush/fsync, validation, bounded lock retry, and atomic replace.
- [x] Populated replacements create runtime backups and clean temporary files.
- [x] Existing files survive staging/validation/lock failure.
- [x] Ledger entries are written only after installed-row verification.
- [x] Same-checksum rows skip; missing ledger entries reconcile; stale rows repair.
- [x] Duplicate IDs and wrong-month/ledger-path conflicts block unsafe writes.
- [x] Manifest sync timestamps update only after a fully successful run.

## Lifecycle and verification

- [x] Finalization commits locally before automatic sync and preserves local success on failure.
- [x] Summary shows synced or pending wording; Settings provides manual retry and status.
- [x] Startup and live day rollover verify the previous local day without timer mutation.
- [x] Verification checks checksums, duplicates, parents, split aggregates, ledger paths, and gaps.
- [x] Daily verification produces no daily/weekly/monthly summary CSV.

## Commands and manual acceptance

- [x] Pytest and the 90% coverage gate pass.
- [x] Ruff check/format and mypy pass.
- [x] Session integrity and portable verification scripts pass in isolated acceptance data.
- [x] Manual scenarios A–L completed in isolated roots.
- [x] No global install, Git command, commit, or push was performed.

Phase 8 is intentionally not started.
