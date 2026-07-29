# Product boundary after 1.0.0

LockIn v1.0.0 is feature-complete. There is no Phase 14. Maintenance may address data safety,
accessibility, Windows compatibility, security, documentation, or release-blocking defects without
redesigning the product.

Spotify, cloud accounts/synchronization, telemetry, auto-update, global keyboard hooks, kiosk/system
blocking, background services, macOS, Linux, and mobile applications are not part of LockIn 1.0.0.
Concurrent multi-device conflict resolution remains a deliberate manual workflow.
# LockIn 1.1 maintenance boundary

Manual-session editing is deferred until the same transaction, checksum, portable partition,
conflict, and re-import guarantees can be applied to updates. Deletion is deferred because the
current portable format has no tombstone contract; a local-only delete could reappear after import.
Neither operation should be added without end-to-end propagation and reconstruction tests.
