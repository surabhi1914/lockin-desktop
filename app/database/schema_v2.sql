ALTER TABLE runtime_session_state
    ADD COLUMN timer_version INTEGER NOT NULL DEFAULT 0
    CHECK (timer_version >= 0);

CREATE UNIQUE INDEX IF NOT EXISTS ux_segments_one_open_per_session
    ON segments(session_id)
    WHERE ended_at_utc IS NULL;
