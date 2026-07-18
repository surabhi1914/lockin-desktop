# Modifying the app

Preserve Phase 0 schema/CSV contracts, UTC authority, path separation, and non-destructive writes.
UI code must not write SQL or portable CSV.

## Change categories

Preserve immutable IDs, canonical UUIDs, Unicode name normalization, case-insensitive uniqueness,
the protected deterministic `Other`, archive/restore instead of delete, and exact timestamps. Route
all permanent mutations through `CategoryService`; UI code must not call the repository or portable
store to write. Preserve the stage/transaction/replace/commit sequence, backup behavior, rollback,
recovery marker, and startup consistency check. Add failure-path tests for any change.

## Add a focus setup option

Add the immutable field to `FocusSessionDraft`, validate it in the model, expose it through
`SessionOptionsPanel`, and hand it through `FocusSessionCoordinator` to `TimerConfig` only if it is a
timer concern. QSettings may retain safe defaults, but never intention text or active preview state.
Do not add session persistence as a side effect of a setup option.

## Add a page/sidebar item

Create a content-only QWidget under `app/ui/pages`, then add one `PageDefinition` in
`build_page_registry`. Use a unique stable ID and order. The sidebar and stack derive from that
registry automatically; pages must not call them directly.

## Add a theme

Add a QSS file and typed Theme metadata in `ThemeRegistry.standard`. Reuse shared object names and
dynamic properties, keep colors in QSS, provide visible focus states, and add registry/application
tests. Do not add icon/font/theme packages.

## Add a reusable widget

Keep widgets small and content-neutral under `app/ui/widgets`. Prefer PageHeader, MetricCard,
EmptyState, and IconButton before expanding the design vocabulary.

## Change timer behavior

Keep all timing truth in `app.timer`, expressed as monotonic integer nanoseconds. Never calculate
elapsed duration from `datetime.now()`, `time.time()`, GUI repaint counts, QTimer callback counts, or
repeatedly decrementing a displayed integer. Preserve the injected `Clock` boundary and extend
ManualClock tests before changing state transitions or rounding.

Add a `TimerEventType` and emit its immutable `TimerEvent` from the domain transition that owns the
fact. The Qt adapter may forward events, but it must not invent them. Keep event detail values simple
and serializable, and test once-only emission and strict sequence ordering.

The default polling interval is 150 ms and may be configured when constructing `QtTimerAdapter`.
Changing it affects display smoothness only; it must never affect accounting. Starting or stopping
polling cannot alter engine state.

The continuity grace belongs to each immutable `TimerConfig` and defaults to 10 seconds. Compare
exact nanoseconds with an inclusive threshold. A joined gap is still non-focus time, and changing the
grace must not change total focus or total pause.

Do not add SQL, CSV paths, QSettings, networking, sound, tray, or shortcut responsibilities to the
engine or adapter. Persistent session/recovery orchestration stays in services, and intention must
never be written to SQLite, CSV, QSettings, logs, backups, or recovery markers.

## Change the focus experience

Keep timing and transitions in `TimerEngine`; focus widgets format and display `TimerSnapshot` only.
Keep ritual/controls/cursor/window/overlay flow in `FocusExperienceService` and focused widgets, not
the setup page. Qt timers may schedule animation, polling, and inactivity only; they must not measure
focus duration.

Preserve current-monitor selection order (largest frame intersection, window-handle screen, primary),
prior geometry/maximized restoration, and windowed-primary recovery after monitor removal. Do not add
kiosk mode, always-on-top, global cursor changes, input trapping, or global shortcuts.

## Change focus shortcuts

Add stable actions only through `ShortcutRegistry`, with typed ID, metadata, default, allowed timer
states, and confirmation rule. Keep key parsing/conflicts in `ShortcutValidator`, complete-set device
preference writes in `ShortcutSettingsService`, and Qt objects in `QtShortcutManager`. Never use
`ApplicationShortcut`, native hotkeys, administrator access, or global-hook packages. The dispatcher
must continue to recheck focus/window visibility, minimized/hidden state, modal ownership, editable
focus, enablement, and timer state after every Qt activation. Extend suppression tests for any new
text-editing widget and no-persistence tests for any new action.

Distraction marker changes belong in `DistractionMarkerService`, persistence, and the immutable model.
Preserve the simple no-type/no-note contract and canonical portable mapping.

Quote selection must remain active, validated, local, and snapshot-driven. Hourly rotation uses
cumulative active focus only. Do not add credentials or networking to the focus controller.

All exit paths must share the active-session guard. Intention remains memory-only.

## Change Phase 6 persistence

Keep SQL inside repositories and lifecycle ordering inside `SessionPersistenceService`. Repositories
must not commit; every mutation uses one `UnitOfWork` transaction and preserves the one-open-segment
invariant. Durations come from `TimerSnapshot` monotonic totals, never wall-time subtraction. Add
failure-injection tests for every new transaction.

Do not populate `temporary_intention_text` or bypass portable/recovery validation. When finalized
fields change, update checksum, recovery audit, analytics revision, and the read-only verifier
together. UI buttons and shortcuts must continue to share one persistence-aware action path.
## Extending portable data

Keep mappers pure and deterministic, preserve the immutable header contracts, and update the
validator before adding any writer behavior. A ledger mutation must happen only after atomic
replacement and installed-row verification. Never add implicit Git operations. Keep export and
staged import/reconstruction as separate explicit boundaries.

## Extending portable import

Keep validation read-only and complete before any database write. Add contract validation before
mapping, mapping before conflict policy, and conflict tests before promotion logic. Never mutate the
live database directly: use staging, run SQLite integrity plus domain checks, create/verify a backup,
then atomically replace. Duplicate and conflict classifications must be deterministic; an explicitly
skipped parent must suppress its dependents. Preserve source device IDs and keep new local device
registration outside historical ledger reconstruction. Do not add implicit Git or cloud work.

## Modify production packaging

Preserve source/frozen resource separation, installed writable paths, deterministic sanitized starter
resources, `--health-check-output`, explicit PyInstaller data, per-user uninstall retention, and the
final privacy checker. Never build from live portable history or commit build/release output.
