# SQLite schema version 4

The runtime database enables foreign keys, requests WAL mode, uses a 5-second busy timeout, and
applies migrations transactionally. All timestamps are aware ISO 8601 strings; `*_utc` values end
in `Z`. Boolean integers are constrained to `0` or `1`. Durations are whole seconds.

## `schema_migrations`

- `version` — integer primary key and applied schema version.
- `applied_at_utc` — required migration timestamp.

## `app_metadata`

- `key` — text primary key for application metadata.
- `value` — required text value.

## `devices`

- `device_id` — UUID text primary key.
- `device_label` — optional human label.
- `created_at_utc`, `updated_at_utc` — required lifecycle timestamps.

## `categories`

- `category_id` — UUID text primary key.
- `category_name` — required display/analytical name.
- `category_icon` — optional future icon identifier.
- `is_active` — required Boolean integer.
- `created_at_utc`, `updated_at_utc` — required lifecycle timestamps.

Unique index `ux_categories_name_nocase` prevents category names that differ only by case.

## `daily_goals`

- `goal_id` — UUID text primary key.
- `effective_from_date` — required inclusive local `YYYY-MM-DD` start.
- `effective_to_date` — optional inclusive local end, constrained not to precede the start.
- `goal_seconds` — required non-negative daily target.
- `created_at_utc`, `updated_at_utc` — required lifecycle timestamps.

Index `ix_daily_goals_dates` supports effective-range lookup.

## `sessions`

- `session_id` — UUID text primary key.
- `schema_version` — required record schema version.
- `device_id` — required foreign key to `devices.device_id`.
- `session_sequence` — required positive per-device sequence; unique with `device_id`.
- `category_id` — required foreign key to `categories.category_id`.
- `category_name_snapshot` — required name retained as it appeared at session time.
- `local_date_started` — required local start date.
- `timezone_name` — required IANA timezone.
- `utc_offset_started_minutes` — required signed start offset from UTC.
- `started_at_utc`, `started_at_local` — required aware start timestamps.
- `ended_at_utc`, `ended_at_local` — optional aware end timestamps while active.
- `planned_focus_seconds` — required positive planned duration.
- `actual_focus_seconds` — non-negative accumulated focus, default `0`.
- `planned_focus_completed_seconds` — non-negative planned portion completed, default `0`.
- `overtime_seconds` — non-negative overtime, default `0`.
- `total_pause_seconds` — non-negative pause total, default `0`.
- `wall_clock_seconds` — non-negative elapsed wall time, default `0`.
- `continuous_block_count` — non-negative focus-block count, default `0`.
- `longest_continuous_seconds` — non-negative longest block, default `0`.
- `average_continuous_seconds` — non-negative average block, default `0`.
- `median_continuous_seconds` — non-negative median block, default `0`.
- `pause_count`, `short_pause_count`, `long_pause_count` — non-negative counts, default `0`.
- `distraction_count` — non-negative marked-distraction count, default `0`.
- `status` — required: `running`, `paused`, `completed`, `completed_with_overtime`,
  `stopped_early`, `recovered`, or `discarded`.
- `completion_reason` — optional: `timer_completed`, `manual_stop`, `app_close`,
  `system_shutdown`, `crash_recovery`, `sleep_detected`, or `data_repair`.
- `stopped_early_seconds` — non-negative uncompleted planned time, default `0`.
- `completed_planned_timer` — Boolean, default `0`.
- `overtime_enabled` — Boolean, default `0`.
- `fullscreen_used` — Boolean, default `0`.
- `quotes_enabled` — Boolean, default `1`.
- `start_ritual_enabled` — Boolean, default `1`.
- `created_at_utc`, `updated_at_utc` — required lifecycle timestamps.
- `record_checksum` — optional lowercase SHA-256 portable-record checksum.

Indexes cover `local_date_started`, `category_id`, `status`, and `started_at_utc`.

## `segments`

- `segment_id` — UUID text primary key.
- `schema_version` — required record schema version.
- `session_id` — required foreign key to `sessions.session_id`; historical rows do not cascade.
- `device_id` — required foreign key to `devices.device_id`.
- `segment_sequence` — required positive sequence; unique with `session_id`.
- `segment_type` — required `focus` or `pause`.
- `started_at_utc` — required aware UTC start.
- `ended_at_utc` — optional aware UTC end while active.
- `timezone_name` — required IANA timezone.
- `utc_offset_started_minutes` — required signed offset.
- `duration_seconds` — non-negative duration, default `0`.
- `counts_as_focus` — required Boolean.
- `pause_classification` — required `none`, `short_grace_pause`, `continuity_break`, or
  `system_sleep`.
