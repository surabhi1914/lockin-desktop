# Architecture

## Local-first foundation

LockIn's operational state stays on the user's device. Phase 0 has no server, account, or network
requirement. UTC timestamps are authoritative; IANA timezone names, offsets, and local dates retain
the context needed for reporting and midnight partitioning.

## Two storage roles

Runtime SQLite at `.local_data/runtime/lockin.sqlite3` is the transactional operational store. It
supports integrity constraints, recovery state, relationships, and future timer writes. The binary
database, WAL, and journal files are ignored because they are machine-local, frequently changing,
and unsuitable for Git merging.

Portable UTF-8 CSV under `portable_data/` is the future human-inspectable history and reference-data
format. Root reference files are unpartitioned; sessions, segments, and distractions use local
year/month partitions with 10-MiB rotation. Phase 0 defines validation and safe partition creation,
but deliberately does not implement database-to-CSV synchronization.

## Phase 1 desktop shell

`app.application` composes QApplication, Phase 0 startup validation, SQLite, UI settings, themes,
portable previews, the page registry, main window, tray service, and one shutdown coordinator. The
factory returns a testable context without entering the event loop. `main.py` preserves Phase 0 flags
and otherwise starts the GUI.

The standard `QMainWindow` contains a persistent Sidebar and `QStackedWidget`. A typed page registry
is the sole source of stable IDs, titles, descriptions, order, symbols, and factories. Each of the
seven pages is created once; pages contain content only and never manipulate navigation.

QSettings stores only theme, geometry/state, sidebar state/startup behavior, tray/close preferences,
and last page. Theme metadata is typed and QSS files own most colors. The tray service is optional:
the app closes normally when Windows reports no tray. One coordinator saves UI state, closes SQLite,
disposes the tray icon, and ensures explicit Exit terminates the process.

`PortablePreviewService` validates Phase 0 CSV contracts before returning immutable read-only
category/quote projections. UI classes contain no SQL and never mutate portable data.

## Phase 2 timer domain

`app.timer` is a GUI-independent, single-thread-owned domain layer. `TimerEngine` accepts immutable
`TimerConfig` and an injected `Clock`; production uses `time.monotonic_ns()` and authoritative tests
use an exact `ManualClock`. The engine never sleeps, starts threads, reads wall time, performs I/O,
or infers elapsed time from UI refresh counts.

The state machine owns planned focus, overtime, pauses, wall elapsed time, exact focus/pause
intervals, validated transitions, and ordered immutable events. Immutable snapshots expose exact
nanoseconds and rounded display seconds. Planned focus is capped at its configured duration; delayed
polling after completion becomes a non-focus wait and overtime begins only through an explicit
transition.

`continuous_blocks` is a pure calculator. Adjacent focus intervals separated by a gap at or below
the grace threshold are analytically joined without adding that gap to focus duration. Longer gaps
split blocks. Average and even median calculations use integer floor division.

`QtTimerAdapter` uses a GUI-thread `QTimer` only to poll snapshots. It emits on snapshot versions and
domain transitions but owns no timing truth. `TimerDemoService` composes a disposable engine and
adapter for the Start Focus developer preview. Neither component receives the SQLite connection,
portable paths, QSettings, tray, or synchronization services, so the persistence boundary is
structural as well as tested.

## Phase 3 category and setup layers

`CategoryRepository` owns parameterized SQLite access, `CategoryPortableStore` owns strict CSV
validation/staging/atomic replacement, and `CategoryService` owns validation plus the cross-store
operation. A mutation stages CSV, starts an immediate SQLite transaction, updates SQLite, replaces
CSV, then commits. Failure rolls back and restores when necessary; an unrecoverable restoration
creates a runtime recovery marker and blocks mutation. Startup imports the Phase 0 categories into
an empty database once, then requires exact field consistency.

