# Portable CSV data dictionary

All files are UTF-8 with exact ordered headers. Empty values are allowed only where stated. UUIDs
are canonical lowercase, UTC timestamps end in `Z`, local timestamps include an offset, dates are
`YYYY-MM-DD`, durations are whole non-negative seconds, booleans are `true` or `false`, and record
checksums are lowercase SHA-256 hex.

Root files are `devices.csv`, `categories.csv`, `quotes.csv`, and `daily_goals.csv`. Historical files
will be placed under `<entity>/YYYY/<entity>_YYYY-MM.csv`, rotating to `_part002`, `_part003`, and so
on at 10 MiB. Phase 3 coordinates only permanent category changes; it does not synchronize history.

## Devices

- `schema_version` — integer record schema version.
- `device_id` — UUID primary record identifier.
- `device_label` — optional human-readable device name.
- `created_at_utc`, `updated_at_utc` — required lifecycle timestamps.

## Categories

- `schema_version` — integer record schema version.
- `category_id` — UUID analytical identifier; starters use deterministic UUID5.
- `category_name` — normalized Unicode display name, 1-60 characters, unique after case folding.
- `category_icon` — optional value of at most 16 characters.
- `is_active` — lowercase Boolean.
- `created_at_utc`, `updated_at_utc` — required lifecycle timestamps.

Phase 3 writes the exact ordered header, UTF-8 text, and lowercase booleans. Active rows sort before
archived rows, then by normalized name. Rewrites use a validated same-directory stage, atomic
replacement, and a runtime backup. Categories are archived/restored, never deleted. The deterministic
`Other` row cannot be renamed or archived.

## Quotes

- `quote_id` — unique short identifier (`q001` onward for generated starters).
- `quote_text` — required short UTF-8 quote text.
- `author` — optional attribution; generated originals leave this empty.
- `category` — optional classification.
- `is_active` — lowercase Boolean.
- `is_favorite` — lowercase Boolean.

## Daily goals

- `schema_version` — integer record schema version.
- `goal_id` — UUID record identifier.
- `effective_from_date` — required inclusive local start date.
- `effective_to_date` — optional inclusive local end date.
- `goal_seconds` — non-negative daily target in seconds.
- `created_at_utc`, `updated_at_utc` — required lifecycle timestamps.

## Sessions

- `schema_version` — integer record schema version.
- `session_id` — UUID record identifier.
- `device_id` — UUID source device.
- `session_sequence` — positive sequence unique per device.
- `category_id` — UUID category.
- `category_name_snapshot` — category name at session time.
- `local_date_started` — local start date.
- `timezone_name` — IANA timezone used for local interpretation.
- `utc_offset_started_minutes` — signed start offset from UTC in minutes.
- `started_at_utc`, `started_at_local` — required aware start timestamps.
- `ended_at_utc`, `ended_at_local` — optional aware end timestamps.
- `planned_focus_seconds` — positive planned duration.
- `actual_focus_seconds` — accumulated focus duration.
- `planned_focus_completed_seconds` — completed planned-focus duration.
- `overtime_seconds` — overtime duration.
- `total_pause_seconds` — total pause duration.
- `wall_clock_seconds` — elapsed wall-clock duration.
- `continuous_block_count` — number of continuous focus blocks.
- `longest_continuous_seconds` — longest block duration.
- `average_continuous_seconds` — average block duration.
- `median_continuous_seconds` — median block duration.
- `pause_count`, `short_pause_count`, `long_pause_count` — pause counts.
- `distraction_count` — marked-distraction count.
- `status` — `running`, `paused`, `completed`, `completed_with_overtime`, `stopped_early`,
  `recovered`, or `discarded`.
- `completion_reason` — optional `timer_completed`, `manual_stop`, `app_close`,
  `system_shutdown`, `crash_recovery`, `sleep_detected`, or `data_repair`.
