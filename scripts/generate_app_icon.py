"""Generate the original LockIn focus-ring/L icon deterministically."""

import struct
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication

SIZES = (16, 24, 32, 48, 64, 128, 256)


def _image(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(QColor("#101522"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    margin = size * 0.12
    width = max(2.0, size * 0.09)
    painter.setPen(QPen(QColor("#7b8cff"), width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawEllipse(QRectF(margin, margin, size - 2 * margin, size - 2 * margin))
    path = QPainterPath()
    path.moveTo(size * 0.43, size * 0.29)
    path.lineTo(size * 0.43, size * 0.66)
    path.lineTo(size * 0.68, size * 0.66)
    painter.setPen(QPen(QColor("#f4f6ff"), width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawPath(path)
    painter.end()
    return image


def _png_bytes(image: QImage) -> bytes:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):  # type: ignore[call-overload]
        raise RuntimeError("Qt could not encode the LockIn icon")
    return bytes(data.data())


def generate(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    images = [(size, _png_bytes(_image(size))) for size in SIZES]
    if not _image(256).save(str(output / "lockin.png"), "PNG"):  # type: ignore[call-overload]
        raise RuntimeError("Qt could not save lockin.png")
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries: list[bytes] = []
    payload = bytearray()
    for size, data in images:
        dimension = 0 if size == 256 else size
        entries.append(
            struct.pack("<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(data), offset)
        )
        payload.extend(data)
        offset += len(data)
    (output / "lockin.ico").write_bytes(header + b"".join(entries) + payload)


def main() -> int:
    application = QApplication.instance() or QApplication(["lockin-icon-generator"])
    generate(Path(__file__).resolve().parents[1] / "app" / "assets" / "icons")
    if isinstance(application, QApplication):
        application.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
