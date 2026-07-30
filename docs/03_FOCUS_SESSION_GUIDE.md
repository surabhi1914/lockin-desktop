# LockIn 1.1.1 focus experience

The setup form validates duration, active category, an optional intention up to 240 characters, and
session options. Category changes are permanent; the intention remains temporary and memory-only.

## Ritual and timer boundary

The optional non-blocking Qt ritual lasts about five seconds: one slow breath, the temporary
intention when present, 3, 2, 1, then a fade to black. Cancel returns to setup and clears intention.
The engine is prepared but not created or started during the ritual. The black canvas becomes active
at the completion boundary, then the monotonic `TimerEngine` starts exactly once. Disabling ritual
starts immediately.

## Focus canvas

The focus canvas owns presentation only. It formats `TimerSnapshot.remaining_planned_seconds` as
`MM:SS` below one hour or `HH:MM:SS` from one hour onward. Overtime is explicit and displays
`OVERTIME` plus `+HH:MM:SS`. Font size responds to the available window/full-screen area and is
protected from normal theme rules.

One active quote may be selected from validated local `quotes.csv` at session start. It never changes
during that session and can be hidden/shown. No quote is shown when disabled, invalid, or unavailable.
There is no network, quote editing, CSV mutation, or hourly rotation.

Pause/resume/stop/minimize/full-screen/quote/distraction/help controls reveal near the bottom.
Inactivity hides controls and the canvas cursor while running/overtime only; movement or C restores
both. Current enabled shortcut hints appear on applicable controls. Cursor changes are local to
LockIn and never trap/confine input.

## Local shortcuts and distractions

Eight configurable `QShortcut` bindings are parented to the focus widget with
`WidgetWithChildrenShortcut`. The dispatcher rechecks active focus/window, visibility, minimized
state, modal ownership, editable focus, enabled binding, and timer state. No `ApplicationShortcut`,
native hotkey, or global hook is used. QSettings stores only portable binding text and enablement.

D records a snapshot-derived marker in memory while running/overtime and never pauses. Markers have
strict session sequence, monotonic offset, focus/remaining values, overtime flag, and category
snapshot. Only the count appears in the summary; returning to setup clears every marker.

## Completion, overtime, and summary

Completion appears once and shows planned focus, total focus, and longest continuous block. Waiting
there is non-focus time. **Continue Overtime** uses the existing explicit engine transition and keeps
the same quote/window mode. **Finish Session** or confirmed Stop creates a temporary summary with
planned/overtime/focus/pause/continuity values and status.

Returning to setup disposes the engine/adapter, restores shell/window state, and clears intention.
Once the ritual completes, the session lifecycle is saved transactionally; cancellation before timer
start creates no session. Finalized focus becomes available to portable sync, dashboard, statistics,
and history.

## Phase 6 persistence lifecycle

The Phase 6 application replaces the earlier unsaved boundary. The monotonic engine remains timing
authority; aware wall time supplies timestamps only. Start inserts the session, first planned-focus
segment, and runtime heartbeat together. Pause closes focus and opens pause; Resume classifies the
pause at the fixed ten-second grace and opens planned or overtime focus. Planned completion closes
the planned segment and retains runtime state without an open segment. Overtime is explicit.

Stop, Finish, and End-and-Exit reconcile integer seconds, save aggregates and a canonical SHA-256
checksum, and delete runtime state atomically. A transition write failure blocks later actions rather
than continuing unsaved. Distraction feedback appears only after commit. The intention stays in memory.

## Phase 10 focus feedback

Quote rotation derives exclusively from `TimerSnapshot.total_focus_seconds`, so it is invariant to UI
poll cadence and excludes pause/sleep/completion waits. Large snapshot jumps advance every crossed
hour in order. The completion audio service resets at session start and consumes its once-only guard
on the first planned-completion presentation; pause, resume, stop, recovery, and overtime completion
do not invoke it. Distraction feedback includes an accessible count and never changes timer state.
# Historical focus without a timer run

The Session History **+ Add Past Session** workflow writes a finalized historical aggregate
directly. It never starts or simulates the timer. Actual duration is authoritative; one planned
focus segment is stored when actual focus does not exceed the plan, and a contiguous overtime
segment is added when it does. Both use one continuity group so analytics treat the activity as one
continuous block.
