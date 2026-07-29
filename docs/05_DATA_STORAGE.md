# Data storage

SQLite is LockIn's operational source of truth; portable UTF-8 CSV is its explicit, human-readable
interchange. Installed defaults are:

```text
%LOCALAPPDATA%\LockIn\runtime\
%LOCALAPPDATA%\LockIn\logs\
%LOCALAPPDATA%\LockIn\backups\
%LOCALAPPDATA%\LockIn\diagnostics\
<Windows Documents>\LockIn\portable_data\
```

Windows Known Folder resolution supports redirected/OneDrive Documents. Development defaults remain
`.local_data\runtime` and `portable_data` in the repository. `LOCKIN_RUNTIME_ROOT` and
`LOCKIN_PORTABLE_ROOT` provide explicit overrides; the resolved roots must differ.

SQLite stores device identity, effective-dated goals, sessions, segments, distractions, runtime
heartbeats, recovery audit, checksums, and the sync ledger. Portable CSV stores validated devices,
categories, quotes, goals, finalized sessions, logical segment fragments, and distractions. Writes
are staged, validated, backed up, and atomically replaced. Imports build or merge in staging before
promotion. Unknown crash gaps and temporary intentions are never counted or exported; intention is
always memory-only/NULL.

Immutable themes, sound, icon, migrations, and sanitized starter templates live in the installed
bundle. LockIn never writes beside `LockIn.exe`. Installer upgrades cannot overwrite user data and
uninstall never deletes history.
# Manual-session provenance

SQLite schema v5 adds `entry_source`, `manual_entry_created_at_utc`, and
`manual_entry_updated_at_utc` to sessions. A manual session is finalized in one transaction with
one or two closed focus segments and no runtime, heartbeat, recovery, pause, distraction, sleep, or
intention row. Portable session CSV schema v2 carries the same provenance. Schema-v1 portable
folders remain readable and are upgraded with backups before local synchronization.
