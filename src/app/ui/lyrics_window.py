from __future__ import annotations

import bisect
import logging
import re
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.library.models import Track
from app.utils.paths import LYRICS_DIR

logger = logging.getLogger(__name__)

#: Marcas de tiempo LRC: ``[mm:ss]``, ``[mm:ss.xx]`` o ``[mm:ss.xxx]``.
LRC_TIME_RE = re.compile(r"\[(\d{1,2}):(\d{1,2})(?:[.:](\d{1,3}))?\]")

WINDOW_TITLE_MIN = (260, 320)

#: Aviso centrado cuando la pista no tiene letra disponible.
PLACEHOLDER_TEXT = "Letra no disponible :("


def parse_lrc(text: str) -> list[tuple[int, str]]:
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
    audio = Path(track_path)
    candidates = (audio.with_suffix(".lrc"), LYRICS_DIR / f"{audio.stem}.lrc")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


class LyricsWindow(QDialog):

    seek_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setModal(False)
        self.setWindowTitle(tr("Letra — PyAmp"))
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

        self._placeholder = QLabel(tr(PLACEHOLDER_TEXT))
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

        self._list.itemActivated.connect(self._on_item_activated)

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        row = self._list.row(item)
        if 0 <= row < len(self._times):
            self.seek_requested.emit(self._times[row])

    # ------------------------------------------------------------ API pública
    @property
    def entries(self) -> list[tuple[int, str]]:
        return list(self._entries)

    @property
    def active_row(self) -> int:
        return self._active_row

    @property
    def showing_placeholder(self) -> bool:
        return not self._placeholder.isHidden()

    def show_track(self, track: Track | None) -> None:
        self._entries = []
        self._times = []
        self._active_row = -1
        self._list.clear()
        self._set_placeholder(False)

        if track is None or not track.path:
            self._label_track.setText("—")
            self._status.setText(tr("No hay ninguna pista en reproducción"))
            self._set_placeholder(True)
            return

        self._label_track.setText(track.display_name)
        lrc_path = find_lrc_path(track.path)
        if lrc_path is None:
            stem = Path(track.path).stem
            self._status.setText(
                tr("No encontré «{stem}.lrc» (junto al audio o en {directory})").format(
                    stem=stem, directory=LYRICS_DIR
                )
            )
            self._set_placeholder(True)
            return

        try:
            text = lrc_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.warning("No se pudo leer la letra %s: %s", lrc_path, exc)
            self._status.setText(
                tr("No se pudo leer {name}: {error}").format(name=lrc_path.name, error=exc)
            )
            self._set_placeholder(True)
            return

        self._entries = parse_lrc(text)
        if not self._entries:
            raw = text.strip()
            if not raw:
                self._status.setText(
                    tr("{name}: sin marcas de tiempo [mm:ss]").format(name=lrc_path.name)
                )
                self._set_placeholder(True)
                return
            self._list.addItem(raw)
            self._status.setText(
                tr("{name}: sin marcas de tiempo [mm:ss]").format(name=lrc_path.name)
            )
            return

        self._status.setText(tr("Letra: {name}").format(name=lrc_path.name))
        for _position_ms, lyric in self._entries:
            self._list.addItem(lyric)
        self._times = [position_ms for position_ms, _lyric in self._entries]

    def _set_placeholder(self, visible: bool) -> None:
        self._placeholder.setVisible(visible)
        self._list.setVisible(not visible)

    def sync_position(self, position_ms: int) -> None:
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
        self.show_track(None)

    # --------------------------------------------------------------- internas
    def _apply_style(self, item: QListWidgetItem, *, active: bool) -> None:
        item.setFont(self._active_font if active else self._base_font)
        if active:
            item.setForeground(QColor(60, 140, 255))
        else:
            item.setForeground(self._list.palette().text())
