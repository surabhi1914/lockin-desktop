from app.recovery.gap_detector import GapDetector
from app.recovery.sleep_detector import PowerEvent, PowerEventSource, SleepDetector
from app.recovery.windows_power_event_filter import (
    PBT_APMRESUMEAUTOMATIC,
    PBT_APMRESUMESUSPEND,
    PBT_APMSUSPEND,
    _power_event,
)


def test_gap_detector_requires_recovery_only_above_threshold() -> None:
    detector = GapDetector(15)
    assert not detector.assess(
        wall_progress_seconds=10,
        monotonic_progress_seconds=10,
        heartbeat_age_seconds=15,
    ).recovery_required
    gap = detector.assess(
        wall_progress_seconds=40,
        monotonic_progress_seconds=10,
        heartbeat_age_seconds=20,
    )
    assert gap.recovery_required and gap.unexplained_gap_seconds == 30


def test_sleep_detector_deduplicates_suspend_and_resume(qapp) -> None:
    source = PowerEventSource()
    detector = SleepDetector(source)
    events: list[str] = []
    detector.suspended.connect(lambda: events.append("suspend"))
    detector.resumed.connect(lambda: events.append("resume"))
    source.emit_event(PowerEvent.SUSPEND)
    source.emit_event(PowerEvent.SUSPEND)
    source.emit_event(PowerEvent.RESUME_AUTOMATIC)
    source.emit_event(PowerEvent.RESUME_USER)
    assert events == ["suspend", "resume"]
    assert not detector.is_suspended


def test_windows_power_constants_map_without_native_polling() -> None:
    assert _power_event(PBT_APMSUSPEND) is PowerEvent.SUSPEND
    assert _power_event(PBT_APMRESUMEAUTOMATIC) is PowerEvent.RESUME_AUTOMATIC
    assert _power_event(PBT_APMRESUMESUSPEND) is PowerEvent.RESUME_USER
    assert _power_event(999) is None
