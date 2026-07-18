# Backup and private Git hosting

Portable CSV can be copied or stored in a private repository after deliberate review. LockIn never
runs Git automatically and does not resolve concurrent-device conflicts. Finish and sync on one
device before transferring/importing on another. Never put runtime SQLite, WAL/SHM files, logs,
diagnostics, intentions, credentials, or unreviewed personal history in a public repository.

Atomic CSV replacement keeps runtime backups. Database import keeps a verified timestamped backup
before promotion. Keep independent backups of `%LOCALAPPDATA%\LockIn` and the selected portable root.

The LockIn source repository and v1.0.0/v1.0.1 Releases are private. Release assets contain only the
installer, portable application ZIP, and SHA-256 checksums; portable history is never a release
asset. Repository privacy does not replace account security, collaborator review, or endpoint
encryption.
