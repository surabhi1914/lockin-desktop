from dataclasses import replace

from app.services.heartbeat_service import HeartbeatService
from app.timer import ManualClock, TimerConfig, TimerEngine


class PersistenceStub:
    def __init__(self, results: list[bool | Exception]) -> None:
        self.results = results

    def heartbeat(self, _snapshot):
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def test_heartbeat_reports_change_and_repeated_failures(qtbot: object) -> None:
    clock = ManualClock()
    engine = TimerEngine(TimerConfig(10), clock)
    snapshot = engine.start()
    stub = PersistenceStub([True, RuntimeError("disk"), RuntimeError("disk"), RuntimeError("disk")])
    heartbeat = HeartbeatService(  # type: ignore[arg-type]
        stub, lambda: replace(snapshot), interval_ms=5000, failure_threshold=3
    )
    messages: list[str] = []
    heartbeat.repeated_failure.connect(messages.append)
    assert heartbeat.tick()
    assert not heartbeat.tick()
    assert not heartbeat.tick()
    assert not heartbeat.tick()
    assert messages == ["disk"]
    heartbeat.start()
    assert heartbeat.active
    heartbeat.stop()
    assert not heartbeat.active
