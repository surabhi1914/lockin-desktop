"""UI-facing manual/automatic sync status and previous-day verification."""

import sqlite3
from datetime import date, timedelta

from PySide6.QtCore import QObject, QTimer, Signal

from app.models.portable_sync import PortableSyncResult, PortableVerificationReport
from app.services.portable_sync_service import PortableSyncService
from app.services.portable_verification_service import PortableVerificationService


class PortableSyncCoordinator(QObject):
    status_changed = Signal()

    def __init__(
        self,
        connection: sqlite3.Connection,
        sync_service: PortableSyncService,
        verifier: PortableVerificationService,
    ) -> None:
        super().__init__()
        self._connection = connection
        self._sync = sync_service
        self._verifier = verifier
        self.last_result: PortableSyncResult | None = None
        self.last_verification: PortableVerificationReport | None = None
        self._observed_day = date.today()
        self._day_timer = QTimer(self)
        self._day_timer.setInterval(60_000)
        self._day_timer.timeout.connect(self._check_day_rollover)
        self._startup_timer = QTimer(self)
        self._startup_timer.setSingleShot(True)
        self._startup_timer.timeout.connect(self.verify_previous_day)

    def start(self) -> None:
        self._day_timer.start()
        self._startup_timer.start(0)

    def stop(self) -> None:
        self._day_timer.stop()
        self._startup_timer.stop()

    @property
    def pending(self) -> bool:
        return self.last_result is not None and not self.last_result.success

    def sync_all(self) -> PortableSyncResult:
        self.last_result = self._sync.sync_all()
        self.status_changed.emit()
        return self.last_result

    def sync_session(self, session_id: str) -> tuple[bool, str]:
        self.last_result = self._sync.sync_session(session_id)
        self.status_changed.emit()
        return self.last_result.success, self.last_result.message

    def verify_previous_day(
        self, today: date | None = None, *, repair: bool = True
    ) -> PortableVerificationReport:
        target = (today or date.today()) - timedelta(days=1)
        report = self._verifier.verify(local_date=target.isoformat())
        if repair and not report.healthy:
            self.last_result = self._sync.sync_all()
            report = self._verifier.verify(local_date=target.isoformat())
        self.last_verification = report
        self._connection.execute(
            """
            INSERT INTO app_metadata(key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (f"portable_verification/{target.isoformat()}", "ok" if report.healthy else "pending"),
        )
        self._connection.commit()
        self.status_changed.emit()
        return report

    def _check_day_rollover(self) -> None:
        today = date.today()
        if today != self._observed_day:
            self._observed_day = today
            self.verify_previous_day(today)
