-- LockIn 1.1 source provenance and manual past-session support.
PRAGMA defer_foreign_keys = ON;

CREATE TABLE sessions_v5 (
    session_id TEXT PRIMARY KEY,
    schema_version INTEGER NOT NULL,
    device_id TEXT NOT NULL,
    session_sequence INTEGER NOT NULL CHECK (session_sequence >= 1),
    category_id TEXT NOT NULL,
    category_name_snapshot TEXT NOT NULL,
    local_date_started TEXT NOT NULL,
    timezone_name TEXT NOT NULL,
    utc_offset_started_minutes INTEGER NOT NULL,
    started_at_utc TEXT NOT NULL,
    started_at_local TEXT NOT NULL,
    ended_at_utc TEXT,
    ended_at_local TEXT,
    planned_focus_seconds INTEGER NOT NULL CHECK (planned_focus_seconds > 0),
    actual_focus_seconds INTEGER NOT NULL DEFAULT 0 CHECK (actual_focus_seconds >= 0),
    planned_focus_completed_seconds INTEGER NOT NULL DEFAULT 0
        CHECK (planned_focus_completed_seconds >= 0),
    overtime_seconds INTEGER NOT NULL DEFAULT 0 CHECK (overtime_seconds >= 0),
    total_pause_seconds INTEGER NOT NULL DEFAULT 0 CHECK (total_pause_seconds >= 0),
    wall_clock_seconds INTEGER NOT NULL DEFAULT 0 CHECK (wall_clock_seconds >= 0),
    continuous_block_count INTEGER NOT NULL DEFAULT 0 CHECK (continuous_block_count >= 0),
    longest_continuous_seconds INTEGER NOT NULL DEFAULT 0
        CHECK (longest_continuous_seconds >= 0),
    average_continuous_seconds INTEGER NOT NULL DEFAULT 0
        CHECK (average_continuous_seconds >= 0),
    median_continuous_seconds INTEGER NOT NULL DEFAULT 0
        CHECK (median_continuous_seconds >= 0),
    pause_count INTEGER NOT NULL DEFAULT 0 CHECK (pause_count >= 0),
    short_pause_count INTEGER NOT NULL DEFAULT 0 CHECK (short_pause_count >= 0),
    long_pause_count INTEGER NOT NULL DEFAULT 0 CHECK (long_pause_count >= 0),
    distraction_count INTEGER NOT NULL DEFAULT 0 CHECK (distraction_count >= 0),
    status TEXT NOT NULL CHECK (status IN (
        'running', 'paused', 'completed', 'completed_with_overtime',
        'stopped_early', 'recovered', 'discarded'
    )),
    completion_reason TEXT CHECK (completion_reason IS NULL OR completion_reason IN (
        'timer_completed', 'manual_stop', 'manual_entry', 'app_close', 'system_shutdown',
        'crash_recovery', 'sleep_detected', 'data_repair'
    )),
    stopped_early_seconds INTEGER NOT NULL DEFAULT 0 CHECK (stopped_early_seconds >= 0),
    completed_planned_timer INTEGER NOT NULL DEFAULT 0 CHECK (completed_planned_timer IN (0, 1)),
    overtime_enabled INTEGER NOT NULL DEFAULT 0 CHECK (overtime_enabled IN (0, 1)),
    fullscreen_used INTEGER NOT NULL DEFAULT 0 CHECK (fullscreen_used IN (0, 1)),
    quotes_enabled INTEGER NOT NULL DEFAULT 1 CHECK (quotes_enabled IN (0, 1)),
    start_ritual_enabled INTEGER NOT NULL DEFAULT 1 CHECK (start_ritual_enabled IN (0, 1)),
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    entry_source TEXT NOT NULL DEFAULT 'timer'
        CHECK (entry_source IN ('timer', 'manual', 'recovery', 'imported')),
    manual_entry_created_at_utc TEXT,
    manual_entry_updated_at_utc TEXT,
    record_checksum TEXT,
    FOREIGN KEY (device_id) REFERENCES devices(device_id),
    FOREIGN KEY (category_id) REFERENCES categories(category_id),
    UNIQUE (device_id, session_sequence),
    CHECK (
        (entry_source = 'manual'
         AND completion_reason = 'manual_entry'
         AND manual_entry_created_at_utc IS NOT NULL)
        OR
        (entry_source != 'manual'
         AND completion_reason != 'manual_entry'
         AND manual_entry_created_at_utc IS NULL
         AND manual_entry_updated_at_utc IS NULL)
    )
);