- `breaks_continuity` — required Boolean.
- `continuity_group_id` — optional UUID joining continuous work.
- `pause_grace_threshold_seconds` — non-negative threshold, default `10`.
- `focus_phase` — required `planned`, `overtime`, or `not_applicable`.
- `end_reason` — optional termination label reserved for future controlled values.
- `created_at_utc`, `updated_at_utc` — required lifecycle timestamps.

Indexes cover `session_id` and `started_at_utc`.

## `distractions`

- `distraction_id` — UUID text primary key.
- `schema_version` — required record schema version.
- `session_id` — required foreign key to `sessions.session_id`.
- `segment_id` — optional foreign key to `segments.segment_id`.
- `device_id` — required foreign key to `devices.device_id`.
- `marked_at_utc`, `marked_at_local` — required aware mark timestamps.
- `local_date` — required local date.
- `timezone_name` — required IANA timezone.
- `category_id` — required foreign key to `categories.category_id`.
- `category_name_snapshot` — required category name at mark time.
- `elapsed_focus_seconds` — required non-negative focused time.
- `remaining_planned_seconds` — required non-negative planned time remaining.
- `is_overtime` — required Boolean.
- `optional_note` — optional user note.
- `created_at_utc` — required creation timestamp.

Indexes cover `session_id`, `local_date`, `category_id`, and `marked_at_utc`.

## `runtime_session_state`

- `session_id` — primary key and foreign key to `sessions.session_id`.
- `timer_state` — required future recovery-state label.
- `temporary_intention_text` — optional runtime-only intention; a future finalization transaction
  must delete it. It is never portable.
- `remaining_planned_seconds` — required non-negative recovery value.
- `is_overtime` — required Boolean recovery flag.
- `last_heartbeat_at_utc` — optional last heartbeat timestamp.
- `updated_at_utc` — required state timestamp.

## `sync_ledger`

- `record_type` — entity type; first part of the composite primary key.
- `record_id` — record UUID; second part of the composite primary key.
- `partition_relative_path` — required portable-root-relative CSV path.
- `record_checksum` — required lowercase SHA-256 checksum.
- `exported_at_utc` — required export timestamp.

This local table records verified portable exports and makes synchronization idempotent. It is not
itself portable history and is reconstructed from imported provenance when needed.

## Migration v2

SQLite migration v2 is forward-only and transactional. It adds non-negative
`runtime_session_state.timer_version` and partial unique index
`ux_segments_one_open_per_session` on `segments(session_id) WHERE ended_at_utc IS NULL`. Schema v1 is
unchanged, upgrades preserve data, and the portable record/manifest schema remains v1.

Phase 6 always stores `temporary_intention_text` as `NULL`. Planned-completion wait has no open
segment. Finalized rows have an end timestamp, a final status/reason/checksum, reconciled aggregates,
and no runtime row or open segment.

## Phase 8 reconstruction

Phase 8 adds no schema migration. It reconstructs the current schema through existing migrations, then loads
devices, categories, goals, finalized sessions, reconstructed logical segments, distractions, and
sync-ledger provenance transactionally. Portable midnight fragments sharing a `source_segment_id`
become one SQLite segment with validated contiguous times and summed duration; legacy unsplit rows
receive deterministic source identity. `app_metadata` stores import provenance. The new local device
is registered separately and does not replace historical device foreign keys.

## Migration v3

Migration v3 adds confirmed planned, overtime, pause, and wall-clock counters plus the optional
sleep boundary to `runtime_session_state`. The local-only `recovery_events` table records detection,
the last heartbeat, confirmed boundary, unknown gap, user action, original state, and integrity
result; it never stores an intention. Analytics indexes are additive. Recovery finalization removes
runtime state, closes the open segment at the confirmed boundary, recomputes aggregates/checksum,
and retains the audit row.

## Migration v4

Migration v4 adds database triggers that reject overlapping `daily_goals` ranges, initializes the
`analytics_revision` metadata key, and increments it after session, segment, distraction, or goal
mutations. Dashboard/statistics caches therefore invalidate after finalization, recovery, import,
and goal changes without making UI widgets calculate business metrics.
# Schema version 5

Migration v5 rebuilds `sessions` to extend the completion-reason constraint with `manual_entry` and
adds:

- `entry_source`: `timer`, `manual`, `recovery`, or `imported`;
- `manual_entry_created_at_utc`: required only for manual entries;
- `manual_entry_updated_at_utc`: reserved for a future fully transactional editor.

Legacy recovery rows are classified from recovery metadata and completion reason; normal timer rows
remain timer rows. Imported schema-v1 portable rows with no reliable provenance become `imported`.
Manual sessions require finalized focus-only segments, zero pause/distraction aggregates, one
continuity group, no runtime or recovery rows, and a source-aware checksum.
