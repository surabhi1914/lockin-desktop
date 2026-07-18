"""Theme-independent visual primitives for the dedicated focus surface."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QWidget


def enforce_black_background(widget: QWidget) -> None:
    """Make a focus surface paint true black regardless of application QSS."""
    palette = QPalette(widget.palette())
    palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Base, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    widget.setPalette(palette)
    widget.setAutoFillBackground(True)
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
