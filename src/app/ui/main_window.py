"""Ventana principal de PyAmp — UI mínima de la Fase 1.

Contiene lo justo para reproducir: abrir archivo/carpeta, transporte,
sliders de seek y volumen, etiquetas de pista/tiempo y lista simple con
guardar/cargar ``.m3u``. Esta UI la sustituirá la Winamp moderna en la
Fase 3 (LCD, playlist lateral, temas).

Reglas que respeta:

* La UI **nunca** habla con VLC: llama a :class:`app.core.player.Player`
  y escucha sus señales.
* La UI **nunca** lanza notificaciones: solo existe UNA conexión
  ``player.track_changed -> notifier.notify_track``.
* El escaneo de carpetas ocurre en :class:`_FolderLoader` (QThread) — la
  interfaz nunca se bloquea (RNF).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QAction, QFontDatabase, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QSlider,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.player import STATE_PLAYING, STATE_STOPPED, Player
from app.core.playlist import audio_filter_string, collect_audio_files
from app.core.settings import Settings, get_settings
from app.library.metadata import read_metadata
from app.library.models import Track
from app.notifications.notifier import Notifier
from app.utils.paths import PLAYLISTS_DIR
from app.utils.time_format import format_time

logger = logging.getLogger(__name__)

WINDOW_TITLE = "PyAmp"
ERROR_TIMEOUT_MS = 10000
VOLUME_SLIDER_WIDTH = 140


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
    """Ventana principal con la UI mínima de la Fase 1."""

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
        self._duration_ms = 0
        self._last_folder = str(Path.home())

        self._build_ui()
        self._connect_signals()
        self._restore_state()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        """Construye el layout mínimo (sin lógica de negocio)."""
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumSize(480, 360)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # --- fila de información (título / artista / tiempo) ---
        info_row = QHBoxLayout()
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
        info_row.addLayout(text_col, stretch=1)

        self._label_time = QLabel("0:00 / 0:00")
        fixed_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self._label_time.setFont(fixed_font)
        info_row.addWidget(self._label_time, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(info_row)

        # --- transporte + volumen ---
        transport_row = QHBoxLayout()
        self._button_prev = self._make_button(
            QStyle.StandardPixmap.SP_MediaSkipBackward, "Anterior (lista)", self._player.prev
        )
        self._button_play = self._make_button(
            QStyle.StandardPixmap.SP_MediaPlay, "Reproducir", self._player.play
        )
        self._button_pause = self._make_button(
            QStyle.StandardPixmap.SP_MediaPause, "Pausar", self._player.pause
        )
        self._button_stop = self._make_button(
            QStyle.StandardPixmap.SP_MediaStop, "Detener", self._player.stop
        )
        self._button_next = self._make_button(
            QStyle.StandardPixmap.SP_MediaSkipForward, "Siguiente", self._player.next
        )
        for button in (
            self._button_prev,
            self._button_play,
            self._button_pause,
            self._button_stop,
            self._button_next,
        ):
            transport_row.addWidget(button)

        transport_row.addStretch(1)

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

        # --- seek ---
        self._slider_seek = QSlider(Qt.Orientation.Horizontal)
        self._slider_seek.setRange(0, 0)
        self._slider_seek.setToolTip("Posición de reproducción")
        self._slider_seek.setAccessibleName("Posición")
        self._slider_seek.sliderReleased.connect(self._on_seek_released)
        self._slider_seek.sliderMoved.connect(self._on_seek_moved)
        layout.addWidget(self._slider_seek)

        # --- lista simple ---
        self._playlist_widget = QListWidget()
        self._playlist_widget.setAlternatingRowColors(True)
        self._playlist_widget.setToolTip("Lista de reproducción (doble clic para reproducir)")
        layout.addWidget(self._playlist_widget, stretch=1)

        self.setCentralWidget(central)
        self._build_menus()
        self._on_state_changed(STATE_STOPPED)
        self._update_mute_icon(self._settings.muted)

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

        self._playlist_widget.itemActivated.connect(self._on_item_activated)

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
        """Diálogo de carpeta: escaneo en segundo plano."""
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

    def _add_paths(self, paths: list[str]) -> None:
        """Añade pistas al modelo y a la lista; arranca si estaba vacía."""
        if not paths:
            return
        was_empty = len(self._player.playlist) == 0
        tracks = self._player.add_paths(paths)
        for track in tracks:
            self._append_row(track)
        if was_empty and tracks:
            # Primeras pistas de la sesión: empieza a sonar la primera.
            self._player.play_index(0)
        else:
            self.statusBar().showMessage(
                "Doble clic en una pista para reproducir", ERROR_TIMEOUT_MS
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
        self._rebuild_rows()
        self.statusBar().showMessage(f"Playlist cargada ({count} pistas)", ERROR_TIMEOUT_MS)
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
        self._playlist_widget.clear()
        self._label_title.setText(WINDOW_TITLE)
        self._label_artist.setText("—")
        self.statusBar().showMessage("Playlist vaciada", ERROR_TIMEOUT_MS)

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        """Doble clic o Enter en una fila: reproducir esa pista."""
        self._player.play_index(self._playlist_widget.row(item))

    # ------------------------------------------------------ slots del player
    def _on_track_changed(self, track: object) -> None:
        """Nuevo pista sonando: etiquetas, fila y (vía única conexión) notificación."""
        if isinstance(track, Track):
            self._show_track(track)

    def _show_track(self, track: Track) -> None:
        """Actualiza etiquetas y fila con los datos de la pista."""
        self._label_title.setText(track.display_title)
        self._label_title.setToolTip(track.path)
        self._label_artist.setText(track.display_artist)
        self._label_artist.setToolTip(track.path)

        if track.duration_ms > 0:
            self._duration_ms = track.duration_ms
            self._slider_seek.setRange(0, track.duration_ms)
        self._update_time_label(self._slider_seek.value())

        index = self._player.playlist.current_index
        if 0 <= index < self._playlist_widget.count():
            item = self._playlist_widget.item(index)
            if item is not None:
                if track.title:
                    item.setText(track.display_name)
                item.setSelected(True)
            self._playlist_widget.setCurrentRow(index)

    def _on_state_changed(self, state: str) -> None:
        """Refleja el estado en los botones de transporte."""
        playing = state == STATE_PLAYING
        self._button_play.setEnabled(state != STATE_PLAYING)
        self._button_pause.setEnabled(playing)
        self._button_stop.setEnabled(state != STATE_STOPPED)
        self._button_prev.setEnabled(state != STATE_STOPPED)
        self._button_next.setEnabled(state != STATE_STOPPED)

    def _on_position_changed(self, position_ms: int) -> None:
        if not self._slider_seek.isSliderDown():
            self._slider_seek.setValue(position_ms)
            self._update_time_label(position_ms)

    def _on_duration_changed(self, duration_ms: int) -> None:
        self._duration_ms = max(0, duration_ms)
        self._slider_seek.setRange(0, self._duration_ms)
        self._update_time_label(self._slider_seek.value())

    def _on_volume_changed(self, volume: int) -> None:
        if self._slider_volume.value() != volume:
            self._slider_volume.blockSignals(True)
            self._slider_volume.setValue(volume)
            self._slider_volume.blockSignals(False)

    def _on_error(self, message: str) -> None:
        """Error no fatal: se muestra en la barra de estado; nada crashea."""
        logger.warning("UI recibe error: %s", message)
        self.statusBar().showMessage(message, ERROR_TIMEOUT_MS)

    # ------------------------------------------------------- slots de sliders
    def _on_seek_released(self) -> None:
        self._player.seek(self._slider_seek.value())

    def _on_seek_moved(self, value: int) -> None:
        self._update_time_label(value)

    def _on_volume_slider_changed(self, value: int) -> None:
        self._player.set_volume(value)

    def _on_mute_toggled(self, checked: bool) -> None:
        self._player.set_muted(checked)
        self._update_mute_icon(checked)

    # -------------------------------------------------------------- helpers
    def _append_row(self, track: Track) -> None:
        item = QListWidgetItem(track.display_title if not track.title else track.display_name)
        item.setData(Qt.ItemDataRole.UserRole, track.path)
        item.setToolTip(track.path)
        self._playlist_widget.addItem(item)

    def _rebuild_rows(self) -> None:
        self._playlist_widget.clear()
        for track in self._player.playlist:
            self._append_row(track)
        current = self._player.playlist.current_index
        if 0 <= current < self._playlist_widget.count():
            self._playlist_widget.setCurrentRow(current)

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
            self._rebuild_rows()

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
        self._notifier.close_all()
        self._player.shutdown()
        logger.info("Ventana cerrada; estado guardado")
        super().closeEvent(event)  # type: ignore[arg-type]
