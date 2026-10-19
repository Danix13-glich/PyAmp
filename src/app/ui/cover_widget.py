from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QWidget

from app.i18n import tr

#: Lado del cuadrado en píxeles.
COVER_SIZE_PX = 64

_PLACEHOLDER_TEXT = "♪"
_STYLE = "QLabel { border: 1px solid rgba(120,120,120,160); border-radius: 4px; }"


def station_initials(name: str) -> str:
    words = [word for word in str(name).split() if word]
    if not words:
        return "R"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][:1] + words[1][:1]).upper()


def station_badge(name: str, size: int, accent: str, text_color: str) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(accent))
    painter.setPen(Qt.PenStyle.NoPen)
    radius = max(6, size // 8)
    painter.drawRoundedRect(QRect(0, 0, size, size), radius, radius)
    painter.setPen(QColor(text_color))
    font = QFont()
    font.setPixelSize(max(10, int(size * 0.42)))
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, station_initials(name))
    painter.end()
    return pixmap


class CoverLabel(QLabel):

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(COVER_SIZE_PX, COVER_SIZE_PX)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setToolTip(tr("Carátula"))
        self.setStyleSheet(_STYLE)
        self.clear_cover()

    def clear_cover(self) -> None:
        self.setPixmap(QPixmap())
        self.setText(_PLACEHOLDER_TEXT)

    def set_cover(self, path: str | Path | None) -> None:
        if not path:
            self.clear_cover()
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.clear_cover()
            return
        scaled = pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setText("")
        self.setPixmap(scaled)

    def set_station_badge(self, name: str, accent: str, text_color: str) -> None:
        self.setText("")
        self.setToolTip(name)
        self.setPixmap(station_badge(name, COVER_SIZE_PX, accent, text_color))
