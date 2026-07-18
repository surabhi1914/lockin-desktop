from app.recovery.sleep_detector import PowerEvent
from app.recovery.windows_power_event_filter import (
    PBT_APMRESUMEAUTOMATIC,
    PBT_APMRESUMESUSPEND,
    PBT_APMSUSPEND,
    _power_event,
)


def test_native_power_values_have_explicit_platform_neutral_meanings() -> None:
    assert _power_event(PBT_APMSUSPEND) is PowerEvent.SUSPEND
    assert _power_event(PBT_APMRESUMEAUTOMATIC) is PowerEvent.RESUME_AUTOMATIC
    assert _power_event(PBT_APMRESUMESUSPEND) is PowerEvent.RESUME_USER
    assert _power_event(-1) is None
