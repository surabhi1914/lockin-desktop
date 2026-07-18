ALTER TABLE runtime_session_state
    ADD COLUMN confirmed_planned_focus_seconds INTEGER NOT NULL DEFAULT 0
    CHECK (confirmed_planned_focus_seconds >= 0);

ALTER TABLE runtime_session_state
    ADD COLUMN confirmed_overtime_seconds INTEGER NOT NULL DEFAULT 0
    CHECK (confirmed_overtime_seconds >= 0);

ALTER TABLE runtime_session_state
    ADD COLUMN confirmed_pause_seconds INTEGER NOT NULL DEFAULT 0
    CHECK (confirmed_pause_seconds >= 0);

ALTER TABLE runtime_session_state
    ADD COLUMN confirmed_wall_clock_seconds INTEGER NOT NULL DEFAULT 0
    CHECK (confirmed_wall_clock_seconds >= 0);

ALTER TABLE runtime_session_state
    ADD COLUMN sleep_started_at_utc TEXT;

CREATE TABLE IF NOT EXISTS recovery_events (
    recovery_event_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    detected_at_utc TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (
        event_type IN (
            'crash', 'forced_termination', 'power_loss', 'os_restart',
            'missed_suspend', 'system_sleep', 'runtime_mismatch',
            'completed_not_finalized', 'overtime_interrupted', 'paused_interrupted'
        )
    ),
    last_heartbeat_at_utc TEXT,
    confirmed_boundary_at_utc TEXT NOT NULL,
    unknown_gap_seconds INTEGER NOT NULL CHECK (unknown_gap_seconds >= 0),
    selected_action TEXT CHECK (
        selected_action IS NULL OR selected_action IN (
            'save_confirmed', 'discard', 'resume_after_sleep',
            'stop_after_sleep', 'auto_pause'
        )
    ),
    finalized_at_utc TEXT,
    original_timer_state TEXT NOT NULL,
    integrity_result TEXT NOT NULL,
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE INDEX IF NOT EXISTS ix_recovery_events_session
    ON recovery_events(session_id, detected_at_utc);

CREATE INDEX IF NOT EXISTS ix_segments_local_allocation
    ON segments(started_at_utc, ended_at_utc, segment_type, focus_phase);

CREATE INDEX IF NOT EXISTS ix_sessions_analytics_range
    ON sessions(status, local_date_started, category_id, device_id);

CREATE INDEX IF NOT EXISTS ix_distractions_analytics_range
    ON distractions(local_date, session_id, category_id);
