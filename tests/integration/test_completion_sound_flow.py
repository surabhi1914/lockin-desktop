from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from app.audio.completion_sound import CompletionSoundService
from app.services.settings_service import SettingsService
from tests.phase4_helpers import build_phase4_harness, focus_draft


class RecordingBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, float]] = []

    def play(self, asset: Path, volume: float) -> None:
        self.calls.append((asset, volume))


def test_enabled_session_plays_sound_once_at_planned_completion(
    qapp: QApplication, tmp_path: Path
) -> None:
    asset = tmp_path / "completion.wav"
    asset.write_bytes(b"RIFF-test")
    settings = SettingsService(
        QSettings(str(tmp_path / "sound-settings.ini"), QSettings.Format.IniFormat)
    )
    settings.set_completion_sound_volume(45)
    backend = RecordingBackend()
    sound = CompletionSoundService(settings, asset, backend_factory=lambda: backend)
    harness = build_phase4_harness(qapp, tmp_path, completion_sound=sound)
    try:
        harness.service.start_focus(focus_draft(harness, duration=10, sound=True))
        harness.clock.advance_seconds(10)
        harness.coordinator.adapter.poll_once()
        harness.coordinator.adapter.poll_once()
        assert backend.calls == [(asset, 0.45)]
    finally:
        harness.close()
