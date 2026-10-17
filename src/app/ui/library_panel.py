"""Panel de biblioteca: árbol Artista → Álbum → Pista + búsqueda (Fase 3).

Reglas del proyecto:

* La UI nunca se bloquea (RNF): las consultas son perezosas —artistas al
  mostrar, álbumes al expandir artista, pistas al expandir álbum— e
  indexadas. El escáner (Fase 2) rellena SQLite en su QThread.
* La UI no habla con SQLite «a su manera»: recibe una
  :class:`~app.library.database.LibraryDatabase` y solo usa su API.

Señales:

* ``track_activated(track, context_tracks)`` — doble clic o Enter sobre
  una pista; ``context_tracks`` son los hermanos visibles (el álbum, el
  bucket «(Sin álbum)» o los resultados de búsqueda).
* ``selection_changed(selection)`` — :class:`Track`, :class:`Album` o
  None (la ventana lo usa para la vista previa de carátula).
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QStyle,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.library.database import LibraryDatabase
from app.library.models import Track
from app.utils.time_format import format_time

logger = logging.getLogger(__name__)

#: Retardo del filtro de búsqueda (evita una consulta por tecla).
SEARCH_DEBOUNCE_MS = 300

#: Tope de resultados mostrados en la vista plana de búsqueda.
SEARCH_LIMIT = 500

NO_ARTIST_LABEL = "(Sin artista)"
NO_ALBUM_LABEL = "(Sin álbum)"
SEARCH_TRUNCATED_LABEL = f"(mostrando solo los primeros {SEARCH_LIMIT} resultados)"

#: Roles de datos en los items del árbol.
ROLE_KIND = Qt.ItemDataRole.UserRole  # "artist" | "album" | "track" | "bucket" | "dummy"
ROLE_ID = Qt.ItemDataRole.UserRole + 1  # id de artista o álbum
ROLE_TRACK = Qt.ItemDataRole.UserRole + 2  # Track (nodos de pista)
ROLE_SELECTION = Qt.ItemDataRole.UserRole + 3  # Track|Album para selection_changed


class LibraryPanel(QWidget):
    """Árbol de biblioteca + búsqueda; emite acciones hacia la ventana."""

    track_activated = Signal(object, list)
    selection_changed = Signal(object)

    def __init__(self, database: LibraryDatabase, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._database = database

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        search_row = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Buscar título, artista o álbum...")
        self._search_edit.setClearButtonEnabled(True)
        search_row.addWidget(self._search_edit, stretch=1)
        self._button_refresh = QToolButton()
        self._button_refresh.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        )
        self._button_refresh.setToolTip("Refrescar biblioteca")
        self._button_refresh.setAccessibleName("Refrescar biblioteca")
        search_row.addWidget(self._button_refresh)
        root.addLayout(search_row)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Biblioteca", "Duración"])
        self._tree.setAlternatingRowColors(True)
        self._tree.setColumnWidth(0, 260)
        self._tree.setUniformRowHeights(True)
        root.addWidget(self._tree, stretch=1)

        self._stats_label = QLabel("")
        self._stats_label.setToolTip("Totales de la biblioteca")
        root.addWidget(self._stats_label)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(SEARCH_DEBOUNCE_MS)
        self._search_timer.timeout.connect(self.refresh)

        self._search_edit.textChanged.connect(self._on_search_text_changed)
        self._button_refresh.clicked.connect(self.refresh)
        self._tree.itemExpanded.connect(self._on_item_expanded)
        self._tree.itemActivated.connect(self._on_item_activated)
        self._tree.itemSelectionChanged.connect(self._on_selection_changed)

    # ------------------------------------------------------------ API pública
    @property
    def tree(self) -> QTreeWidget:
        """Vista del árbol (tests y accesibilidad)."""
        return self._tree

    def refresh(self) -> None:
        """Recarga el árbol (o los resultados si hay búsqueda activa)."""
        term = self._search_edit.text().strip()
        self._tree.setUpdatesEnabled(False)
        try:
            if term:
                self._populate_search(term)
            else:
                self._populate_tree()
        except Exception as exc:  # noqa: BLE001 - una consulta no tumbará la UI
            logger.warning("Biblioteca: fallo al recargar el panel: %s", exc)
        finally:
            self._tree.setUpdatesEnabled(True)
        self._update_stats()

    def search(self, term: str) -> None:
        """Aplica un filtro de búsqueda de inmediato (sin debounce)."""
        self._search_timer.stop()
        self._search_edit.setText(term)
        self.refresh()

    # ------------------------------------------------------------- poblado
    def _populate_tree(self) -> None:
        """Nivel superior: artistas + bucket «(Sin artista)» (perezoso)."""
        self._tree.clear()
        for artist in self._database.list_artists():
            item = QTreeWidgetItem([artist.display_name, ""])
            item.setData(0, ROLE_KIND, "artist")
            item.setData(0, ROLE_ID, artist.id)
            if artist.track_count:
                item.setToolTip(0, f"{artist.track_count} pistas")
            self._add_dummy(item)
            self._tree.addTopLevelItem(item)
        if self._database.count_tracks_without_artist() > 0:
            bucket = QTreeWidgetItem([NO_ARTIST_LABEL, ""])
            bucket.setData(0, ROLE_KIND, "artist")
            bucket.setData(0, ROLE_ID, None)
            self._add_dummy(bucket)
            self._tree.addTopLevelItem(bucket)

    def _add_dummy(self, item: QTreeWidgetItem) -> None:
        """Hijo marcador para cargar los hijos al expandir."""
        dummy = QTreeWidgetItem(item)
        dummy.setDisabled(True)
        dummy.setData(0, ROLE_KIND, "dummy")

    def _on_item_expanded(self, item: QTreeWidgetItem) -> None:
        """Carga perezosa: rellena el nodo si aún tiene el marcador."""
        if item.childCount() != 1:
            return
        child = item.child(0)
        if child is None or child.data(0, ROLE_KIND) != "dummy":
            return
        item.takeChildren()
        kind = item.data(0, ROLE_KIND)
        try:
            if kind == "artist":
                self._fill_artist(item)
            elif kind == "album":
                self._fill_album(item)
        except Exception as exc:  # noqa: BLE001 - la UI no se cae por una consulta
            logger.warning("Biblioteca: fallo al expandir %s: %s", kind, exc)

    def _fill_artist(self, item: QTreeWidgetItem) -> None:
        """Álbumes del artista + bucket «(Sin álbum)» si hay huérfanas."""
        artist_id = item.data(0, ROLE_ID)
        for album in self._database.albums_by_artist(artist_id):
            label = album.title
            if album.year:
                label = f"{album.title} ({album.year})"
            album_item = QTreeWidgetItem([label, ""])
            album_item.setData(0, ROLE_KIND, "album")
            album_item.setData(0, ROLE_ID, album.id)
            album_item.setData(0, ROLE_SELECTION, album)
            if album.track_count:
                album_item.setToolTip(0, f"{album.track_count} pistas")
            self._add_dummy(album_item)
            item.addChild(album_item)
        orphans = self._database.tracks_without_album_by_artist(artist_id)
        if orphans:
            bucket = QTreeWidgetItem([NO_ALBUM_LABEL, ""])
            bucket.setData(0, ROLE_KIND, "bucket")
            for track in orphans:
                self._add_track_item(bucket, track)
            item.addChild(bucket)

    def _fill_album(self, item: QTreeWidgetItem) -> None:
        """Pistas del álbum (ya con metadatos de la BD)."""
        album_id = item.data(0, ROLE_ID)
        for track in self._database.tracks_by_album(album_id):
            self._add_track_item(item, track)

    def _add_track_item(
        self, parent: QTreeWidgetItem | None, track: Track, label: str | None = None
    ) -> None:
        """Nodo de pista: «NN. Título» + duración; el Track va en UserRole."""
        if label is None:
            number = f"{track.track_no}. " if track.track_no else ""
            label = f"{number}{track.display_title}"
        item = QTreeWidgetItem([label, ""])
        item.setData(0, ROLE_KIND, "track")
        item.setData(0, ROLE_TRACK, track)
        item.setData(0, ROLE_SELECTION, track)
        item.setToolTip(0, track.path)
        if track.duration_ms > 0:
            item.setText(1, format_time(track.duration_ms))
        if parent is None:
            self._tree.addTopLevelItem(item)
        else:
            parent.addChild(item)

    # -------------------------------------------------------------- búsqueda
    def _on_search_text_changed(self, _text: str) -> None:
        self._search_timer.start()

    def _populate_search(self, term: str) -> None:
        """Vista plana con los resultados (tope + aviso de truncado)."""
        self._tree.clear()
        results = self._database.search_tracks(term, limit=SEARCH_LIMIT + 1)
        for track in results[:SEARCH_LIMIT]:
            self._add_track_item(None, track, label=track.display_name)
        if len(results) > SEARCH_LIMIT:
            info = QTreeWidgetItem([SEARCH_TRUNCATED_LABEL, ""])
            info.setDisabled(True)
            self._tree.addTopLevelItem(info)

    # -------------------------------------------------------------- acciones
    def _on_item_activated(self, item: QTreeWidgetItem, _column: int) -> None:
        """Enter o doble clic: si es pista, emite con su contexto visible."""
        if item.data(0, ROLE_KIND) != "track":
            return
        track = item.data(0, ROLE_TRACK)
        if not isinstance(track, Track):
            return
        self.track_activated.emit(track, self._context_tracks(item))

    def _context_tracks(self, item: QTreeWidgetItem) -> list[Track]:
        """Pistas hermanas visibles (padre = álbum/bucket o raíz en búsqueda)."""
        parent = item.parent()
        container = parent if parent is not None else self._tree.invisibleRootItem()
        tracks: list[Track] = []
        for index in range(container.childCount()):
            child = container.child(index)
            if child is None:
                continue
            track = child.data(0, ROLE_TRACK)
            if isinstance(track, Track):
                tracks.append(track)
        return tracks

    def _on_selection_changed(self) -> None:
        """Selección → Track/Album/None (la ventana decide la carátula)."""
        items = self._tree.selectedItems()
        if not items:
            self.selection_changed.emit(None)
            return
        self.selection_changed.emit(items[0].data(0, ROLE_SELECTION))

    def _update_stats(self) -> None:
        stats = self._database.stats()
        self._stats_label.setText(
            f"{stats['tracks']} pistas · {stats['artists']} artistas"
            f" · {stats['albums']} álbumes"
        )
