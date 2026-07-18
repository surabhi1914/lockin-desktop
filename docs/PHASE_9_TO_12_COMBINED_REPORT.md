# Phases 9–12 combined acceptance report

## Scope and sequence

Phase 9 added conservative confirmed-time recovery and Windows sleep auto-pause. Phase 10 added
active-focus-hour quotes, atomic local quote management, one original local completion chime, its
QSettings preferences, and unchanged simple distraction markers. Phase 11 added historical daily
goals and the motivational Home dashboard. Phase 12 added canonical analytics, Qt-native charts,
calendar heatmap, advanced read-only history, and explicit statistics export. Each phase passed its
internal gate before work began on the next.

Database migrations advance the schema to version 4 without rewriting old migrations: version 3
adds confirmed runtime counters, sleep metadata, recovery audit storage/indexes; version 4 adds
historical goal constraints, analytics indexes, an analytics revision row, and invalidation triggers.

## Policy proofs

- Recovery clips every result at the last committed heartbeat boundary. Unknown wall-clock gaps are
  stored in the audit and always excluded. Save and discard are transactional; recovery finalization
  uses normal portable synchronization.
- Suspend auto-pauses a running planned or overtime segment and breaks continuity. Resume continues
  the same saved session in a new continuity group; pause, resume, stop, and stay-paused are explicit.
- Quotes advance once per completed 3,600 seconds of planned plus overtime focus. Pause and sleep do
  not advance the index; multi-hour jumps advance each crossed boundary; cycles avoid repeats before
  exhaustion and favorites receive extra selection weight.
- The generated WAV is an original local asset. It plays at most once at planned completion; master
  enable, per-session enable, volume, and preview are local settings. Audio failure never blocks the
  timer.
- Analytics uses persisted canonical fields and segment allocation. Fixed fixtures prove 6,000
  seconds across four included sessions, 600 seconds overtime, 120 seconds sleep pause, and two
  distractions. Discarded history is excluded and intentions are absent from SQLite, portable CSV,
  history details, statistics, diagnostics, and exports.

See [18_ANALYTICS_AND_HISTORY.md](18_ANALYTICS_AND_HISTORY.md) for the complete metric dictionary,
history/filter contract, chart architecture, caching/index strategy, and export distinction.

## Gates and performance

- Phase 9: 355 tests passed; Ruff, format, mypy, integrity, and portable verification passed.
- Phase 10: 360 tests passed; the same full internal gate passed.
- Phase 11: 366 tests passed; the internal gate plus dashboard verification and 10,000-session
  benchmark passed (about 140.65 ms, indexed session/status plan).
- Phase 12/final: 396 tests passed with 90.09% measured coverage; Ruff, formatting, mypy, integrity,
  portable, and analytics checks passed. The fresh five-year benchmark measured 2,485.84 ms for
  analytics and 5.10 ms for history paging with an indexed range plan.

## Manual scenarios A–Z

All scenarios were exercised with isolated or disposable data and inspected in the GUI where visual
behavior applied: A save confirmed crash; B discard/unblock; C suspend auto-pause/break; D explicit
resume/new group; E overtime suspend; F recovery sync/restart; G active-hour quote; H multi-hour
advance; I nonrepeat/favorite selection; J one completion sound; K enable/volume/preview; L simple
distraction marker; M historical goal change; N over-100% progress; O yesterday/week comparison;
P streak; Q longest record; R motivation/empty state; S presets/custom statistics; T midnight/DST;
U category/device/status filters; V block/pause/distraction metrics; W heatmap; X history/details;
Y external atomic statistics export; Z large-data benchmark/query plan.

## Boundaries and platform notes

Native suspend detection is Windows-specific; non-Windows development runs use a safe disabled
adapter. Actual suspend and audio output depend on host drivers, so deterministic adapters cover
those policies in automated acceptance. Destructive reconstruction and benchmark checks use
temporary runtime paths. No Git command or automatic Git operation was used. Spotify, cloud sync,
multi-device concurrent conflict resolution, kiosk/system blocking, global shortcuts, packaging,
and installer work remain outside this scope.
