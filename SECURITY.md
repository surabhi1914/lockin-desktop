# Security and privacy

LockIn is local-first. It has no telemetry, cloud account, background service, remote API, or bundled
Git automation. Operational data is stored in local SQLite and portable UTF-8 CSV at the locations
documented in the README. A private GitHub repository still requires normal account and collaborator
hygiene; repository privacy is not a substitute for backups or endpoint security.

The Windows 1.0.1 binaries are unsigned. Windows SmartScreen may warn. Verify both downloaded assets
against the lowercase SHA-256 values in `SHA256SUMS.txt` from the same private release. Do not disable
Windows security controls.

To report a vulnerability, use the private repository's Security tab or open a private discussion
with the repository owner. Do not include focus history, intentions, tokens, database files, portable
CSV, or other personal data in a report. No private email address is published for this project.
Support and remediation are best-effort.
