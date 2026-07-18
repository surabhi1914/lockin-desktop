# Contributing

LockIn 1.0.0 is feature-complete. Changes should be narrowly scoped to correctness, accessibility,
data safety, documentation, or Windows compatibility. Do not add telemetry, cloud accounts, Spotify,
global hooks, kiosk/system blocking, or automatic Git operations.

Use Python 3.12 and install dependencies only in `.venv`. Run pytest with the documented coverage
gate, Ruff, formatting, mypy, integrity, portable verification, import verification, and analytics
verification before proposing a change. Tests that write data must use temporary runtime and portable
roots. Never commit databases, logs, backups, diagnostics, credentials, intentions, personal history,
build output, or release binaries.
