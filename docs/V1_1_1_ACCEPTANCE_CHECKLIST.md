# LockIn v1.1.1 acceptance checklist

- [x] Original missing manual record and live runtime database paths diagnosed read-only.
- [x] Unrelated unresolved sessions no longer cause false overlap warnings.
- [x] Adjacent intervals use half-open UTC semantics and do not overlap.
- [x] Genuine overlaps identify date, time, category, source, status, and session ID.
- [x] Start-time changes immediately update validation and preview.
- [x] Local commit and History refresh occur before portable synchronization.
- [x] Manual rows appear immediately, survive restart, and update dashboard/statistics.
- [x] Portable synchronization and import compatibility remain healthy.
- [x] No process popup, unintended top-level widget, or transient-window flicker was observed.
- [x] Full tests, coverage, Ruff, formatting, mypy, integrity, sync, and analytics gates pass.
- [x] Packaged application, installer upgrade, privacy scan, and candidate artifact hashes are
      verified.
- [ ] Private push, tag, final artifact hashes, and GitHub Release are verified.
