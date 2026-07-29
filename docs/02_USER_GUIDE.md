# User guide

Launch installed LockIn from the Start Menu or run `main.py` in a development checkout. Home shows
today's goal progress, yesterday, week comparison, longest blocks, streak, and a deterministic focus
challenge. The sidebar opens setup, statistics, history, categories, quotes, and settings.

## Focus workflow

Open **Start Focus**, choose a duration and active category, optionally enter a temporary intention,
and select ritual/full-screen/quote/sound/overtime options. The ritual displays the intention only in
memory, then transitions 3–2–1 into the black focus screen. Pause/resume, confirmed stop, full screen,
minimize, quote visibility, distraction marking, and shortcut help remain visible or accessible.

Default focus-window-only shortcuts are Space, F11, Esc, Ctrl+Shift+S, D, Q, C, and Ctrl+/. Settings
can reassign or disable each. They are suppressed in text inputs, dialogs, other applications, and
when LockIn is minimized/hidden; there is no global hook.

Minimize/tray and application switching do not pause. Planned completion shows an overlay and plays
the optional local chime once. Finish or explicitly enter overtime. Stop/exit requires confirmation.
Sessions, focus/pause segments, distractions, continuity, and final checksums are saved locally and
then synchronized to portable CSV. Temporary intention is never persisted.

## Recovery and portable data

After a crash, save only heartbeat-confirmed time or discard the session; the unknown gap is always
excluded and retained only in audit evidence. Windows sleep auto-pauses and breaks continuity. Resume
is explicit and starts a new continuity group.

Settings provides manual sync, portable-folder access, validated fresh-device reconstruction, and a
safe staged merge. Exact duplicates are skipped; conflicts never silently overwrite data. Historical
device identity remains attached to imported history.

## Quotes, sound, goals, and analytics

Quotes can be searched, added, edited, enabled, favorited, imported, and exported. Rotation advances
after each full active focus hour; pauses and sleep do not count. Completion sound has master enable,
volume, preview, and per-session control. Distractions remain simple markers without types or notes.

Goals are effective-dated and preserve history. Statistics supports presets/custom dates, filters,
Qt-native charts, calendar heatmap, block/pause/distraction metrics, and explicit external CSV export.
Session History is read-only, searchable, filtered, sorted, paginated, and exposes segment/recovery/
sync evidence without intentions.

Use **Help > About LockIn** for version, build, privacy statement, and data-folder buttons.
# Manual past sessions

Open **Session History** and choose **+ Add Past Session** to record focus completed without the
timer. Enter the local date, start time, actual focus duration, category, and optionally a different
planned duration. Archived categories are available under the labelled historical group. The
preview shows the derived end time and whether the result is completed, completed with overtime, or
stopped early.

Manual records carry a visible **Manual** source badge. They count toward goals, streaks, dashboard
records, heatmaps, and statistics. They do not reconstruct intentions, pauses, distractions, sleep,
heartbeat, or recovery data. An exact duplicate is blocked; other overlaps require confirmation.
Ambiguous fall-back times require selecting the first or second occurrence, and nonexistent
spring-forward times are rejected.
