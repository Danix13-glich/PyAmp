from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    QPoint,
    QSortFilterProxyModel,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QStyle,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.library.database import LibraryDatabase
from app.library.models import Track
from app.utils.time_format import format_time

logger = logging.getLogger(__name__)

#: Retardo del filtro de búsqueda (evita recalcular por tecla).
SEARCH_DEBOUNCE_MS = 300

COLUMN_NAME, COLUMN_DURATION, COLUMN_ARTIST, COLUMN_FAVORITE = range(4)
HEADERS = ("Nombre", "Duración", "Artista", "★")

#: Rol de ordenación: valor comparable de cada columna (str/ int).
SORT_ROLE = Qt.ItemDataRole.UserRole + 1

#: Prefijo que marca una pista oculta cuando se muestran.
HIDDEN_PREFIX = "-"

ACTION_FAVORITE = "favorite"
ACTION_UNFAVORITE = "unfavorite"
ACTION_HIDE = "hide"
ACTION_UNHIDE = "unhide"
ACTION_RENAME = "rename"
ACTION_DELETE = "delete"
ACTION_EDIT_METADATA = "edit_metadata"


class SongsTableModel(QAbstractTableModel):

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tracks: list[Track] = []
        self._show_hidden = False

    def set_tracks(self, tracks: list[Track], show_hidden: bool = False) -> None:
        self._show_hidden = bool(show_hidden)
        visible = [track for track in tracks if self._show_hidden or not track.is_hidden]
        self.beginResetModel()
        self._tracks = visible
        self.endResetModel()

    def track_at(self, row: int) -> Track | None:
        if 0 <= row < len(self._tracks):
            return self._tracks[row]
        return None

    # ---------------------------------------------------------- interfaz Qt
    def rowCount(  # noqa: N802
        self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()
    ) -> int:
        return 0 if parent.isValid() else len(self._tracks)

    def columnCount(  # noqa: N802
        self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()
    ) -> int:
        return 0 if parent.isValid() else len(HEADERS)

    def headerData(  # noqa: N802
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(HEADERS)
        ):
            return tr(HEADERS[section])
        return None

    def data(  # noqa: N802
        self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if not isinstance(index, QModelIndex) or not index.isValid():
            return None
        track = self._tracks[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if column == COLUMN_NAME:
                name = track.display_title
                return f"{HIDDEN_PREFIX}{name}" if track.is_hidden else name
            if column == COLUMN_DURATION:
                return format_time(track.duration_ms) if track.duration_ms > 0 else "—"
            if column == COLUMN_ARTIST:
                return track.display_artist
            if column == COLUMN_FAVORITE:
                return "★" if track.is_favorite else ""
        elif role == Qt.ItemDataRole.ToolTipRole:
            return track.path
        elif role == SORT_ROLE:
            if column == COLUMN_DURATION:
                return track.duration_ms
            if column == COLUMN_ARTIST:
                return track.display_artist.casefold()
            if column == COLUMN_FAVORITE:
                return 1 if track.is_favorite else 0
            name = track.display_title.casefold()
            return f"{HIDDEN_PREFIX}{name}" if track.is_hidden else name
        return None


class SongsTable(QWidget):

    track_activated = Signal(object, list)
    favorite_toggled = Signal(object)
    #: El botón de refresco pide re-escanear (la ventana decide cómo).
    refresh_requested = Signal()
    #: Acción del menú contextual: (id, pista).
    action_requested = Signal(str, object)

    def __init__(self, database: LibraryDatabase, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._database = database
        self._favorites_only = False
        self._show_hidden = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        search_row = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText(tr("Buscar nombre, artista o álbum..."))
        self._search_edit.setClearButtonEnabled(True)
        search_row.addWidget(self._search_edit, stretch=1)
        self._button_refresh = QToolButton()
        self._button_refresh.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        )
        self._button_refresh.setToolTip(tr("Refrescar canciones"))
        self._button_refresh.setAccessibleName(tr("Refrescar canciones"))
        search_row.addWidget(self._button_refresh)
        root.addLayout(search_row)

        self._model = SongsTableModel(self)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortRole(SORT_ROLE)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._proxy.setFilterKeyColumn(-1)  # busca en todas las columnas

        self._view = QTableView()
        self._view.setModel(self._proxy)
        self._view.setSortingEnabled(True)
        self._view.sortByColumn(COLUMN_NAME, Qt.SortOrder.AscendingOrder)
        self._view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._view.setAlternatingRowColors(True)
        self._view.verticalHeader().setVisible(False)
        self._view.setColumnWidth(COLUMN_NAME, 320)
        self._view.setColumnWidth(COLUMN_DURATION, 80)
        self._view.setColumnWidth(COLUMN_ARTIST, 220)
        self._view.setColumnWidth(COLUMN_FAVORITE, 32)
        self._view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._view.customContextMenuRequested.connect(self._on_context_menu)
        root.addWidget(self._view, stretch=1)

        self._empty_label = QLabel("")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._empty_label)

        self._stats_label = QLabel("")
        self._stats_label.setToolTip(tr("Catálogo cargado"))
        root.addWidget(self._stats_label)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(SEARCH_DEBOUNCE_MS)
        self._search_timer.timeout.connect(self._apply_filter)

        self._search_edit.textChanged.connect(self._on_search_text_changed)
        self._button_refresh.clicked.connect(self.refresh_requested.emit)
        self._view.activated.connect(self._on_activated)

    # ------------------------------------------------------------ API pública
    @property
    def view(self) -> QTableView:
        return self._view

    @property
    def proxy(self) -> QSortFilterProxyModel:
        return self._proxy

    @property
    def model(self) -> SongsTableModel:
        return self._model

    @property
    def favorites_only(self) -> bool:
        return self._favorites_only

    def set_favorites_only(self, favorites_only: bool) -> None:
        self._favorites_only = bool(favorites_only)
        self.refresh()

    def set_show_hidden(self, show_hidden: bool) -> None:
        self._show_hidden = bool(show_hidden)
        self.refresh()

    def selected_track(self) -> Track | None:
        index = self._view.currentIndex()
        if not index.isValid():
            return None
        source = self._proxy.mapToSource(index)
        return self._model.track_at(source.row())

    def refresh(self) -> None:
        try:
            if self._favorites_only:
                tracks = self._database.favorite_tracks()
            else:
                tracks = self._database.all_tracks()
        except Exception as exc:  # noqa: BLE001 - una consulta no tumbará la UI
            logger.warning("Canciones: fallo al recargar: %s", exc)
            tracks = []
        self._model.set_tracks(tracks, self._show_hidden)
        self._update_labels()

    def search(self, term: str) -> None:
        self._search_timer.stop()
        self._search_edit.setText(term)
        self._apply_filter()

    # --------------------------------------------------------------- internos
    def _on_search_text_changed(self, _text: str) -> None:
        self._search_timer.start()

    def _apply_filter(self) -> None:
        self._proxy.setFilterFixedString(self._search_edit.text().strip())
        self._update_labels()

    def _update_labels(self) -> None:
        visible = self._proxy.rowCount()
        total = self._model.rowCount()
        favorites = sum(1 for track in self._model._tracks if track.is_favorite)
        term = self._search_edit.text().strip()
        if visible == 0:
            if term:
                self._empty_label.setText(tr("Sin resultados para «{term}»").format(term=term))
            elif self._favorites_only:
                self._empty_label.setText(
                    tr("Aún no hay favoritas — marca ★ en la vista Canciones")
                )
            else:
                self._empty_label.setText(
                    tr("Biblioteca vacía — «Archivo → Escanear carpeta en biblioteca...»")
                )
            self._empty_label.show()
        else:
            self._empty_label.hide()
        self._stats_label.setText(
            tr("{visible} de {total} canciones · {favorites} favoritas").format(
                visible=visible, total=total, favorites=favorites
            )
        )

    def _track_at_position(self, position: QPoint) -> Track | None:
        index = self._view.indexAt(position)
        if not index.isValid():
            return None
        self._view.setCurrentIndex(index)
        source = self._proxy.mapToSource(index)
        return self._model.track_at(source.row())

    def _on_context_menu(self, position: QPoint) -> None:
        track = self._track_at_position(position)
        if track is None or not track.path:
            return
        menu = QMenu(self)
        if track.is_favorite:
            action_fav = menu.addAction(tr("Quitar de favoritos"))
            action_fav.triggered.connect(
                lambda: self.action_requested.emit(ACTION_UNFAVORITE, track)
            )
        else:
            action_fav = menu.addAction(tr("Mover a favoritos"))
            action_fav.triggered.connect(lambda: self.action_requested.emit(ACTION_FAVORITE, track))
        if track.is_hidden:
            action_hide = menu.addAction(tr("Mostrar"))
            action_hide.triggered.connect(lambda: self.action_requested.emit(ACTION_UNHIDE, track))
        else:
            action_hide = menu.addAction(tr("Ocultar"))
            action_hide.triggered.connect(lambda: self.action_requested.emit(ACTION_HIDE, track))
        menu.addSeparator()
        action_rename = menu.addAction(tr("Renombrar"))
        action_rename.triggered.connect(lambda: self.action_requested.emit(ACTION_RENAME, track))
        action_metadata = menu.addAction(tr("Editar metadata"))
        action_metadata.triggered.connect(
            lambda: self.action_requested.emit(ACTION_EDIT_METADATA, track)
        )
        menu.addSeparator()
        action_delete = menu.addAction(tr("Eliminar"))
        action_delete.triggered.connect(lambda: self.action_requested.emit(ACTION_DELETE, track))
        menu.exec(self._view.viewport().mapToGlobal(position))

    def _on_activated(self, proxy_index: QModelIndex) -> None:
        if not proxy_index.isValid():
            return
        source_index = self._proxy.mapToSource(proxy_index)
        track = self._model.track_at(source_index.row())
        if track is None:
            return
        if proxy_index.column() == COLUMN_FAVORITE:
            self.favorite_toggled.emit(track)
            return
        self.track_activated.emit(track, self.visible_tracks())

    def visible_tracks(self) -> list[Track]:
        tracks: list[Track] = []
        for row in range(self._proxy.rowCount()):
            source = self._proxy.mapToSource(self._proxy.index(row, COLUMN_NAME))
            track = self._model.track_at(source.row())
            if track is not None:
                tracks.append(track)
        return tracks