`FocusSessionDraft` is an immutable, validated setup value. `FocusSessionCoordinator` creates a fresh
Phase 2 engine and thin Qt adapter for one active preview at a time. It holds the draft and intention
in memory and clears them on reset/shutdown. The coordinator is intentionally not given session
repositories or history CSV paths. The setup page owns presentation and safe-default QSettings only.

## Phase 4 focus experience

`FocusExperienceService` coordinates the visual lifecycle while `TimerEngine` remains the only timing
authority. `FocusSessionCoordinator.prepare` retains a validated draft/category without creating an
engine. The non-blocking ritual runs through Qt timers/animation; after its `1`/fade boundary the black
canvas activates and `start_timer` creates and starts the engine. All displayed values and tray status
come from immutable snapshots, never callback counts.

`FocusExperience` is one widget installed beside the normal shell in the existing main-window root
stack. Entering focus hides shell/sidebar chrome without creating another window. Its child views own
ritual, black canvas, controls, completion, and temporary summary presentation. The controller owns
flow, explicit overtime, cleanup, close guarding, and shell restoration.

`FocusWindowService` selects the QScreen with the largest intersection with the current main-window
frame, then falls back to the window-handle screen and primary screen. It saves/restores geometry and
normal/maximized state. Monitor removal exits full screen and recovers windowed on the current primary
screen; it never resets the coordinator or creates a second window. No kiosk/always-on-top/input lock
is used.

`FocusQuoteService` selects one active record from validated local `quotes.csv` at session start.
Selection is injectable and read-only. `TrayService` exposes presentation-only status; hide/minimize
never pauses polling or the monotonic engine. The active-session exit guard is shared by window Close
and tray Exit.

## Phase 5 local shortcut layer

`app.shortcuts` owns the stable eight-action registry, immutable bindings, portable `QKeySequence`
normalization, conflict/safety validation, typed dispatch outcomes, editable-widget suppression, and
the `QtShortcutManager`. The manager parents `QShortcut` objects to the focus widget using
`WidgetWithChildrenShortcut`; it activates at timer start, refreshes as one complete set, and disposes
at summary/return/exit. The dispatcher rechecks application/window focus, visibility/minimized state,
focus-view ownership, modal/text context, enablement, and allowed timer state before calling existing
focus methods.

`ShortcutSettingsService` is the sole persistence boundary for bindings. It validates a full staged
set before QSettings writes, rolls back a failed save, recovers corrupt conflicts to safe defaults,
and emits refreshes. It has no SQLite or portable path. `DistractionMarkerService` owns immutable raw
markers for only the active session; summary projection consumes the count, and disposal clears them.

## Layer responsibilities

- `app.core`: dependency-light contracts for paths, aware time, identifiers, and checksums.
- `app.database`: configured SQLite connections and forward-only schema migrations.
- `app.portability`: manifest, immutable CSV headers, validation, partition selection, and atomic
  category portable storage.
- `app.bootstrap`: orchestration that validates before writing and remains idempotent.
- `app.timer`: clocks, state machine, exact accounting, events, snapshots, continuity, and Qt polling.
- `app.shortcuts`: local action metadata, binding validation, text suppression, dispatch, and Qt
  shortcut object lifecycle.
- `scripts`: thin operational entry points; business rules remain in `app`.
- `app.ui`: Phase 1 shell, reusable widgets, page content, and navigation presentation.
- `app.themes`: theme metadata, registry, QSS loading, fallback, and application.
- `app.services`: category coordination, in-memory focus/window/quote/distraction coordination,
  typed settings, tray behavior, and validated portable previews.
- `app.models`: immutable category and focus-session-draft values; timer models remain in their
  dependency-light domain package.

`runtime_session_state.temporary_intention_text` is recovery-only. A future timer must delete it on
finalization, and portability code must never export it.

## Future boundaries

Later persistence must use a separate session-lifecycle service that owns transactions and history
CSV synchronization, consuming timer events without placing storage inside `TimerEngine`. Optional
now-playing remains isolated behind
`NowPlayingService`; there is still no Spotify SDK, credential, network, or song storage.

## Phase 6 persistence boundary

