# LockIn v1.0.1

LockIn v1.0.1 is a focused Windows hotfix for the transient window flash seen during normal UI
interaction. It contains no feature addition, database migration, or user-history format change.

## Fixed

The Categories page previously created each row's Rename and Archive buttons without a Qt parent and
called `setVisible(True)` before adding them to the row layout. Qt therefore promoted every visible
button to a native top-level window for about 31–32 ms. Opening or refreshing Categories rebuilt the
rows, so one interaction could create many brief blank windows.

The controls are now parented to their `CategoryRow`, added to the layout, and only then assigned
visibility. Development-only tracing and automated regression coverage verify that normal
interactions launch no processes, create no parentless transient widgets, preserve the main native
window, and reuse existing pages.

## Installation and compatibility

Verify `LockIn-Setup-v1.0.1.exe` using `SHA256SUMS.txt`, then install it over v1.0.0. The per-user
upgrade replaces program files while preserving runtime SQLite data, portable CSV history, settings,
logs, backups, and diagnostics. The portable ZIP must be completely extracted before
`LockIn\LockIn.exe` is run.

Runtime data remains under `%LOCALAPPDATA%\LockIn`; portable history remains under the Windows
Documents known folder at `LockIn\portable_data`. Uninstall removes program files and shortcuts but
retains user data.

## Privacy and limitations

There is no telemetry, cloud account, Spotify integration, global keyboard hook, background service,
or automatic update. Release artifacts contain sanitized starter resources and no runtime database,
logs, backups, intentions, personal history, portable data, or credentials.

This release is unsigned; SmartScreen may warn. Compare each download with the lowercase SHA-256
digest in `SHA256SUMS.txt` from the same private GitHub Release. Windows 10/11 x64 remains the
supported target. The existing v1.0.0 tag, Release, and assets remain unchanged.
