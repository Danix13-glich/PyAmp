"""Etiqueta de carátula cuadrada para la UI (Fase 3).

Muestra la carátula del álbum/pista en la fila de información. Sin
carátula (o con archivo ilegible) muestra un placeholder con borde
redondeado. El escalado es suave (SmoothTransformation) y la lectura es
un único QPixmap local — nunca bloquea la UI.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QWidget

#: Lado del cuadrado en píxeles.
COVER_SIZE_PX = 64

_PLACEHOLDER_TEXT = "♪"
_STYLE = "QLabel { border: 1px solid rgba(120,120,120,160); border-radius: 4px; }"


class CoverLabel(QLabel):
    """Carátula escalada a un cuadrado fijo; placeholder si no hay."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(COVER_SIZE_PX, COVER_SIZE_PX)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setToolTip("Carátula")
        self.setStyleSheet(_STYLE)
        self.clear_cover()

    def clear_cover(self) -> None:
        """Vuelve al placeholder (borde + nota musical)."""
        self.setPixmap(QPixmap())
        self.setText(_PLACEHOLDER_TEXT)

    def set_cover(self, path: str | Path | None) -> None:
        """Carga y escala la carátula; placeholder si no hay o es ilegible."""
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
