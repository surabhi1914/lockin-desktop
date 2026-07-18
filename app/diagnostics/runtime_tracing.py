"""Opt-in process-launch and transient Qt-window diagnostics for development."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import traceback
from datetime import UTC, datetime
from time import monotonic_ns
from typing import Any, ClassVar

from PySide6.QtCore import QEvent, QObject, QProcess, Qt, QTimer
from PySide6.QtWidgets import QApplication, QWidget

PROCESS_TRACE_ENV = "LOCKIN_TRACE_PROCESS_LAUNCHES"
WINDOW_TRACE_ENV = "LOCKIN_TRACE_TRANSIENT_WINDOWS"

_process_tracing_installed = False
_window_tracer: TransientWindowTracer | None = None


def install_process_launch_tracing() -> None:
    """Trace runtime process-launch APIs when explicitly enabled."""
    global _process_tracing_installed
    if _process_tracing_installed or os.environ.get(PROCESS_TRACE_ENV) != "1":
        return
    _process_tracing_installed = True

    class TracingPopen(subprocess.Popen[Any]):
        def __init__(self, args: Any, *positional: Any, **keywords: Any) -> None:
            _trace_process("subprocess.Popen", args, keywords)
            super().__init__(args, *positional, **keywords)

    subprocess.Popen = TracingPopen  # type: ignore[misc]

    original_system = os.system

    def traced_system(command: Any) -> int:
        _trace_process("os.system", command, {})
        return original_system(command)

    os.system = traced_system
    original_startfile = getattr(os, "startfile", None)
    if original_startfile is not None:

        def traced_startfile(path: Any, *positional: Any, **keywords: Any) -> Any:
            _trace_process("os.startfile", path, keywords)
            return original_startfile(path, *positional, **keywords)

        os.startfile = traced_startfile  # type: ignore[assignment]

    original_qprocess_start = QProcess.start

    def traced_qprocess_start(self: QProcess, *args: Any, **kwargs: Any) -> Any:
        _trace_process("QProcess.start", args, kwargs)
        return original_qprocess_start(self, *args, **kwargs)

    QProcess.start = traced_qprocess_start  # type: ignore[method-assign]
    original_qprocess_detached = QProcess.startDetached

    def traced_qprocess_detached(*args: Any, **kwargs: Any) -> Any:
        _trace_process("QProcess.startDetached", args, kwargs)
        return original_qprocess_detached(*args, **kwargs)

    QProcess.startDetached = traced_qprocess_detached  # type: ignore[method-assign]


def install_transient_window_tracing(application: QApplication) -> None:
    """Install the opt-in top-level widget lifecycle event filter once."""
    global _window_tracer
    if _window_tracer is not None or os.environ.get(WINDOW_TRACE_ENV) != "1":
        return
    _window_tracer = TransientWindowTracer(application)
    application.installEventFilter(_window_tracer)


class TransientWindowTracer(QObject):
    """Trace unexpected top-level widget lifetimes without changing UI behavior."""

    _EVENT_NAMES: ClassVar[dict[QEvent.Type, str]] = {
        QEvent.Type.Show: "Show",
        QEvent.Type.ShowToParent: "ShowToParent",
        QEvent.Type.Hide: "Hide",
        QEvent.Type.HideToParent: "HideToParent",
        QEvent.Type.Close: "Close",
        QEvent.Type.Destroy: "Destroy",
        QEvent.Type.WindowActivate: "WindowActivate",
        QEvent.Type.WindowDeactivate: "WindowDeactivate",
        QEvent.Type.Polish: "Polish",
        QEvent.Type.ParentChange: "ParentChange",
        QEvent.Type.WinIdChange: "WinIdChange",
        QEvent.Type.FocusIn: "FocusIn",
        QEvent.Type.FocusOut: "FocusOut",
    }

    def __init__(self, application: QApplication) -> None:
        super().__init__(application)
        self._application = application
        self._shown_at: dict[int, int] = {}

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        event_type = event.type()
        if event_type == QEvent.Type.MouseButtonPress:
            QTimer.singleShot(0, self._trace_top_levels_after_press)
        if isinstance(watched, QWidget) and event_type in self._EVENT_NAMES:
            is_top_level = watched.isWindow() or watched.parentWidget() is None
            if is_top_level:
                self._trace_widget(watched, self._EVENT_NAMES[event_type], event_type)
        return False

    def _trace_widget(self, widget: QWidget, event_name: str, event_type: QEvent.Type) -> None:
        identity = id(widget)
        now = monotonic_ns()
        lifetime_ms: float | None = None
        if event_type in (QEvent.Type.Show, QEvent.Type.ShowToParent):
            self._shown_at[identity] = now
        elif event_type in (
            QEvent.Type.Hide,
            QEvent.Type.HideToParent,
            QEvent.Type.Close,
            QEvent.Type.Destroy,
        ):
            shown = self._shown_at.pop(identity, None)
            if shown is not None:
                lifetime_ms = (now - shown) / 1_000_000
        record = {
            "trace": "qt-window",
            "timestamp": _timestamp(),
            "event": event_name,
            **_widget_details(widget),
            "lifetime_ms": lifetime_ms,
            "active_window": _widget_identity(self._application.activeWindow()),
            "active_popup": _widget_identity(self._application.activePopupWidget()),
            "active_modal": _widget_identity(self._application.activeModalWidget()),
        }
        if event_type in (QEvent.Type.Show, QEvent.Type.ShowToParent):
            record["stack"] = _short_stack()
        _write(record)

    def _trace_top_levels_after_press(self) -> None:
        _write(
            {
                "trace": "qt-top-levels-after-mouse-press",
                "timestamp": _timestamp(),
                "widgets": [
                    _widget_details(widget)
                    for widget in QApplication.topLevelWidgets()
                    if widget.isVisible()
                ],
            }
        )


def _trace_process(api: str, command: Any, options: dict[str, Any]) -> None:
    flags = options.get("creationflags", 0)
    _write(
        {
            "trace": "process-launch",
            "timestamp": _timestamp(),
            "api": api,
            "command": _safe_command(command),
            "creationflags": int(flags) if isinstance(flags, int) else str(flags),
            "shell": bool(options.get("shell", False)),
            "classification": "unexpected",
            "stack": _short_stack(),
        }
    )


def _widget_details(widget: QWidget) -> dict[str, Any]:
    parent = widget.parentWidget()
    geometry = widget.geometry()
    native_id: int | None = None
    if widget.testAttribute(Qt.WidgetAttribute.WA_WState_Created):
        native_id = int(widget.winId())
    return {
        "class": type(widget).__name__,
        "object_name": widget.objectName(),
        "title": widget.windowTitle(),
        "parent": _widget_identity(parent),
        "window_flags": int(widget.windowFlags()),
        "modality": widget.windowModality().name,
        "geometry": [geometry.x(), geometry.y(), geometry.width(), geometry.height()],
        "visible": widget.isVisible(),
        "native_id": native_id,
    }


def _widget_identity(widget: QWidget | None) -> str | None:
    if widget is None:
        return None
    return f"{type(widget).__name__}:{widget.objectName() or widget.windowTitle()}"


def _safe_command(command: Any) -> list[str]:
    if isinstance(command, (str, bytes, os.PathLike)):
        return [str(command)]
    try:
        return [str(part) for part in command]
    except TypeError:
        return [f"<{type(command).__name__}>"]


def _short_stack() -> list[str]:
    frames: list[str] = []
    for frame in traceback.extract_stack(limit=20)[:-2]:
        normalized = frame.filename.replace("\\", "/")
        marker = "/app/"
        if marker not in normalized:
            continue
        relative = "app/" + normalized.split(marker, 1)[1]
        frames.append(f"{relative}:{frame.lineno}:{frame.name}")
    return frames[-6:]


def _safe_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    except (TypeError, ValueError):
        return json.dumps(str(value), ensure_ascii=True)


def _write(record: dict[str, Any]) -> None:
    print(_safe_json(record), file=sys.stderr, flush=True)


def _timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
