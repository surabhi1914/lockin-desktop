# Troubleshooting

Confirm Python 3.12 is selected, use only the repository `.venv`, and run the commands in
[12_TESTING.md](12_TESTING.md).

If full screen opens on an unexpected monitor, exit full screen, move most of the normal LockIn
window onto the intended monitor, and enter again. There is intentionally no monitor selector. If a
monitor is unplugged, LockIn should recover windowed on the current primary display while time keeps
running.

If controls/cursor disappear, move the pointer near the bottom or use the currently assigned Show
focus controls shortcut (C by default). They remain visible while paused or while overlay/confirmation
UI is open. If no quote appears, confirm Show quotes is enabled and `quotes.csv` validates; focus
continues safely without a quote.

If a shortcut does nothing, confirm it is enabled in Settings, has no inline conflict, and that the
focus screen is the active non-minimized LockIn window. Shortcuts are intentionally suppressed in
text fields, key capture, blocking dialogs, setup/settings pages, another application, and tray-hidden
state. Use Reset on one row or confirmed Reset All if stored preferences are unsuitable. Esc exits
full screen only; it intentionally does nothing while windowed.

When LockIn is hidden, use **Show LockIn** in the tray. Without a system tray, minimize remains safe
but Minimize-to-Tray is not offered by the active exit guard. Local shortcuts do not operate while
hidden. There is no global shortcut fallback or notification. If completion sound is enabled but
inaudible, use **Settings > Preview Sound**, verify volume, and check the Windows output device;
timer completion continues even when audio is unavailable.

## Installed application does not start

Run `LockIn.exe --health-check-output health.json` from PowerShell with temporary runtime and portable
overrides. Review only the privacy-safe status fields. Reinstall from a checksum-verified installer
if an immutable resource is missing. Do not move `LockIn.exe` out of its onedir folder and do not
delete `%LOCALAPPDATA%\LockIn` while diagnosing user history.

An unsigned-build SmartScreen warning is expected; verify SHA-256 rather than disabling Windows
security. On uninstall, application files should disappear while runtime and portable history remain.

If LockIn reports an unfinished local session, review the confirmed focus and separately displayed
unknown gap. **Save Confirmed Time** closes at the last trustworthy boundary and syncs the recovered
record; **Discard Session** retains an audit but excludes the session from focus totals. Neither
choice invents time. Run `scripts\inspect_recovery_state.py` for a privacy-safe read-only summary.

After Windows sleep, LockIn remains paused and sleep is a continuity-breaking, non-focus pause.
Choose Resume or Stop; LockIn never resumes automatically. If native power events are unavailable,
heartbeat-gap recovery remains conservative.

If a lifecycle or heartbeat write fails, LockIn shows a local-database error. After possible
timer/database divergence, actions remain blocked. Do not delete the database; run the read-only
`scripts/verify_session_integrity.py` command and preserve runtime files for diagnosis.
## Portable sync pending

Close programs such as Excel that may lock a CSV, then choose **Settings > Sync now**. LockIn
keeps the finalized SQLite session even when export fails. Do not hand-move rows between monthly
partitions. Run `scripts/verify_portable_sync.py` for duplicate, checksum, parent, aggregate, or
ledger-path errors before retrying repair.

## Portable import is not ready

Run `scripts\inspect_import_readiness.py --portable-root <folder>`. A missing file, newer manifest,
incorrect header, invalid checksum, duplicate ID, broken parent reference, partition gap, or aggregate
mismatch blocks staging. Repair the source deliberately; do not edit only a checksum. For a conflict
against the live database, export the JSON report and compare both records. A failed staging build
does not replace the live database; preserve its diagnostic path and timestamped backup. Close active
focus and resolve unfinished runtime state before retrying.
