-- Phase 11 cache invalidation and database-level daily-goal overlap protection.
INSERT INTO app_metadata(key, value) VALUES ('analytics_revision', '0')
ON CONFLICT(key) DO NOTHING;

CREATE TRIGGER IF NOT EXISTS trg_daily_goals_no_overlap_insert
BEFORE INSERT ON daily_goals
WHEN EXISTS (
    SELECT 1 FROM daily_goals existing
    WHERE COALESCE(existing.effective_to_date, '9999-12-31') >= NEW.effective_from_date
      AND COALESCE(NEW.effective_to_date, '9999-12-31') >= existing.effective_from_date
)
BEGIN
    SELECT RAISE(ABORT, 'daily goal effective ranges overlap');
END;

CREATE TRIGGER IF NOT EXISTS trg_daily_goals_no_overlap_update
BEFORE UPDATE OF effective_from_date, effective_to_date ON daily_goals
WHEN EXISTS (
    SELECT 1 FROM daily_goals existing
    WHERE existing.goal_id != NEW.goal_id
      AND COALESCE(existing.effective_to_date, '9999-12-31') >= NEW.effective_from_date
      AND COALESCE(NEW.effective_to_date, '9999-12-31') >= existing.effective_from_date
)
BEGIN
    SELECT RAISE(ABORT, 'daily goal effective ranges overlap');
END;

CREATE TRIGGER IF NOT EXISTS trg_analytics_sessions_insert
AFTER INSERT ON sessions BEGIN
    UPDATE app_metadata SET value = CAST(value AS INTEGER) + 1 WHERE key='analytics_revision';
END;
CREATE TRIGGER IF NOT EXISTS trg_analytics_sessions_update
AFTER UPDATE ON sessions BEGIN
    UPDATE app_metadata SET value = CAST(value AS INTEGER) + 1 WHERE key='analytics_revision';
END;
CREATE TRIGGER IF NOT EXISTS trg_analytics_sessions_delete
AFTER DELETE ON sessions BEGIN
    UPDATE app_metadata SET value = CAST(value AS INTEGER) + 1 WHERE key='analytics_revision';
END;
CREATE TRIGGER IF NOT EXISTS trg_analytics_segments_insert
AFTER INSERT ON segments BEGIN
    UPDATE app_metadata SET value = CAST(value AS INTEGER) + 1 WHERE key='analytics_revision';
END;
CREATE TRIGGER IF NOT EXISTS trg_analytics_segments_update
AFTER UPDATE ON segments BEGIN
    UPDATE app_metadata SET value = CAST(value AS INTEGER) + 1 WHERE key='analytics_revision';
END;
CREATE TRIGGER IF NOT EXISTS trg_analytics_segments_delete
AFTER DELETE ON segments BEGIN
    UPDATE app_metadata SET value = CAST(value AS INTEGER) + 1 WHERE key='analytics_revision';
END;
CREATE TRIGGER IF NOT EXISTS trg_analytics_distractions_insert
AFTER INSERT ON distractions BEGIN
    UPDATE app_metadata SET value = CAST(value AS INTEGER) + 1 WHERE key='analytics_revision';
END;
CREATE TRIGGER IF NOT EXISTS trg_analytics_distractions_delete
AFTER DELETE ON distractions BEGIN
    UPDATE app_metadata SET value = CAST(value AS INTEGER) + 1 WHERE key='analytics_revision';
END;
CREATE TRIGGER IF NOT EXISTS trg_analytics_goals_insert
AFTER INSERT ON daily_goals BEGIN
    UPDATE app_metadata SET value = CAST(value AS INTEGER) + 1 WHERE key='analytics_revision';
END;
CREATE TRIGGER IF NOT EXISTS trg_analytics_goals_update
AFTER UPDATE ON daily_goals BEGIN
    UPDATE app_metadata SET value = CAST(value AS INTEGER) + 1 WHERE key='analytics_revision';
END;
CREATE TRIGGER IF NOT EXISTS trg_analytics_goals_delete
AFTER DELETE ON daily_goals BEGIN
    UPDATE app_metadata SET value = CAST(value AS INTEGER) + 1 WHERE key='analytics_revision';
END;
