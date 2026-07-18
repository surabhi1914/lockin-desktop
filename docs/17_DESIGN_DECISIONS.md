# Design decisions

1. **SQLite is the operational store.** Transactions, constraints, foreign keys, and recovery state
   belong in a local database.
2. **Partitioned CSV is portable history.** It is inspectable, diffable, and suitable for private
   Git backup once synchronization is implemented.
3. **Runtime data is excluded from Git.** Database, WAL, journals, logs, and local backups are
   device-local artifacts.
4. **Portable data is committed only to a private repository.** It may contain personal focus
   history; users must review it before any Git operation.
5. **Rotation is monthly plus 10 MiB.** Local month paths aid navigation; size parts keep files
   manageable. The first part has no suffix, then `_part002`, `_part003`, and so on.
6. **UTC is authoritative.** Aware UTC timestamps preserve ordering and elapsed duration.
7. **Local context is retained.** Local date, IANA timezone, and offset support meaningful reports,
   including daylight-saving changes.
8. **Session intentions are temporary.** They exist only in runtime recovery state, are deleted at
   finalization, and are never portable.
9. **Categories are permanent analytical dimensions.** Sessions retain category identifiers and
   name snapshots; starter identifiers are deterministic UUID5 values.
10. **Phase 1 uses a standard QMainWindow.** Native title bars and conventional window behavior are
    preferred over frameless, always-on-top, or full-screen shells.
11. **Spotify is future work behind a service interface.** The provider-neutral protocol prevents a
    future integration from leaking credentials, networking, or dependencies into core logic.
12. **Page IDs are stable and centralized.** One typed registry drives order, labels, factories,
    sidebar buttons, and navigation validation; pages are constructed once.
13. **QSettings stores UI preferences only.** History, intentions, categories, quotes, goals, and
    credentials remain outside it. Tests use isolated INI stores.
14. **Tray support degrades safely.** Close-to-tray operates only when configured and available;
    otherwise close exits. Explicit Exit always terminates.
15. **No fake statistics.** Placeholders use `—`, empty states, and disabled controls until real data
    and calculation services exist.
16. **The timer remains separate from the shell and persistence.** Phase 2 places timing truth in a
    GUI-independent domain. The Qt preview creates no sessions or portable data.
17. **Elapsed time uses monotonic integer nanoseconds.** This avoids wall-clock corrections, GUI
    jitter, float drift, and loss of sub-second remainders. Elapsed displays floor; remaining planned
    seconds ceil.
18. **Overtime is explicit.** Planned focus caps at the requested duration. Polling overshoot and
    completion wait are non-focus gaps; only `start_overtime` begins overtime.
19. **Every pause is non-focus time.** Pause time accumulates exactly even when the pause is short
    enough to preserve analytical continuity.
20. **Continuity grace is inclusive.** A gap at or below 10 seconds joins adjacent focus blocks; a
    longer gap splits them. Joined gaps never inflate focus duration.
21. **The timer is single-thread owned.** The future GUI owns it on the Qt GUI thread. There are no
    locks, worker threads, asyncio tasks, or sleeping schedulers in the domain.
22. **Qt polling owns no timing truth.** QTimer controls update cadence only; snapshot versions avoid
    redundant UI emissions without changing accounting.
23. **Phase 2 timer use is non-persistent.** The engine, adapter, and demo receive no database or
    portable-data dependencies. Automated tests prove row counts, partition lists, and portable
    hashes remain unchanged.
24. **Categories are coordinated permanent reference data.** Phase 3 stages validated CSV, updates
    SQLite transactionally, atomically replaces CSV, and rolls back or records recovery needs.
25. **Categories are never hard-deleted.** Archive/restore preserves identifiers for future session
    analysis; names remain normalized and unique across active and archived records.
26. **`Other` is protected.** Its deterministic starter identifier provides a stable fallback and it
    cannot be renamed or archived.
27. **Intentions are temporary by construction.** The draft/coordinator hold them only in memory;
    QSettings, SQLite, CSV, backups, logs, and recovery markers never receive them.
28. **The Phase 3 preview remains unsaved.** It validates the real setup-to-engine handoff without
    pretending that a final focus screen or session lifecycle exists.
29. **Focus presentation is a separate controller/view stack.** Phase 4 replaces shell chrome inside
    the existing main window; it does not create another process or duplicate timer calculations.
30. **Ritual time is not focus.** A prepared draft has no engine. The black canvas activates at the
    ritual boundary, then the monotonic engine starts exactly once.
31. **The focus canvas is always black.** Application themes cannot override its background or
    responsive timer typography.
32. **Full screen follows the current window.** Largest frame intersection chooses the monitor; there
    is no selector, kiosk mode, always-on-top, or input suppression.
33. **Monitor removal recovers windowed on primary.** This favors predictable on-screen recovery while
    preserving the same engine and focus widget.
34. **Minimize/hide is presentation-only.** Monotonic timing and polling continue; tray status is a
    snapshot projection and offers no timer actions.
