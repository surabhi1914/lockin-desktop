# LockIn v1.0.0

LockIn is a local-first Windows focus timer with a monotonic timer engine, distraction markers,
confirmed-time crash recovery, Windows sleep auto-pause, portable CSV synchronization/import,
historical goals, dashboard, statistics, charts, and advanced read-only history.

## Installation

Verify `LockIn-Setup-v1.0.0.exe` using `SHA256SUMS.txt`, run it, and launch LockIn from the Start Menu.
The per-user installer needs no administrator access. The portable ZIP must be completely extracted
before `LockIn\LockIn.exe` is run.

Runtime data is under `%LOCALAPPDATA%\LockIn`; portable history is under the Windows Documents known
folder at `LockIn\portable_data`. Uninstall removes program files and shortcuts but retains user data.

## Privacy and integrity

There is no telemetry, cloud account, Spotify integration, global keyboard hook, or background
service. Release artifacts contain sanitized starter categories/quotes and empty data templates—no
devices, goals, sessions, segments, distractions, intentions, databases, logs, or backups.

This release is unsigned; SmartScreen may warn. Compare each download with the lowercase SHA-256
digest in `SHA256SUMS.txt` from the same private GitHub Release.

## Known limitations

- Windows 10/11 x64 only.
- Unsigned installer and executable.
- No auto-update, cloud sync, concurrent-device conflict resolution, Spotify, kiosk mode, or global
  shortcuts.
- System-sleep detection depends on Windows power notifications and audio depends on local drivers.