- `stopped_early_seconds` — uncompleted planned duration.
- `completed_planned_timer` — lowercase Boolean.
- `overtime_enabled` — lowercase Boolean.
- `fullscreen_used` — lowercase Boolean.
- `quotes_enabled` — lowercase Boolean.
- `start_ritual_enabled` — lowercase Boolean.
- `created_at_utc`, `updated_at_utc` — lifecycle timestamps.
- `exported_at_utc` — portable export timestamp.
- `record_checksum` — canonical record SHA-256 checksum.

## Segments

- `schema_version` — integer record schema version.
- `segment_id` — UUID exported-part identifier.
- `source_segment_id` — optional UUID original segment when midnight splitting creates parts.
- `session_id` — UUID parent session.
- `device_id` — UUID source device.
- `segment_sequence` — positive sequence within the session.
- `midnight_part_number` — positive part number after local-midnight splitting.
- `segment_type` — `focus` or `pause`.
- `started_at_utc`, `ended_at_utc` — aware UTC bounds; end may be empty while active.
- `started_at_local`, `ended_at_local` — offset-aware local bounds; end may be empty.
- `local_date` — local date represented by this exported part.
- `timezone_name` — IANA timezone.
- `utc_offset_minutes` — signed UTC offset at part start.
- `duration_seconds` — part duration.
- `counts_as_focus` — lowercase Boolean.
- `pause_duration_seconds` — pause duration represented by the part.
- `pause_classification` — `none`, `short_grace_pause`, `continuity_break`, or `system_sleep`.
- `breaks_continuity` — lowercase Boolean.
- `continuity_group_id` — optional UUID grouping uninterrupted work.
- `pause_grace_threshold_seconds` — configured grace threshold.
- `focus_phase` — `planned`, `overtime`, or `not_applicable`.
- `crossed_midnight` — lowercase Boolean indicating the source crossed a local midnight.
- `end_reason` — optional controlled future termination label.
- `created_at_utc` — source creation timestamp.
- `exported_at_utc` — portable export timestamp.
- `record_checksum` — canonical record SHA-256 checksum.

## Distractions

- `schema_version` — integer record schema version.
- `distraction_id` — UUID record identifier.
- `session_id` — UUID parent session.
- `segment_id` — optional UUID active segment.
- `device_id` — UUID source device.
- `marked_at_utc`, `marked_at_local` — aware mark timestamps.
- `local_date` — local mark date.
- `timezone_name` — IANA timezone.
- `category_id` — UUID category.
- `category_name_snapshot` — category name at mark time.
- `elapsed_focus_seconds` — focused time elapsed.
- `remaining_planned_seconds` — planned time remaining.
- `is_overtime` — lowercase Boolean.
- `optional_note` — optional user note.
- `created_at_utc` — source creation timestamp.
- `exported_at_utc` — portable export timestamp.
- `record_checksum` — canonical record SHA-256 checksum.

There is deliberately no intentions CSV and no intention column in any portable contract. Phase 3
also creates no session, segment, or distraction CSV; its preview is entirely unsaved.
## Phase 7 encoding and identity rules

All headers come from `app.portability.csv_contracts` in exact order. CSV is UTF-8; booleans are
lowercase `true`/`false`; durations/counts are integer seconds; UUIDs are canonical lowercase;
UTC timestamps end in `Z`; optional values are empty strings. Session checksums reuse the final
SQLite checksum. Segment and distraction checksums exclude `exported_at_utc` and
`record_checksum`. Midnight-split segment rows have deterministic portable IDs while preserving
`source_segment_id`, and their durations sum exactly to the source segment.

## Phase 8 import interpretation

Every discovered CSV must use its manifest contract and exact ordered header. Partition filenames,
month keys, part numbering, UUIDs, timestamps, enums, booleans, relationships, aggregate formulas,
and checksums are validated before staging. Root singleton tables and all monthly partitions are
scanned. A session checksum is its immutable identity; segment/distraction identities use their
stable content fields. Rows split at local midnight are grouped by `source_segment_id` and rebuilt
as one logical segment. Duplicate IDs with different content and normalized-name category collisions
are conflicts, never last-writer-wins updates.
