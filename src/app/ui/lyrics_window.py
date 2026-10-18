"""Ventana «Ver letra» (Fase 5): letras LRC locales sincronizadas.

Busca la letra en dos sitios, en este orden:

1. Junto al audio: ``cancion.lrc`` (mismo nombre y carpeta).
2. En la biblioteca de letras de la app: ``<datos>/PyAmp/lyrics/``.

Si no hay letra para la pista (o no hay pista), el panel muestra el
aviso centrado «Letra no disponible :(". La ventana es independiente
(``Qt.Window``), se sitúa junto a la principal y sigue la reproducción:
la línea que coincide con la posición actual se resalta en negrita azul.
Sin metadatos de red: solo archivos locales.
"""

from __future__ import annotations

import bisect
import logging
import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.library.models import Track
from app.utils.paths import LYRICS_DIR

logger = logging.getLogger(__name__)

#: Marcas de tiempo LRC: ``[mm:ss]``, ``[mm:ss.xx]`` o ``[mm:ss.xxx]``.
LRC_TIME_RE = re.compile(r"\[(\d{1,2}):(\d{1,2})(?:[.:](\d{1,3}))?\]")

WINDOW_TITLE_MIN = (260, 320)

#: Aviso centrado cuando la pista no tiene letra disponible.
PLACEHOLDER_TEXT = "Letra no disponible :("


def parse_lrc(text: str) -> list[tuple[int, str]]:
    """Convierte el contenido de un .lrc en ``(posición_ms, línea)``.

    Ignora metatags (``[ar:]``, ``[ti:]``...) y líneas sin marca de
    tiempo. Varias marcas sobre la misma línea generan varias entradas.
    La salida sale ordenada por posición.
    """
    entries: list[tuple[int, str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        times = LRC_TIME_RE.findall(line)
        if not times:
            continue  # metatag o texto sin sincronizar
        lyric = LRC_TIME_RE.sub("", line).strip()
        if not lyric:
            continue
        for minutes, seconds, fraction in times:
            frac_ms = int(fraction.ljust(3, "0")[:3]) if fraction else 0
            position_ms = int(minutes) * 60000 + int(seconds) * 1000 + frac_ms
            entries.append((position_ms, lyric))
    entries.sort(key=lambda entry: entry[0])
    return entries


def find_lrc_path(track_path: str) -> Path | None:
    """Ruta del .lrc de la pista (junto al audio o en la carpeta de letras)."""
    audio = Path(track_path)
    candidates = (audio.with_suffix(".lrc"), LYRICS_DIR / f"{audio.stem}.lrc")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


class LyricsWindow(QDialog):
    """Ventana de letra sincronizada con la reproducción (modeless).

    Como ``QDialog`` con la ventana principal como parent, el compositor
    (KDE/Wayland incluido) la sitúa junto a la principal.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setModal(False)
        self.setWindowTitle("Letra — PyAmp")
        self.setMinimumSize(*WINDOW_TITLE_MIN)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self._label_track = QLabel("—")
        title_font = self._label_track.font()
        title_font.setBold(True)
        self._label_track.setFont(title_font)
        self._label_track.setWordWrap(True)
        layout.addWidget(self._label_track)

        self._list = QListWidget()
        self._list.setWordWrap(True)
        self._list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self._list, stretch=1)

        self._placeholder = QLabel(PLACEHOLDER_TEXT)
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setWordWrap(True)
        placeholder_font = QFont(self._placeholder.font())
        placeholder_font.setPointSize(placeholder_font.pointSize() + 1)
        self._placeholder.setFont(placeholder_font)
        self._placeholder.setStyleSheet("color: #9e9ea6;")
        layout.addWidget(self._placeholder, stretch=1)
        self._placeholder.hide()

        self._status = QLabel("")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        self._entries: list[tuple[int, str]] = []
        self._times: list[int] = []
        self._active_row = -1
        self._base_font = self._list.font()
        self._active_font = QFont(self._base_font)
        self._active_font.setBold(True)

    # ------------------------------------------------------------ API pública
    @property
    def entries(self) -> list[tuple[int, str]]:
        """Entradas LRC cargadas (posición_ms, línea)."""
        return list(self._entries)

    @property
    def active_row(self) -> int:
        """Índice de la línea resaltada (-1 si no hay ninguna)."""
        return self._active_row

    @property
    def showing_placeholder(self) -> bool:
        """True si se muestra el aviso «Letra no disponible :(» centrado."""
        return not self._placeholder.isHidden()

    def show_track(self, track: Track | None) -> None:
        """Carga (o limpia) la letra de la pista indicada."""
        self._entries = []
        self._times = []
        self._active_row = -1
        self._list.clear()
        self._set_placeholder(False)

        if track is None or not track.path:
            self._label_track.setText("—")
            self._status.setText("No hay ninguna pista en reproducción")
            self._set_placeholder(True)
            return

        self._label_track.setText(track.display_name)
        lrc_path = find_lrc_path(track.path)
        if lrc_path is None:
            stem = Path(track.path).stem
            self._status.setText(f"No encontré «{stem}.lrc» (junto al audio o en {LYRICS_DIR})")
            self._set_placeholder(True)
            return

        try:
            text = lrc_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.warning("No se pudo leer la letra %s: %s", lrc_path, exc)
            self._status.setText(f"No se pudo leer {lrc_path.name}: {exc}")
            self._set_placeholder(True)
            return

        self._entries = parse_lrc(text)
        if not self._entries:
            raw = text.strip()
            if not raw:
                self._status.setText(f"{lrc_path.name}: sin marcas de tiempo [mm:ss]")
                self._set_placeholder(True)
                return
            self._list.addItem(raw)
            self._status.setText(f"{lrc_path.name}: sin marcas de tiempo [mm:ss]")
            return

        self._status.setText(f"Letra: {lrc_path.name}")
        for _position_ms, lyric in self._entries:
            self._list.addItem(lyric)
        self._times = [position_ms for position_ms, _lyric in self._entries]

    def _set_placeholder(self, visible: bool) -> None:
        """Muestra el aviso centrado (y oculta la lista) o al revés."""
        self._placeholder.setVisible(visible)
        self._list.setVisible(not visible)

    def sync_position(self, position_ms: int) -> None:
        """Resalta la línea que corresponde a la posición actual."""
        if not self._times:
            return
        row = bisect.bisect_right(self._times, position_ms) - 1
        if row == self._active_row:
            return
        if 0 <= self._active_row < self._list.count():
            previous = self._list.item(self._active_row)
            if previous is not None:
                self._apply_style(previous, active=False)
        self._active_row = row
        if 0 <= row < self._list.count():
            item = self._list.item(row)
            if item is not None:
                self._apply_style(item, active=True)
                self._list.scrollToItem(item, QListWidget.ScrollHint.PositionAtCenter)

    def reset(self) -> None:
        """Limpia la letra (al detener o vaciar la playlist)."""
        self.show_track(None)

    # --------------------------------------------------------------- internas
    def _apply_style(self, item: QListWidgetItem, *, active: bool) -> None:
        item.setFont(self._active_font if active else self._base_font)
        if active:
            item.setForeground(QColor(60, 140, 255))
        else:
            item.setForeground(self._list.palette().text())
