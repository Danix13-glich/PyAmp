from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr

#: Color del recuadro según la posición (1.º, 2.º, 3.º y el resto).
MEDAL_COLORS = ("#d4af37", "#c0c0c0", "#cd7f32")
REST_COLOR = "#8a8a8a"

NOT_READY_TEXT = "Aún no está listo :/"


def _entry_title(entry: dict[str, object]) -> str:
    title = str(entry.get("title") or "").strip()
    if title:
        return title
    path = str(entry.get("path") or "")
    return Path(path).stem or tr("Sin título")


def _entry_artist(entry: dict[str, object]) -> str:
    artist = str(entry.get("artist") or "").strip()
    return artist or tr("Artista desconocido")


class HistoryWindow(QDialog):

    def __init__(
        self,
        entries: list[dict[str, object]] | None = None,
        *,
        ready: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Historial — PyAmp"))
        self.setModal(True)
        self.resize(460, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        title = QLabel(tr("Las 10 canciones más escuchadas"))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        rows = list(entries or []) if ready else []
        if not rows:
            placeholder = QLabel(tr(NOT_READY_TEXT))
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setWordWrap(True)
            layout.addStretch(1)
            layout.addWidget(placeholder)
            layout.addStretch(1)
        else:
            for index, entry in enumerate(rows[:10]):
                layout.addWidget(self._build_row(index, entry))
            layout.addStretch(1)

        close = QPushButton(tr("Cerrar"))
        close.clicked.connect(self.accept)
        layout.addWidget(close)

    def _build_row(self, index: int, entry: dict[str, object]) -> QFrame:
        color = MEDAL_COLORS[index] if index < len(MEDAL_COLORS) else REST_COLOR
        text_color = "#101014" if index < len(MEDAL_COLORS) else "#ffffff"
        frame = QFrame()
        frame.setObjectName("historyRow")
        frame.setStyleSheet(
            f"QFrame#historyRow {{ background-color: {color};"
            f" border-radius: 6px; padding: 6px; }}"
        )
        row = QVBoxLayout(frame)
        row.setContentsMargins(8, 4, 8, 4)
        raw_count = entry.get("count")
        count = raw_count if isinstance(raw_count, int) else 0
        label = QLabel(
            tr("{rank}. {title} — {artist}  ({count}×)").format(
                rank=index + 1,
                title=_entry_title(entry),
                artist=_entry_artist(entry),
                count=count,
            )
        )
        label.setStyleSheet(f"color: {text_color};")
        label.setWordWrap(True)
        row.addWidget(label)
        return frame
