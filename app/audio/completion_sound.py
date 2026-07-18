"""Fail-soft, once-per-session completion sound playback."""

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QSoundEffect

from app.services.settings_service import SettingsService


class SoundBackend(Protocol):
    def play(self, asset: Path, volume: float) -> None: ...


class QtSoundBackend:
    def __init__(self) -> None:
        self._effect = QSoundEffect()

    def play(self, asset: Path, volume: float) -> None:
        self._effect.stop()
        self._effect.setSource(QUrl.fromLocalFile(str(asset)))
        self._effect.setVolume(max(0.0, min(1.0, volume)))
        self._effect.play()


class CompletionSoundService:
    def __init__(
        self,
        settings: SettingsService,
        asset: Path,
        *,
        backend_factory: Callable[[], SoundBackend] = QtSoundBackend,
    ) -> None:
        self._settings = settings
        self._asset = asset
        self._backend_factory = backend_factory
        self._backend: SoundBackend | None = None
        self._played = False

    def begin_session(self) -> None:
        self._played = False

    def play_planned_completion(self, *, session_enabled: bool) -> bool:
        if self._played:
            return False
        self._played = True
        if (
            not session_enabled
            or not self._settings.completion_sound_enabled()
            or self._settings.completion_sound_volume() == 0
            or not self._asset.is_file()
        ):
            return False
        return self._play()

    def preview(self) -> bool:
        if not self._asset.is_file() or self._settings.completion_sound_volume() == 0:
            return False
        return self._play()

    def _play(self) -> bool:
        try:
            if self._backend is None:
                self._backend = self._backend_factory()
            self._backend.play(self._asset, self._settings.completion_sound_volume() / 100.0)
            return True
        except (OSError, RuntimeError, ValueError):
            return False
