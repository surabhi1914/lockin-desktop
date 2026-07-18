from PySide6.QtCore import QSettings

from app.application import create_application
from app.models.focus_session_draft import FocusSessionDraft
from app.services.settings_service import SettingsService
from app.ui.pages.history_page import HistoryPage


def test_real_application_focus_flow_saves_locally_and_populates_recent_view(
    qapp,
    qtbot,
    isolated_config,
    tmp_path,
) -> None:
    settings = SettingsService(
        QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    )
    app_context = create_application(
        config=isolated_config,
        settings=settings,
        tray_available=False,
        show_window=False,
    )
    qtbot.addWidget(app_context.window)
    category = app_context.category_service.list_active()[0]
    draft = FocusSessionDraft(
        60,
        category.category_id,
        category.category_name,
        "private temporary text",
        False,
        False,
        False,
        True,
        False,
        10,
    )
    app_context.focus_experience_service.start_focus(draft)
    session_id = app_context.session_persistence_service.active_context.session_id
    runtime = app_context.connection.execute(
        "SELECT temporary_intention_text FROM runtime_session_state WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    assert runtime[0] is None
    assert app_context.focus_experience_service._stop_to_summary("manual_stop")
    summary = app_context.focus_experience_service.current_summary
    assert summary is not None and summary.saved_locally
    assert not app_context.focus_experience_service.has_active_session
    assert app_context.focus_experience.summary.values["saved"].text() == "Saved locally"
    session = app_context.session_persistence_service.sessions.get(session_id)
    assert session is not None
    assert session.status == "stopped_early"
    assert session.completion_reason == "manual_stop"
    assert app_context.session_persistence_service.runtime.get(session_id) is None
    page = app_context.window.page("history")
    assert isinstance(page, HistoryPage)
    page.refresh()
    assert page.table.rowCount() == 1
    assert page.table.item(0, 1).text() == category.category_name
    app_context.focus_experience_service.return_to_setup()
    app_context.shutdown()


def test_unfinished_session_restart_is_read_only_and_blocks_new_focus(
    qapp,
    qtbot,
    isolated_config,
    tmp_path,
) -> None:
    settings = SettingsService(
        QSettings(str(tmp_path / "restart-settings.ini"), QSettings.Format.IniFormat)
    )
    first = create_application(
        config=isolated_config, settings=settings, tray_available=False, show_window=False
    )
    category = first.category_service.list_active()[0]
    timestamp = "2026-07-16T16:00:00Z"
    local = "2026-07-16T12:00:00-04:00"
    session_id = "11111111-1111-4111-8111-111111111111"
    first.connection.execute(
        """
        INSERT INTO sessions (
          session_id, schema_version, device_id, session_sequence, category_id,
          category_name_snapshot, local_date_started, timezone_name,
          utc_offset_started_minutes, started_at_utc, started_at_local,
          planned_focus_seconds, status, created_at_utc, updated_at_utc
        ) VALUES (?, 1, ?, 1, ?, ?, '2026-07-16', 'America/Detroit', -240,
                  ?, ?, 60, 'running', ?, ?)
        """,
        (
            session_id,
            first.device_id,
            category.category_id,
            category.category_name,
            timestamp,
            local,
            timestamp,
            timestamp,
        ),
    )
    first.connection.execute(
        """
        INSERT INTO runtime_session_state (
          session_id, timer_state, temporary_intention_text, remaining_planned_seconds,
          is_overtime, last_heartbeat_at_utc, updated_at_utc, timer_version
        ) VALUES (?, 'running', NULL, 55, 0, ?, ?, 4)
        """,
        (session_id, timestamp, timestamp),
    )
    first.connection.commit()
    first.shutdown()

    restarted = create_application(
        config=isolated_config, settings=settings, tray_available=False, show_window=False
    )
    qtbot.addWidget(restarted.window)
    assert [item.session_id for item in restarted.unfinished_sessions] == [session_id]
    draft = FocusSessionDraft(
        60,
        category.category_id,
        category.category_name,
        "still private",
        False,
        False,
        False,
        True,
        False,
        10,
    )
    restarted.focus_experience_service.start_focus(draft)
    assert restarted.connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1
    assert (
        restarted.connection.execute("SELECT COUNT(*) FROM runtime_session_state").fetchone()[0]
        == 1
    )
    assert "unfinished" in restarted.window.page("focus_setup").form_validation.text().lower()
    restarted.shutdown()