INSERT INTO sessions_v5 (
    session_id, schema_version, device_id, session_sequence, category_id,
    category_name_snapshot, local_date_started, timezone_name,
    utc_offset_started_minutes, started_at_utc, started_at_local, ended_at_utc,
    ended_at_local, planned_focus_seconds, actual_focus_seconds,
    planned_focus_completed_seconds, overtime_seconds, total_pause_seconds,
    wall_clock_seconds, continuous_block_count, longest_continuous_seconds,
    average_continuous_seconds, median_continuous_seconds, pause_count,
    short_pause_count, long_pause_count, distraction_count, status,
    completion_reason, stopped_early_seconds, completed_planned_timer,
    overtime_enabled, fullscreen_used, quotes_enabled, start_ritual_enabled,
    created_at_utc, updated_at_utc, entry_source, manual_entry_created_at_utc,
    manual_entry_updated_at_utc, record_checksum
)
SELECT
    session_id, schema_version, device_id, session_sequence, category_id,
    category_name_snapshot, local_date_started, timezone_name,
    utc_offset_started_minutes, started_at_utc, started_at_local, ended_at_utc,
    ended_at_local, planned_focus_seconds, actual_focus_seconds,
    planned_focus_completed_seconds, overtime_seconds, total_pause_seconds,
    wall_clock_seconds, continuous_block_count, longest_continuous_seconds,
    average_continuous_seconds, median_continuous_seconds, pause_count,
    short_pause_count, long_pause_count, distraction_count, status,
    completion_reason, stopped_early_seconds, completed_planned_timer,
    overtime_enabled, fullscreen_used, quotes_enabled, start_ritual_enabled,
    created_at_utc, updated_at_utc,
    CASE
        WHEN completion_reason IN ('crash_recovery', 'sleep_detected')
             OR EXISTS (
                 SELECT 1 FROM recovery_events r
                 WHERE r.session_id = sessions.session_id
             )
            THEN 'recovery'
        WHEN completion_reason = 'data_repair' THEN 'imported'
        ELSE 'timer'
    END,
    NULL, NULL, record_checksum
FROM sessions;

DROP TABLE sessions;
ALTER TABLE sessions_v5 RENAME TO sessions;

CREATE INDEX ix_sessions_local_date ON sessions(local_date_started);
CREATE INDEX ix_sessions_category ON sessions(category_id);
CREATE INDEX ix_sessions_status ON sessions(status);
CREATE INDEX ix_sessions_started ON sessions(started_at_utc);
CREATE INDEX ix_sessions_analytics_range
    ON sessions(status, local_date_started, category_id, device_id);
CREATE INDEX ix_sessions_entry_source
    ON sessions(entry_source, local_date_started);

CREATE TRIGGER trg_analytics_sessions_insert
AFTER INSERT ON sessions BEGIN
    UPDATE app_metadata SET value = CAST(value AS INTEGER) + 1 WHERE key='analytics_revision';
END;
CREATE TRIGGER trg_analytics_sessions_update
AFTER UPDATE ON sessions BEGIN
    UPDATE app_metadata SET value = CAST(value AS INTEGER) + 1 WHERE key='analytics_revision';
END;
CREATE TRIGGER trg_analytics_sessions_delete
AFTER DELETE ON sessions BEGIN
    UPDATE app_metadata SET value = CAST(value AS INTEGER) + 1 WHERE key='analytics_revision';
END;
