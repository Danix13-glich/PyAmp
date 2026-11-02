from __future__ import annotations

import urllib.parse
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStyle,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.utils.time_format import format_time

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


def _entry_int(entry: dict[str, object], key: str) -> int:
    value = entry.get(key)
    if isinstance(value, (int, float, str)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    return 0


def _youtube_link(entry: dict[str, object]) -> str:
    link = str(entry.get("link") or "").strip()
    if link and "music.apple.com" not in link and "deezer.com" not in link:
        return link
    title = str(entry.get("title") or "").strip()
    artist = str(entry.get("artist") or "").strip()
    query = f"{artist} {title}".strip()
    if not query:
        return link
    params = urllib.parse.urlencode({"search_query": query})
    return f"https://www.youtube.com/results?{params}"


class HistoryWindow(QDialog):

    delete_requested = Signal(int)
    download_requested = Signal(object)

    def __init__(
        self,
        entries: list[dict[str, object]] | None = None,
        *,
        ready: bool = False,
        searches: list[dict[str, object]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Historial — PyAmp"))
        self.setModal(True)
        self.resize(620, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        tabs = QTabWidget()
        tabs.addTab(self._build_ranking(entries, ready), tr("Más escuchadas"))
        tabs.addTab(self._build_searches(searches), tr("Búsquedas"))
        layout.addWidget(tabs, stretch=1)

        close = QPushButton(tr("Cerrar"))
        close.clicked.connect(self.accept)
        layout.addWidget(close)

    def _build_ranking(self, entries: list[dict[str, object]] | None, ready: bool) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
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
        return page

    def _build_searches(self, searches: list[dict[str, object]] | None) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        title = QLabel(tr("Canciones buscadas:"))
        layout.addWidget(title)

        self._search_scroll = QScrollArea()
        self._search_scroll.setWidgetResizable(True)
        self._search_scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self._search_layout = QVBoxLayout(content)
        self._search_layout.setContentsMargins(0, 0, 0, 0)
        self._search_layout.setSpacing(6)
        self._search_scroll.setWidget(content)
        layout.addWidget(self._search_scroll, stretch=1)

        self._searches = [dict(entry) for entry in (searches or [])]
        self._rebuild_searches()
        return page

    def _rebuild_searches(self) -> None:
        while self._search_layout.count():
            item = self._search_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not self._searches:
            placeholder = QLabel(tr("Todavía no hay canciones buscadas."))
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setWordWrap(True)
            self._search_layout.addStretch(1)
            self._search_layout.addWidget(placeholder)
            self._search_layout.addStretch(1)
            return
        for entry in self._searches:
            self._search_layout.addWidget(self._build_search_row(entry))
        self._search_layout.addStretch(1)

    def _build_search_row(self, entry: dict[str, object]) -> QFrame:
        frame = QFrame()
        frame.setObjectName("searchHistoryRow")
        frame.setStyleSheet(
            "QFrame#searchHistoryRow { border: 1px solid #505050;"
            " border-radius: 6px; padding: 6px; }"
        )
        row = QHBoxLayout(frame)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(10)

        info = QVBoxLayout()
        info.setSpacing(2)
        title = str(entry.get("title") or tr("Sin título"))
        artist = str(entry.get("artist") or tr("Artista desconocido"))
        duration_ms = _entry_int(entry, "duration_ms")
        link = _youtube_link(entry)

        name_label = QLabel(title)
        name_font = name_label.font()
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setWordWrap(True)
        info.addWidget(name_label)
        info.addWidget(QLabel(tr("Artista: {artist}").format(artist=artist)))
        info.addWidget(
            QLabel(
                tr("Duración: {duration}").format(
                    duration=format_time(duration_ms) if duration_ms > 0 else "—"
                )
            )
        )
        link_label = QLabel()
        if link:
            link_label.setText(tr("Enlace: {link}").format(link=f'<a href="{link}">{link}</a>'))
            link_label.setOpenExternalLinks(True)
            link_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        else:
            link_label.setText(tr("Enlace: —"))
        link_label.setWordWrap(True)
        info.addWidget(link_label)
        row.addLayout(info, stretch=1)

        actions = QHBoxLayout()
        actions.setSpacing(4)
        actions.addStretch(1)
        delete_button = QToolButton()
        delete_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        delete_button.setToolTip(tr("Eliminar esta búsqueda"))
        delete_button.setAccessibleName(tr("Eliminar esta búsqueda"))
        delete_button.clicked.connect(
            lambda _checked=False, search_id=_entry_int(entry, "id"): self._delete_search(search_id)
        )
        download_button = QToolButton()
        download_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown))
        download_button.setToolTip(tr("Descargar esta canción"))
        download_button.setAccessibleName(tr("Descargar esta canción"))
        download_button.clicked.connect(
            lambda _checked=False, data=dict(entry): self.download_requested.emit(data)
        )
        actions.addWidget(delete_button)
        actions.addWidget(download_button)
        row.addLayout(actions)
        return frame

    def _delete_search(self, search_id: int) -> None:
        if search_id <= 0:
            return
        self._searches = [entry for entry in self._searches if _entry_int(entry, "id") != search_id]
        self.delete_requested.emit(search_id)
        # Reconstruir fuera de la señal del botón: borrar el propio botón
        # dentro de su clicked puede terminar en un fallo de Qt.
        QTimer.singleShot(0, self._rebuild_searches)

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
