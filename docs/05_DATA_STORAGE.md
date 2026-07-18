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
