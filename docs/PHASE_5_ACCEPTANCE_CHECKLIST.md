# Phase 5 acceptance checklist

- [x] Every Phase 0-4 entry test/quality gate and native focus scenario passed before editing.
- [x] No dependency was added; every command uses the workspace `.venv`.
- [x] Eight stable typed actions have the specified enabled defaults and allowed states.
- [x] Portable one-combination validation rejects empty-enabled, modifiers, chords, Alt+F4,
  Windows-key, Print Screen, unsafe Stop, malformed, and enabled duplicates.
- [x] Settings supports enable/disable with retained key, reassignment, Apply, Cancel/Revert, one-row
  reset, confirmed Reset All, inline conflict, and disabled invalid Apply.
- [x] Complete validated binding sets persist only in device-local QSettings with migration,
  rollback, and corrupt-conflict recovery.
- [x] QShortcut objects use `WidgetWithChildrenShortcut`, exist only during active focus, refresh
  without duplication, retain references, and dispose at focus end.
- [x] Dispatch rechecks active app/window/focus view, visibility, minimized/hidden state, editable
  focus, modal/help state, enablement, and allowed timer state.
- [x] Every listed editable widget and marked category/shortcut dialog suppresses focus actions.
- [x] Space/F11/Esc/Ctrl+Shift+S/D/Q/C/Ctrl+/ reuse existing focus behavior safely.
- [x] Esc exits full screen only; Stop reuses one guarded confirmation.
- [x] Help and control tooltips show enabled current custom mappings and update after save.
- [x] Distractions are immutable snapshot-derived memory values, do not pause, show subtle feedback,
  clear at disposal, and expose only count in the temporary summary.
- [x] Minimize/tray/other-window behavior blocks shortcuts while monotonic timing continues.
- [x] Shortcut/marker flows create no session/segment/distraction/recovery/sync DB row or portable
  session/distraction file and do not alter reference CSV.
- [x] Phase 0-5 tests, 90% coverage, Ruff, formatting, mypy, docs, and native scenarios A-L pass.
- [x] No global hooks, tray timer actions, sound, hourly quote rotation, session/distraction
  persistence, CSV sync, sleep/crash recovery, statistics/history, Spotify, packaging, installer,
  commit, or push was added.
