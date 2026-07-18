CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS devices (
    device_id TEXT PRIMARY KEY,
    device_label TEXT,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS categories (
    category_id TEXT PRIMARY KEY,
    category_name TEXT NOT NULL,
    category_icon TEXT,
    is_active INTEGER NOT NULL CHECK (is_active IN (0, 1)),
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_categories_name_nocase
    ON categories(category_name COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS daily_goals (
    goal_id TEXT PRIMARY KEY,
    effective_from_date TEXT NOT NULL,
    effective_to_date TEXT,
    goal_seconds INTEGER NOT NULL CHECK (goal_seconds >= 0),
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    CHECK (effective_to_date IS NULL OR effective_to_date >= effective_from_date)
);

CREATE TABLE IF NOT EXISTS sessions (
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
        'timer_completed', 'manual_stop', 'app_close', 'system_shutdown',
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
    record_checksum TEXT,
    FOREIGN KEY (device_id) REFERENCES devices(device_id),
    FOREIGN KEY (category_id) REFERENCES categories(category_id),
    UNIQUE (device_id, session_sequence)
);

CREATE TABLE IF NOT EXISTS segments (
    segment_id TEXT PRIMARY KEY,
    schema_version INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    segment_sequence INTEGER NOT NULL CHECK (segment_sequence >= 1),
    segment_type TEXT NOT NULL CHECK (segment_type IN ('focus', 'pause')),
    started_at_utc TEXT NOT NULL,
    ended_at_utc TEXT,
    timezone_name TEXT NOT NULL,
    utc_offset_started_minutes INTEGER NOT NULL,
    duration_seconds INTEGER NOT NULL DEFAULT 0 CHECK (duration_seconds >= 0),
    counts_as_focus INTEGER NOT NULL CHECK (counts_as_focus IN (0, 1)),
    pause_classification TEXT NOT NULL CHECK (pause_classification IN (
        'none', 'short_grace_pause', 'continuity_break', 'system_sleep'
    )),
    breaks_continuity INTEGER NOT NULL CHECK (breaks_continuity IN (0, 1)),
    continuity_group_id TEXT,
    pause_grace_threshold_seconds INTEGER NOT NULL DEFAULT 10
        CHECK (pause_grace_threshold_seconds >= 0),
    focus_phase TEXT NOT NULL CHECK (focus_phase IN ('planned', 'overtime', 'not_applicable')),
    end_reason TEXT,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
    FOREIGN KEY (device_id) REFERENCES devices(device_id),
    UNIQUE (session_id, segment_sequence)
);

CREATE TABLE IF NOT EXISTS distractions (
    distraction_id TEXT PRIMARY KEY,
    schema_version INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    segment_id TEXT,
    device_id TEXT NOT NULL,
    marked_at_utc TEXT NOT NULL,
    marked_at_local TEXT NOT NULL,
    local_date TEXT NOT NULL,
    timezone_name TEXT NOT NULL,
    category_id TEXT NOT NULL,
    category_name_snapshot TEXT NOT NULL,
    elapsed_focus_seconds INTEGER NOT NULL CHECK (elapsed_focus_seconds >= 0),
    remaining_planned_seconds INTEGER NOT NULL CHECK (remaining_planned_seconds >= 0),
    is_overtime INTEGER NOT NULL CHECK (is_overtime IN (0, 1)),
    optional_note TEXT,
    created_at_utc TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
    FOREIGN KEY (segment_id) REFERENCES segments(segment_id),
    FOREIGN KEY (device_id) REFERENCES devices(device_id),
    FOREIGN KEY (category_id) REFERENCES categories(category_id)
);

-- Runtime-only recovery state. temporary_intention_text must be deleted when a
-- session is finalized and must never be exported to portable data.
CREATE TABLE IF NOT EXISTS runtime_session_state (
    session_id TEXT PRIMARY KEY,
    timer_state TEXT NOT NULL,
    temporary_intention_text TEXT,
    remaining_planned_seconds INTEGER NOT NULL CHECK (remaining_planned_seconds >= 0),
    is_overtime INTEGER NOT NULL CHECK (is_overtime IN (0, 1)),
    last_heartbeat_at_utc TEXT,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE TABLE IF NOT EXISTS sync_ledger (
    record_type TEXT NOT NULL,
    record_id TEXT NOT NULL,
    partition_relative_path TEXT NOT NULL,
    record_checksum TEXT NOT NULL,
    exported_at_utc TEXT NOT NULL,
    PRIMARY KEY (record_type, record_id)
);

CREATE INDEX IF NOT EXISTS ix_sessions_local_date ON sessions(local_date_started);
CREATE INDEX IF NOT EXISTS ix_sessions_category ON sessions(category_id);
CREATE INDEX IF NOT EXISTS ix_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS ix_sessions_started ON sessions(started_at_utc);
CREATE INDEX IF NOT EXISTS ix_segments_session ON segments(session_id);
CREATE INDEX IF NOT EXISTS ix_segments_started ON segments(started_at_utc);
CREATE INDEX IF NOT EXISTS ix_distractions_session ON distractions(session_id);
CREATE INDEX IF NOT EXISTS ix_distractions_local_date ON distractions(local_date);
CREATE INDEX IF NOT EXISTS ix_distractions_category ON distractions(category_id);
CREATE INDEX IF NOT EXISTS ix_distractions_marked ON distractions(marked_at_utc);
CREATE INDEX IF NOT EXISTS ix_daily_goals_dates
    ON daily_goals(effective_from_date, effective_to_date);