`SessionPersistenceService` is the only timer-lifecycle write facade. It composes repositories under
`UnitOfWork`, maps snapshots to SQLite records, serializes actions, and returns typed failures.
`TimerEngine` has no storage or wall-clock dependency. Integer segment seconds are cumulative
monotonic differences, so final segment sums equal aggregates across sub-second boundaries.

`DeviceIdentityService` keeps one UUID in local QSettings. `HeartbeatService` performs version-aware
five-second runtime updates. `UnfinishedDetectorService` is read-only and blocks new sessions.
`SessionAggregateService` loads summaries/recent rows; the History UI issues no SQL.
## Phase 7 synchronization boundary

Pure mappers convert finalized SQLite models to canonical strings and stable checksums. The sync
service selects monthly/size partitions, validates existing data, performs atomic replacements,
then updates the local ledger only after the installed row is verified. The verifier separately
checks duplicates, references, checksums, split-duration aggregates, ledger paths, and pending
eligible records. The coordinator owns automatic post-session, manual, startup, and day-rollover
operations without changing timer state.

## Phase 8 import boundary

The importer is a validation-first pipeline: folder resolution, immutable CSV scan, manifest/header/
checksum and relationship validation, logical-segment reconstruction, database comparison, staging,
integrity verification, backup, and atomic promotion. Fresh mode starts from migrations; merge mode
starts from a SQLite backup snapshot. Conflict detection distinguishes exact identity from same-ID
content conflicts and semantic category/goal conflicts. Explicit skips also skip dependent rows.
Historical device rows are data; the newly generated local device identity is runtime ownership.
The GUI is a thin selector/preview/conflict/result adapter over the same service used by the CLI.

## Phase 9 recovery boundary

`RecoveryAnalyzer` reads persisted runtime, session, segment, and audit state without mutating the
timer. `RecoveryService` owns transactional save/discard reconciliation and invokes the existing
portable synchronization boundary only after local commit. The Windows native event filter emits a
small platform-neutral power event into `SleepDetector`; focus orchestration synchronizes the
monotonic engine, persists a `system_sleep` pause, and never auto-resumes. The earliest confirmed
heartbeat/lifecycle boundary is authoritative, while restart time after it remains explicitly
unknown and excluded from focus.

## Phase 11 dashboard boundary

`DailyGoalService` splits an effective range instead of overwriting history and coordinates the
SQLite change with a validated atomic `daily_goals.csv` replacement. Database triggers enforce
non-overlap and advance a shared analytics revision. `DashboardService` owns the single read-only
query, local-midnight allocation, continuity grouping, comparisons, records, streak, deterministic
motivation, and revision-aware cache. `HomePage` only formats the returned model.

## Phase 12 analytics boundary

Statistics and history live under `app.analytics` and only read canonical persisted records. UI
pages render typed results and never derive business metrics. An `analytics_revision` trigger
counter makes cache invalidation deterministic. Qt-native charts consume the same result model.
Explicit statistics export is separate from portable raw synchronization.

## Phase 13 production boundary

`ResourceLocator` hides source versus PyInstaller `_MEIPASS` resolution and returns immutable files
only. `PathConfig` selects repository-local development roots or installed Local AppData/Documents
roots; no writable path derives from the executable directory. The health command validates Qt,
resources, paths, SQLite migrations, and sanitized portable initialization without entering the GUI
event loop. PyInstaller includes an explicit resource set generated independently of live history.
# LockIn 1.1 manual-entry boundary

`ManualSessionService` resolves a timezone-aware command, delegates overlap assessment to
`SessionOverlapService`, and writes the session aggregate plus focus-only segments inside one
`BEGIN IMMEDIATE` unit of work. The service calls portable synchronization only after commit, so
sync failure leaves a valid local record marked pending. Existing analytics revision triggers make
dashboard, statistics, and History reads observe the new record without a second source of truth.
The UI is a parented modal dialog and does not invoke timer, recovery, power, process, or shell APIs.