35. **Quotes are static and local per session.** One active validated quote may be selected; hourly
    rotation and network providers are later work.
36. **Completion and overtime remain explicit.** Completion appears once, waiting is non-focus, and
    only the existing engine transition starts overtime.
37. **Active unsaved sessions are guarded.** Close and tray Exit share Keep, Minimize when available,
    and End-and-Exit choices so ritual/focus is never silently discarded.
38. **Phase 4 summaries are temporary.** They are snapshot-derived, cleared on return/shutdown, and
    create no history, statistics, recovery state, sync record, or CSV.
39. **Focus shortcuts are strictly local.** QShortcut uses the focus widget's child context; every
    activation is rechecked and no application/global/native keyboard hook is installed.
40. **Bindings are device-local preferences.** Portable Qt key text and enablement live in QSettings;
    failed staged sets never partially replace active settings and corrupt conflicts recover safely.
41. **Text entry always wins.** A shared helper blocks focus actions for line/multiline edits, spin
    boxes, editable combos, key-sequence editors, and explicitly marked editing dialogs.
42. **Esc has one narrow meaning.** It exits full screen only and cannot pause, stop, end a session,
    close the application, or act when already windowed.
43. **Stop always confirms.** Ctrl+Shift+S reuses the existing stop decision and a guard prevents
    concurrent confirmations.
44. **Distraction markers are Phase 5 memory only.** Snapshot-derived raw markers have no wall time,
    note, SQL, CSV, sync, or recovery representation; only their count reaches the temporary summary.
45. **SQLite lifecycle writes are transactional.** One unit of work owns each lifecycle mutation;
    repositories never commit independently.
46. **Monotonic time remains duration truth.** Wall time supplies aware timestamps only; cumulative
    remainder allocation makes segment sums equal aggregates.
47. **One open segment is enforced twice.** Service checks and migration v2's partial unique index
    protect the invariant.
48. **Intentions remain memory-only.** Runtime intention storage is always `NULL`.
49. **Completion wait is not a pause.** It retains heartbeat state with no open segment; explicit
    overtime opens focus only after persistence succeeds.
50. **Unfinished detection is non-destructive.** Read-only use/exit is offered and new focus is
    blocked; recovery actions are deferred.
51. **Portable session synchronization is deferred.** CSV headers, partitions, manifest data version,
    sync ledger, and portable session files are unchanged.
## Phase 7 decisions

- SQLite is operational truth; CSV is portable finalized history.
- Monthly-plus-size partitions bound file growth while retaining understandable paths.
- Stable content checksums and a local ledger make synchronization idempotent.
- Existing-file backups and atomic replacement prioritize recoverability.
- Previous-day verification repairs raw history only; it creates no summary CSV.
- Git remains manual, and import/rebuild is deferred to Phase 8.

## Phase 8 decisions

- Portable input is immutable; pre/post hashes prove import did not rewrite it.
- Complete validation precedes staging so malformed or newer contracts cannot partially load.
- Fresh and merge both operate in staging; an existing live database is backed up and promoted only
  after SQLite and domain integrity checks.
- Exact duplicates are skipped; same-ID and semantic conflicts are reported and never silently won.
- Explicit conflict skips propagate to dependent entities to avoid partial histories.
- Historical device identity is preserved, while each new installation receives a separate UUID.
- Ledger reconstruction records imported provenance and excludes the new local device until it
  exports its own records.
- Git/cloud transport, concurrent merge resolution, and recovery actions remain outside Phase 8.

## Phases 9–12 decisions

- Confirmed heartbeat counters are the recovery authority; unknown time is audit-only, never focus.
- System sleep is an explicit long-pause classification and continuity boundary.
- Quote rotation uses cumulative active focus hours, not wall-clock time.
- Completion audio is original, local, optional, and failure-tolerant; settings stay in QSettings.
- Daily goals are effective-dated, so changes never rewrite historical truth.
- Dashboard/statistics share canonical inputs but expose purpose-specific typed results.
- UI charts are Qt-native and render service metrics with honest zero baselines.
- Statistics export is explicit derived output and forbidden inside portable raw data.
- History is read-only, exposes audit/sync evidence, and excludes temporary intention.

## Phase 13 decisions

- Version identity is authoritative in `app/version.py` and propagated to Windows metadata/artifacts.
- Frozen resources are immutable and never double as writable user storage.
- Windows Known Folder lookup supports redirected Documents; uninstall retains every data root.
- Onedir is primary because its resource/plugin layout is inspectable and installer-friendly.
- Release starter data is regenerated deterministically and never sourced from live `portable_data`.
- The original icon is generated from geometry with no downloaded artwork or bundled font.
- Health diagnostics are noninteractive JSON and use explicit temporary overrides during acceptance.
- The installer is per-user, unsigned, service-free, startup-task-free, and upgrade-safe.
- GitHub publication is private, non-force, and restricted to three verified release assets.
