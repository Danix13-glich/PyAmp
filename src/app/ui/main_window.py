"""Ventana principal de PyAmp — Fase 4.

Vistas (menú Ver): «Canciones» (tabla del catálogo, por defecto) y
«Biblioteca» (árbol artista→álbum→pista), una sola a todo el ancho en un
``QStackedWidget``. Sin lista lateral: la cola interna se controla con el
transporte (▶/siguiente/anterior).

Reglas que respeta:

* La UI **nunca** habla con VLC: llama a :class:`app.core.player.Player`
  y escucha sus señales.
* La UI **nunca** lanza notificaciones: solo existe UNA conexión
  ``player.track_changed -> notifier.notify_track`` (el botón «Probar»
  de Ajustes pasa por el MISMO Notifier).
* Carpetas: :class:`_FolderLoader` (cola) y :class:`ScannerThread`
  (biblioteca) en QThread — la interfaz nunca se bloquea (RNF).
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QFontDatabase, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSlider,
    QStackedWidget,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.player import STATE_PAUSED, STATE_PLAYING, STATE_STOPPED, Player
from app.core.playlist import audio_filter_string, collect_audio_files
from app.core.settings import (
    VIEW_BIBLIOTECA,
    VIEW_CANCIONES,
    Settings,
    get_settings,
)
from app.library.covers import extract_cover
from app.library.database import LibraryDatabase
from app.library.metadata import read_metadata
from app.library.models import Track
from app.library.scanner import ScannerThread
from app.notifications.notifier import Notifier
from app.ui.cover_widget import CoverLabel
from app.ui.library_panel import LibraryPanel
from app.ui.lyrics_window import LyricsWindow
from app.ui.settings_dialog import SettingsDialog
from app.ui.songs_table import SongsTable
from app.ui.spectrum_widget import SpectrumWidget
from app.utils.paths import PLAYLISTS_DIR
from app.utils.time_format import format_time
from app.version import __version__

logger = logging.getLogger(__name__)

WINDOW_TITLE = "PyAmp"
ERROR_TIMEOUT_MS = 10000
VOLUME_SLIDER_WIDTH = 140

#: Ancho de la zona de título/artista (ajuste Fase 5).
TEXT_COL_WIDTH = 148

#: Tamaño inicial de la ventana (ajuste Fase 5: 630×485).
WINDOW_INITIAL_SIZE = (630, 485)

#: Separación (px) entre la ventana principal y la de letra.
LYRICS_GAP_PX = 8


class _FolderLoader(QThread):
    """Recorre una carpeta buscando audio sin bloquear la UI (RNF).

    Args:
        folder: Carpeta a escanear.
        parent: QObject propietario (la ventana).
    """

    #: Emite la lista de rutas encontradas (llega encolada al hilo de UI).
    paths_loaded = Signal(list)

    def __init__(self, folder: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._folder = folder

    def run(self) -> None:
        """Cuerpo del hilo: solo llama a la función pura de core/playlist."""
        try:
            paths = collect_audio_files(self._folder)
        except Exception as exc:  # noqa: BLE001 - un error de disco no debe tumbar la app
            logger.error("Error escaneando %s: %s", self._folder, exc)
            paths = []
        self.paths_loaded.emit(paths)


class MainWindow(QMainWindow):
    """Ventana principal con la UI de la Fase 5."""

    #: Peticiones MPRIS llegadas del bus (hilo ajeno → hilo de UI).
    _raise_requested = Signal()
    _quit_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings: Settings = get_settings()
        self._player = Player(settings=self._settings)

        # ÚNICO punto del programa que lanza notificaciones de escritorio.
        self._notifier = Notifier(
            timeout_ms=self._settings.notifications_timeout_ms,
            enabled=self._settings.notifications_enabled,
        )
        self._player.track_changed.connect(self._notifier.notify_track)
        logger.info(
            "Notifier iniciado (backend=%s, enabled=%s, timeout=%dms)",
            self._notifier.backend_name,
            self._notifier.enabled,
            self._notifier.timeout_ms,
        )

        self._folder_loader: _FolderLoader | None = None
        self._scanner: ScannerThread | None = None
        self._library = LibraryDatabase()
        self._duration_ms = 0
        self._last_folder = str(Path.home())
        self._mpris: Any = None  # MprisAdapter (solo Linux; ver _init_mpris)
        self._lyrics_window: LyricsWindow | None = None

        self._build_ui()
        self._connect_signals()
        self._restore_state()
        self._init_mpris()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        """Construye el layout (sin lógica de negocio)."""
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumSize(480, 360)
        self.resize(*WINDOW_INITIAL_SIZE)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # --- fila de información (carátula / título / artista / tiempo) ---
        info_row = QHBoxLayout()
        self._cover_label = CoverLabel()
        info_row.addWidget(self._cover_label, alignment=Qt.AlignmentFlag.AlignVCenter)
        text_col = QVBoxLayout()
        self._label_title = QLabel(WINDOW_TITLE)
        title_font = self._label_title.font()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 2)
        self._label_title.setFont(title_font)
        self._label_title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._label_artist = QLabel("—")
        self._label_artist.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text_col.addWidget(self._label_title)
        text_col.addWidget(self._label_artist)
        text_wrap = QWidget()
        text_wrap.setFixedWidth(TEXT_COL_WIDTH)
        text_wrap.setLayout(text_col)
        info_row.addWidget(text_wrap, stretch=1)

        self._label_time = QLabel("0:00 / 0:00")
        fixed_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self._label_time.setFont(fixed_font)
        info_row.addWidget(self._label_time, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(info_row)

        # --- barra de posición justo debajo del tiempo (ajuste Fase 5) ---
        self._slider_seek = QSlider(Qt.Orientation.Horizontal)
        self._slider_seek.setRange(0, 0)
        self._slider_seek.setToolTip("Posición de reproducción")
        self._slider_seek.setAccessibleName("Posición")
        self._slider_seek.sliderReleased.connect(self._on_seek_released)
        self._slider_seek.sliderMoved.connect(self._on_seek_moved)
        layout.addWidget(self._slider_seek)

        # --- transporte: play/pausa unificado + favorito + volumen ---
        transport_row = QHBoxLayout()
        self._button_prev = self._make_button(
            QStyle.StandardPixmap.SP_MediaSkipBackward, "Anterior (F9)", self._player.prev
        )
        self._button_play = self._make_button(
            QStyle.StandardPixmap.SP_MediaPlay, "Reproducir (F10)", self._on_play_clicked
        )
        self._button_next = self._make_button(
            QStyle.StandardPixmap.SP_MediaSkipForward, "Siguiente (F11)", self._player.next
        )
        for button in (
            self._button_prev,
            self._button_play,
            self._button_next,
        ):
            transport_row.addWidget(button)

        transport_row.addStretch(1)

        self._button_favorite = QToolButton()
        self._button_favorite.setText("★")
        self._button_favorite.setCheckable(True)
        self._button_favorite.setToolTip("Marcar la pista actual como favorita")
        self._button_favorite.setAccessibleName("Favorito")
        self._button_favorite.clicked.connect(self._on_favorite_clicked)
        transport_row.addWidget(self._button_favorite)

        self._button_mute = QToolButton()
        self._button_mute.setCheckable(True)
        self._button_mute.setToolTip("Silenciar (mute)")
        self._button_mute.setAccessibleName("Silenciar")
        self._button_mute.toggled.connect(self._on_mute_toggled)
        transport_row.addWidget(self._button_mute)

        self._slider_volume = QSlider(Qt.Orientation.Horizontal)
        self._slider_volume.setRange(0, 100)
        self._slider_volume.setValue(self._settings.volume)
        self._slider_volume.setFixedWidth(VOLUME_SLIDER_WIDTH)
        self._slider_volume.setToolTip("Volumen")
        self._slider_volume.setAccessibleName("Volumen")
        self._slider_volume.valueChanged.connect(self._on_volume_slider_changed)
        transport_row.addWidget(self._slider_volume)
        layout.addLayout(transport_row)

        # --- espectrograma (visible según el menú Ver) ---
        self._spectrum = SpectrumWidget()
        self._spectrum.setVisible(self._settings.show_spectrum)
        layout.addWidget(self._spectrum)

        # --- vistas a todo el ancho (menú Ver): canciones | biblioteca ---
        self._songs_table = SongsTable(self._library)
        self._library_panel = LibraryPanel(self._library)
        self._stacked = QStackedWidget()
        self._stacked.addWidget(self._songs_table)  # índice 0: canciones
        self._stacked.addWidget(self._library_panel)  # índice 1: biblioteca
        layout.addWidget(self._stacked, stretch=1)

        self.setCentralWidget(central)
        self._build_menus()
        self._on_state_changed(STATE_STOPPED)
        self._update_mute_icon(self._settings.muted)
        self._songs_table.refresh()
        self._library_panel.refresh()
        self._set_view(self._settings.view_mode, save=False)

    def _build_menus(self) -> None:
        """Menú Archivo con las operaciones de playlist."""
        file_menu = self.menuBar().addMenu("&Archivo")

        action_open_files = QAction("Abrir &archivo(s)...", self)
        action_open_files.setShortcut(QKeySequence.StandardKey.Open)
        action_open_files.triggered.connect(self._on_open_files)
        file_menu.addAction(action_open_files)

        action_open_folder = QAction("Abrir &carpeta...", self)
        action_open_folder.setShortcut(QKeySequence("Ctrl+Shift+O"))
        action_open_folder.triggered.connect(self._on_open_folder)
        self._action_open_folder = action_open_folder
        file_menu.addAction(action_open_folder)

        action_scan = QAction("Escanear carpeta en &biblioteca...", self)
        action_scan.triggered.connect(self._on_scan_library)
        self._action_scan = action_scan
        file_menu.addAction(action_scan)

        file_menu.addSeparator()

        action_load = QAction("&Cargar playlist...", self)
        action_load.setShortcut(QKeySequence("Ctrl+Shift+L"))
        action_load.triggered.connect(self._on_load_playlist)
        file_menu.addAction(action_load)

        action_save = QAction("&Guardar playlist como...", self)
        action_save.setShortcut(QKeySequence.StandardKey.SaveAs)
        action_save.triggered.connect(self._on_save_playlist)
        file_menu.addAction(action_save)

        file_menu.addSeparator()

        action_clear = QAction("&Vaciar lista", self)
        action_clear.triggered.connect(self._on_clear_playlist)
        file_menu.addAction(action_clear)

        file_menu.addSeparator()

        action_quit = QAction("&Salir", self)
        action_quit.setShortcut(QKeySequence.StandardKey.Quit)
        action_quit.triggered.connect(self.close)
        file_menu.addAction(action_quit)

        # --- menú Ver: tipo de vista (persistida en QSettings) ---
        view_menu = self.menuBar().addMenu("&Ver")
        self._action_view_canciones = QAction("Canciones (&tabla)", self)
        self._action_view_canciones.setCheckable(True)
        self._action_view_canciones.setShortcut(QKeySequence("Ctrl+1"))
        self._action_view_canciones.triggered.connect(lambda: self._set_view(VIEW_CANCIONES))
        self._action_view_biblioteca = QAction("&Biblioteca (árbol)", self)
        self._action_view_biblioteca.setCheckable(True)
        self._action_view_biblioteca.setShortcut(QKeySequence("Ctrl+2"))
        self._action_view_biblioteca.triggered.connect(lambda: self._set_view(VIEW_BIBLIOTECA))
        view_group = QActionGroup(self)
        view_group.setExclusive(True)
        view_group.addAction(self._action_view_canciones)
        view_group.addAction(self._action_view_biblioteca)
        view_menu.addAction(self._action_view_canciones)
        view_menu.addAction(self._action_view_biblioteca)

        view_menu.addSeparator()

        self._action_show_spectrum = QAction("Mostrar es&trograma", self)
        self._action_show_spectrum.setCheckable(True)
        self._action_show_spectrum.setChecked(self._settings.show_spectrum)
        self._action_show_spectrum.triggered.connect(self._on_toggle_spectrum)
        view_menu.addAction(self._action_show_spectrum)

        action_lyrics = QAction("Ver &letra", self)
        action_lyrics.setShortcut(QKeySequence("Ctrl+L"))
        action_lyrics.triggered.connect(self._on_show_lyrics)
        view_menu.addAction(action_lyrics)

        # --- menú Editar ---
        edit_menu = self.menuBar().addMenu("&Editar")
        action_settings = QAction("&Ajustes...", self)
        action_settings.setShortcut(QKeySequence.StandardKey.Preferences)
        action_settings.triggered.connect(self._on_open_settings)
        edit_menu.addAction(action_settings)

        self._build_shortcuts()

    def _build_shortcuts(self) -> None:
        """Teclas multimedia y F9/F10/F11 (ApplicationShortcut: basta con  que la ventana esté activa, sin necesidad del foco del ratón).

        Las teclas multimedia usan los enums ``Qt.Key`` (el parse por
        nombre «MediaPlay» no produce una secuencia portable en Qt6).
        """
        shortcuts: tuple[tuple[QKeySequence, str, Callable[..., Any]], ...] = (
            (
                QKeySequence(Qt.Key.Key_MediaPrevious),
                "Pista anterior",
                self._player.prev,
            ),
            (
                QKeySequence(Qt.Key.Key_MediaTogglePlayPause),
                "Reproducir/pausar",
                self._on_play_clicked,
            ),
            (QKeySequence(Qt.Key.Key_MediaPlay), "Reproducir", self._player.play),
            (QKeySequence(Qt.Key.Key_MediaPause), "Pausar", self._player.pause),
            (
                QKeySequence(Qt.Key.Key_MediaNext),
                "Pista siguiente",
                self._player.next,
            ),
            (QKeySequence("F9"), "Pista anterior (F9)", self._player.prev),
            (
                QKeySequence("F10"),
                "Reproducir/pausar (F10)",
                self._on_play_clicked,
            ),
            (QKeySequence("F11"), "Pista siguiente (F11)", self._player.next),
        )
        for sequence, name, slot in shortcuts:
            action = QAction(name, self)
            action.setShortcut(sequence)
            action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
            action.triggered.connect(slot)
            self.addAction(action)  # la ventana mantiene viva la acción

    def _make_button(
        self,
        icon: QStyle.StandardPixmap,
        tooltip: str,
        slot: Callable[..., Any],
    ) -> QToolButton:
        """Crea un botón de transporte con icono nativo y tooltip."""
        button = QToolButton()
        button.setIcon(self.style().standardIcon(icon))
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.clicked.connect(slot)
        return button

    # --------------------------------------------------------------- señales
    def _connect_signals(self) -> None:
        """Conecta las señales del player a la UI (y solo eso)."""
        player = self._player
        player.track_changed.connect(self._on_track_changed)
        player.playback_state_changed.connect(self._on_state_changed)
        player.position_changed.connect(self._on_position_changed)
        player.duration_changed.connect(self._on_duration_changed)
        player.volume_changed.connect(self._on_volume_changed)
        player.error_occurred.connect(self._on_error)
        # La biblioteca acumula estadísticas en cada cambio de pista real.
        player.track_changed.connect(self._record_library_play)

        # Peticiones MPRIS (llegan desde el hilo del bus → hilo de UI).
        self._raise_requested.connect(self._raise_and_activate)
        self._quit_requested.connect(self.close)

        self._songs_table.track_activated.connect(self._on_library_track_activated)
        self._songs_table.favorite_toggled.connect(self._on_favorite_row_toggled)
        self._library_panel.track_activated.connect(self._on_library_track_activated)
        self._library_panel.selection_changed.connect(self._on_library_selection_changed)

        if not player.is_available:
            self.statusBar().showMessage(player.backend_error or "Audio no disponible", 0)

    # ------------------------------------------------------------- acciones
    def _on_open_files(self) -> None:
        """Diálogo multi-archivo: añade a la playlist."""
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Abrir archivos de audio",
            self._last_folder,
            f"Archivos de audio ({audio_filter_string()});;Todos los archivos (*)",
        )
        if paths:
            self._last_folder = str(Path(paths[0]).parent)
        self._add_paths(paths)

    def _on_open_folder(self) -> None:
        """Diálogo de carpeta: encola en 2.º plano y actualiza la biblioteca."""
        if self._folder_loader is not None and self._folder_loader.isRunning():
            return
        folder = QFileDialog.getExistingDirectory(self, "Abrir carpeta", self._last_folder)
        if not folder:
            return
        self._last_folder = folder
        self._action_open_folder.setEnabled(False)
        self.statusBar().showMessage(f"Escaneando {folder} ...", 0)
        loader = _FolderLoader(folder, self)
        loader.paths_loaded.connect(self._on_paths_loaded)
        loader.finished.connect(self._on_folder_finished)
        self._folder_loader = loader
        loader.start()
        # Fase 4: la carpeta también pasa a la biblioteca (en 2.º plano),
        # de modo que las canciones siempre aparecen en la vista Canciones.
        self._start_scan(folder)

    def _on_paths_loaded(self, paths: list) -> None:
        """Resultado del escaneo (hilo de UI)."""
        if not paths:
            self.statusBar().showMessage("No se encontraron archivos de audio", ERROR_TIMEOUT_MS)
            return
        self._add_paths([str(p) for p in paths])
        self.statusBar().showMessage(f"{len(paths)} pistas añadidas", ERROR_TIMEOUT_MS)

    def _on_folder_finished(self) -> None:
        self._folder_loader = None
        self._action_open_folder.setEnabled(True)

    # ------------------------------------------------- biblioteca (Fase 2)
    def _on_scan_library(self) -> None:
        """Diálogo de carpeta → escaneo de biblioteca en QThread."""
        if self._scanner is not None and self._scanner.isRunning():
            return
        folder = QFileDialog.getExistingDirectory(
            self, "Escanear carpeta para la biblioteca", self._last_folder
        )
        if not folder:
            return
        self._last_folder = folder
        self._start_scan(folder)

    def _start_scan(self, folder: str) -> None:
        """Lanza el escáner de biblioteca en QThread (nunca bloquea la UI)."""
        if self._scanner is not None and self._scanner.isRunning():
            return
        self._action_scan.setEnabled(False)
        self.statusBar().showMessage(f"Escaneando {folder} ...", 0)
        scanner = ScannerThread(self._library.path, folder, self)
        scanner.progress.connect(self._on_scan_progress)
        scanner.scan_finished.connect(self._on_scan_finished)
        scanner.scan_error.connect(self._on_error)
        self._scanner = scanner
        scanner.start()

    def _on_scan_progress(self, processed: int, current: str) -> None:
        self.statusBar().showMessage(f"Escaneando… {processed} archivos ({current})", 0)

    def _on_scan_finished(self, summary: object) -> None:
        """Resumen del escaneo (hilo de UI); reactiva el menú."""
        self._scanner = None
        self._action_scan.setEnabled(True)
        if not isinstance(summary, dict):
            return
        message = (
            f"Biblioteca: {summary['added']} añadidas, {summary['updated']} "
            f"actualizadas, {summary['skipped']} sin cambios, "
            f"{summary['removed']} eliminadas"
        )
        if summary.get("errors"):
            message += f", {summary['errors']} errores"
        if summary.get("cancelled"):
            message += " (escaneo cancelado)"
        self.statusBar().showMessage(message, ERROR_TIMEOUT_MS)
        self._library_panel.refresh()
        self._songs_table.refresh()

    def _record_library_play(self, track: object) -> None:
        """Suma una reproducción en la biblioteca (nunca rompe el playback)."""
        if not isinstance(track, Track) or not track.path:
            return
        try:
            self._library.record_play_by_path(track.path)
        except Exception as exc:  # noqa: BLE001 - la música no se detiene
            logger.warning("No se pudo registrar la reproducción: %s", exc)

    def _on_library_track_activated(self, track: object, context: object) -> None:
        """Doble clic en la biblioteca: el contexto visible pasa a playlist."""
        if not isinstance(track, Track) or not isinstance(context, list):
            return
        tracks = [t for t in context if isinstance(t, Track)]
        if not tracks:
            return
        try:
            start = tracks.index(track)
        except ValueError:
            start = 0
        self._player.replace_playlist(tracks, start)
        logger.info(
            "Biblioteca: reproduciendo %r (%d pistas en contexto)",
            track.display_title,
            len(tracks),
        )
        self.statusBar().showMessage(
            f"▶ {track.display_name} ({len(tracks)} pistas en cola)", ERROR_TIMEOUT_MS
        )

    def _on_library_selection_changed(self, selection: object) -> None:
        """Selección en la biblioteca → vista previa de carátula."""
        cover = getattr(selection, "cover_path", None)
        if cover:
            self._cover_label.set_cover(cover)
        else:
            self._show_current_cover()

    def _show_current_cover(self) -> None:
        """Carátula de la pista sonando (caché de covers, Fase 2)."""
        current = self._player.current_track
        if current is None:
            self._cover_label.clear_cover()
            return
        self._cover_label.set_cover(self._cover_for(current))

    def _cover_for(self, track: Track) -> str | None:
        """Ruta de carátula de la pista; extrae a caché si aún no está."""
        if track.cover_path:
            return track.cover_path
        try:
            return extract_cover(track.path)
        except Exception as exc:  # noqa: BLE001 - la música no se detiene
            logger.debug("Sin carátula para %s: %s", track.path, exc)
            return None

    def _add_paths(self, paths: list[str]) -> None:
        """Añade pistas a la playlist interna; arranca si estaba vacía."""
        if not paths:
            return
        was_empty = len(self._player.playlist) == 0
        tracks = self._player.add_paths(paths)
        if was_empty and tracks:
            # Primeras pistas de la sesión: empieza a sonar la primera.
            self._player.play_index(0)
        else:
            self.statusBar().showMessage(
                f"{len(tracks)} pistas en cola — ▶ para reproducir", ERROR_TIMEOUT_MS
            )

    def _on_load_playlist(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Cargar playlist",
            str(PLAYLISTS_DIR),
            "Playlists (*.m3u *.m3u8);;Todos los archivos (*)",
        )
        if not path:
            return
        try:
            count = self._player.load_playlist(path)
        except OSError as exc:
            self._on_error(f"No se pudo cargar la playlist: {exc}")
            return
        self.statusBar().showMessage(f"Playlist cargada ({count} pistas en cola)", ERROR_TIMEOUT_MS)
        if count:
            current = self._player.current_track
            if current is not None:
                self._show_track(current)

    def _on_save_playlist(self) -> None:
        if len(self._player.playlist) == 0:
            self.statusBar().showMessage("La playlist está vacía", ERROR_TIMEOUT_MS)
            return
        suggested = str(PLAYLISTS_DIR / "playlist.m3u")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar playlist como",
            suggested,
            "Playlist M3U (*.m3u);;Todos los archivos (*)",
        )
        if not path:
            return
        if not Path(path).suffix:
            path += ".m3u"
        try:
            self._player.save_playlist(path)
        except OSError as exc:
            self._on_error(f"No se pudo guardar la playlist: {exc}")
            return
        self.statusBar().showMessage(f"Playlist guardada en {path}", ERROR_TIMEOUT_MS)

    def _on_clear_playlist(self) -> None:
        self._player.stop()
        self._player.playlist.clear()
        self._label_title.setText(WINDOW_TITLE)
        self._label_artist.setText("—")
        if self._lyrics_window is not None:
            self._lyrics_window.reset()
        self.statusBar().showMessage("Playlist vaciada", ERROR_TIMEOUT_MS)

    # ------------------------------------------------------ slots del player
    def _on_track_changed(self, track: object) -> None:
        """Nuevo pista sonando: etiquetas, fila y (vía única conexión) notificación."""
        if isinstance(track, Track):
            self._show_track(track)

    def _show_track(self, track: Track) -> None:
        """Actualiza etiquetas, carátula, favorito, letra y MPRIS."""
        self._label_title.setText(track.display_title)
        self._label_title.setToolTip(track.path)
        self._label_artist.setText(track.display_artist)
        self._label_artist.setToolTip(track.path)
        cover = self._cover_for(track)
        self._cover_label.set_cover(cover)

        if track.duration_ms > 0:
            self._duration_ms = track.duration_ms
            self._slider_seek.setRange(0, track.duration_ms)
        self._update_time_label(self._slider_seek.value())

        self._button_favorite.setEnabled(track.path != "")
        favorite = False
        if track.path:
            try:
                favorite = self._library.is_favorite(track.path)
            except Exception as exc:  # noqa: BLE001 - la música no se detiene
                logger.debug("Sin estado de favorito: %s", exc)
        self._button_favorite.setChecked(favorite)

        if self._lyrics_window is not None and self._lyrics_window.isVisible():
            self._lyrics_window.show_track(track)
        if self._mpris is not None:
            self._mpris.update_metadata(cover or "")

    def _on_state_changed(self, state: str) -> None:
        """Refleja el estado en el icono del play unificado y el espectro."""
        playing = state == STATE_PLAYING
        if playing:
            icon = QStyle.StandardPixmap.SP_MediaPause
            tooltip = "Pausar (F10)"
        elif state == STATE_PAUSED:
            icon = QStyle.StandardPixmap.SP_MediaPlay
            tooltip = "Reanudar (F10)"
        else:
            icon = QStyle.StandardPixmap.SP_MediaPlay
            tooltip = "Reproducir (F10)"
        self._button_play.setIcon(self.style().standardIcon(icon))
        self._button_play.setToolTip(tooltip)
        self._button_play.setAccessibleName(tooltip)
        self._button_prev.setEnabled(state != STATE_STOPPED)
        self._button_next.setEnabled(state != STATE_STOPPED)
        self._spectrum.set_playing(playing)
        if self._mpris is not None:
            self._mpris.update_playback_status()

    def _on_position_changed(self, position_ms: int) -> None:
        if not self._slider_seek.isSliderDown():
            self._slider_seek.setValue(position_ms)
            self._update_time_label(position_ms)
        if self._lyrics_window is not None and self._lyrics_window.isVisible():
            self._lyrics_window.sync_position(position_ms)

    def _on_duration_changed(self, duration_ms: int) -> None:
        self._duration_ms = max(0, duration_ms)
        self._slider_seek.setRange(0, self._duration_ms)
        self._update_time_label(self._slider_seek.value())

    def _on_volume_changed(self, volume: int) -> None:
        if self._slider_volume.value() != volume:
            self._slider_volume.blockSignals(True)
            self._slider_volume.setValue(volume)
            self._slider_volume.blockSignals(False)
        if self._mpris is not None:
            self._mpris.update_volume()

    def _on_error(self, message: str) -> None:
        """Error no fatal: se muestra en la barra de estado; nada crashea."""
        logger.warning("UI recibe error: %s", message)
        self.statusBar().showMessage(message, ERROR_TIMEOUT_MS)

    # ------------------------------------------------------- slots de sliders
    def _on_seek_released(self) -> None:
        self._player.seek(self._slider_seek.value())
        if self._mpris is not None:
            self._mpris.emit_seeked(self._slider_seek.value())

    def _on_seek_moved(self, value: int) -> None:
        self._update_time_label(value)

    def _on_volume_slider_changed(self, value: int) -> None:
        self._player.set_volume(value)

    def _on_mute_toggled(self, checked: bool) -> None:
        self._player.set_muted(checked)
        self._update_mute_icon(checked)

    # ------------------------------------------------- Fase 4: vistas/ajustes
    def _on_play_clicked(self) -> None:
        """▶/⏸ unificado: pausa si suena; (re)anuda o arranca si no."""
        self._player.toggle_pause()

    def _set_view(self, mode: str, *, save: bool = True) -> None:
        """Cambia la vista activa (menú Ver) y la recuerda en QSettings."""
        if mode == VIEW_BIBLIOTECA:
            self._stacked.setCurrentIndex(1)
            action = self._action_view_biblioteca
        else:
            mode = VIEW_CANCIONES
            self._stacked.setCurrentIndex(0)
            action = self._action_view_canciones
        action.setChecked(True)
        if save:
            self._settings.view_mode = mode

    def _on_open_settings(self) -> None:
        """Diálogo de Ajustes; aplica notificaciones al vuelo y prueba."""
        stats: dict[str, int] | None
        try:
            stats = self._library.stats()
        except Exception:  # noqa: BLE001 - la BD no debe tumbar el diálogo
            stats = None
        dialog = SettingsDialog(
            self._settings,
            notifier_backend=self._notifier.backend_name,
            version=__version__,
            library_stats=stats,
            parent=self,
        )
        dialog.apply_settings.connect(self._apply_notification_settings)
        dialog.test_notification.connect(self._send_test_notification)
        dialog.exec()

    def _apply_notification_settings(self, enabled: bool, timeout_ms: int) -> None:
        """Persiste en QSettings y actualiza el Notifier en caliente."""
        self._settings.notifications_enabled = enabled
        self._settings.notifications_timeout_ms = timeout_ms
        self._notifier.enabled = enabled
        self._notifier.timeout_ms = timeout_ms
        self.statusBar().showMessage(
            f"Ajustes aplicados: notificaciones {'activadas' if enabled else 'desactivadas'}, "
            f"{timeout_ms // 1000} s",
            ERROR_TIMEOUT_MS,
        )
        logger.info(
            "Ajustes de notificación aplicados (enabled=%s, timeout=%dms)",
            enabled,
            timeout_ms,
        )

    def _send_test_notification(self) -> None:
        """Notificación de prueba por el MISMO camino que las de pista."""
        try:
            self._notifier.notify("Notificación de prueba", "PyAmp funciona correctamente ✓")
        except Exception as exc:  # noqa: BLE001 - nunca romper la UI
            logger.warning("Notificación de prueba falló: %s", exc)
            self.statusBar().showMessage(f"La notificación falló: {exc}", ERROR_TIMEOUT_MS)
        else:
            self.statusBar().showMessage("Notificación de prueba enviada", ERROR_TIMEOUT_MS)

    def _on_favorite_clicked(self) -> None:
        """★ de la barra de transporte: alterna el favorito de la pista actual."""
        track = self._player.current_track
        if track is None or not track.path:
            self._button_favorite.setChecked(False)
            return
        self._toggle_favorite(track)

    def _on_favorite_row_toggled(self, track: object) -> None:
        """Doble clic sobre ★ en la tabla: alterna y refresca la columna."""
        if isinstance(track, Track) and track.path:
            self._toggle_favorite(track)

    def _toggle_favorite(self, track: Track) -> None:
        """Alterna el favorito en la BD y refleja el cambio en la UI."""
        try:
            favorite = self._library.toggle_favorite(track.path)
        except Exception as exc:  # noqa: BLE001 - la música no se detiene
            logger.warning("No se pudo alternar el favorito: %s", exc)
            self.statusBar().showMessage(f"Favorito no guardado: {exc}", ERROR_TIMEOUT_MS)
            return
        current = self._player.current_track
        if current is not None and current.path == track.path:
            self._button_favorite.setChecked(favorite)
        # Aplazado: evitar reset del modelo dentro de la señal activated.
        QTimer.singleShot(0, self._songs_table.refresh)
        self.statusBar().showMessage(
            "★ Añadida a favoritos" if favorite else "★ Quitada de favoritos",
            ERROR_TIMEOUT_MS,
        )

    # ------------------------------------------------- Fase 5: Ver/espectro/letra
    def _on_toggle_spectrum(self, checked: bool) -> None:
        """Ver → Mostrar espectrograma: oculta/muestra y persiste."""
        self._settings.show_spectrum = checked
        self._spectrum.setVisible(checked)
        if checked:
            self._spectrum.set_playing(self._player.state == STATE_PLAYING)
        else:
            self._spectrum.set_playing(False)
            self._spectrum.shutdown()  # no dejar captura corriendo oculta
        self.statusBar().showMessage(
            "Espectrograma visible" if checked else "Espectrograma oculto",
            ERROR_TIMEOUT_MS,
        )

    def _on_show_lyrics(self) -> None:
        """Ver → Ver letra: ventana al lado con la letra de la pista actual."""
        if self._lyrics_window is None:
            self._lyrics_window = LyricsWindow(self)
            self._lyrics_window.destroyed.connect(self._on_lyrics_destroyed)
        window = self._lyrics_window
        window.show_track(self._player.current_track)
        window.show()
        window.raise_()
        window.activateWindow()
        # Justo al lado de la principal (el compositor puede ajustarlo).
        window.move(self.x() + self.width() + LYRICS_GAP_PX, self.y())

    def _on_lyrics_destroyed(self, *_args: Any) -> None:
        """La ventana de letra se cerró: olvidar la referencia."""
        self._lyrics_window = None

    def _init_mpris(self) -> None:
        """Integración MPRIS (solo Linux; silenciosa si no hay D-Bus)."""
        if sys.platform != "linux":
            return
        try:
            from app.core.mpris import MprisAdapter

            adapter = MprisAdapter(
                self._player,
                self._settings,
                on_raise=self._raise_requested.emit,
                on_quit=self._quit_requested.emit,
            )
            adapter.start()
            self._mpris = adapter
        except Exception as exc:  # noqa: BLE001 - la app funciona sin MPRIS
            logger.info("MPRIS deshabilitado: %s", exc)

    def _raise_and_activate(self) -> None:
        """Raise vía MPRIS: trae la ventana al frente."""
        self.show()
        self.raise_()
        self.activateWindow()

    # -------------------------------------------------------------- helpers
    def _update_time_label(self, position_ms: int) -> None:
        self._label_time.setText(f"{format_time(position_ms)} / {format_time(self._duration_ms)}")

    def _update_mute_icon(self, muted: bool) -> None:
        pixmap = (
            QStyle.StandardPixmap.SP_MediaVolumeMuted
            if muted
            else QStyle.StandardPixmap.SP_MediaVolume
        )
        self._button_mute.setIcon(self.style().standardIcon(pixmap))

    # -------------------------------------------------------- persistencia
    def _restore_state(self) -> None:
        """Restaura geometría, playlist, pista y volumen desde QSettings."""
        geometry = self._settings.window_geometry
        if geometry is not None:
            self.restoreGeometry(geometry)

        restored: list[Track] = []
        for path in self._settings.playlist_paths:
            if Path(path).is_file():
                restored.append(Track(path=path))
        if restored:
            self._player.playlist.add_many(restored)

        index = self._settings.playlist_index
        if 0 <= index < len(self._player.playlist):
            track = self._player.playlist.set_current(index)
            if track is not None:
                # Un solo archivo de metadatos al arranque: coste ms, no bloquea.
                try:
                    info = read_metadata(track.path)
                    track.title = info.title
                    track.artist = info.artist
                    track.album = info.album
                    track.duration_ms = info.duration_ms or track.duration_ms
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Metadatos de restauración omitidos: %s", exc)
                self._show_track(track)

        self._slider_volume.blockSignals(True)
        self._slider_volume.setValue(self._settings.volume)
        self._slider_volume.blockSignals(False)
        if self._settings.muted:
            self._button_mute.blockSignals(True)
            self._button_mute.setChecked(True)
            self._button_mute.blockSignals(False)
            self._update_mute_icon(True)

    def closeEvent(self, event: object) -> None:
        """Guarda estado y apaga todo de forma ordenada."""
        self._settings.window_geometry = self.saveGeometry()
        self._settings.playlist_paths = [track.path for track in self._player.playlist]
        self._settings.playlist_index = self._player.playlist.current_index

        if self._folder_loader is not None and self._folder_loader.isRunning():
            self._folder_loader.wait(5000)
        if self._scanner is not None and self._scanner.isRunning():
            self._scanner.cancel()
            self._scanner.wait(10000)
        if self._lyrics_window is not None:
            self._lyrics_window.close()
        if self._mpris is not None:
            self._mpris.shutdown()
        self._spectrum.shutdown()
        self._notifier.close_all()
        self._player.shutdown()
        self._library.close()
        logger.info("Ventana cerrada; estado guardado")
        super().closeEvent(event)  # type: ignore[arg-type]
