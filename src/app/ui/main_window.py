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

from PySide6.QtCore import QObject, QProcess, Qt, QThread, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QFontDatabase,
    QIcon,
    QKeySequence,
    QPainter,
)
from PySide6.QtWidgets import (
    QApplication,
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
    SHORTCUT_DEFAULTS,
    VIEW_BIBLIOTECA,
    VIEW_CANCIONES,
    VIEW_FAVORITOS,
    Settings,
    get_settings,
)
from app.i18n import set_language, tr
from app.library.covers import extract_cover
from app.library.database import LibraryDatabase
from app.library.metadata import format_audio_info, read_metadata
from app.library.models import Track
from app.library.scanner import ScannerThread
from app.notifications.notifier import Notifier
from app.themes import DEFAULT_THEME_ID, Theme, get_theme, load_themes
from app.ui.cover_widget import CoverLabel
from app.ui.library_panel import ROLE_TRACK, LibraryPanel
from app.ui.lyrics_editor import LyricsEditorDialog
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
        self._scan_queue: list[str] = []
        self._library = LibraryDatabase()
        self._duration_ms = 0
        self._last_folder = str(Path.home())
        self._mpris: Any = None  # MprisAdapter (solo Linux; ver _init_mpris)
        self._lyrics_window: LyricsWindow | None = None
        self._shortcut_actions: dict[str, QAction] = {}
        self._theme_actions: dict[str, QAction] = {}
        #: Icono nativo de cada botón de transporte (para re-teñirlo por tema).
        self._icon_buttons: dict[QToolButton, QStyle.StandardPixmap] = {}
        self._theme: Theme = get_theme(self._settings.theme_id or DEFAULT_THEME_ID)

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

        # --- cabecera estilo Winamp: carátula, texto, espectro y franja ---
        header_panel = QWidget()
        header_panel.setObjectName("headerPanel")
        header_v = QVBoxLayout(header_panel)
        header_v.setContentsMargins(10, 8, 10, 6)
        header_v.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)
        self._cover_label = CoverLabel()
        top_row.addWidget(self._cover_label, alignment=Qt.AlignmentFlag.AlignTop)

        text_col = QVBoxLayout()
        text_col.setSpacing(0)
        self._label_title = QLabel(WINDOW_TITLE)
        self._label_title.setObjectName("labelTitle")
        title_font = self._label_title.font()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 3)
        self._label_title.setFont(title_font)
        self._label_title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._label_artist = QLabel("—")
        self._label_artist.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._label_album = QLabel("")
        self._label_album.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text_col.addWidget(self._label_title)
        text_col.addWidget(self._label_artist)
        text_col.addWidget(self._label_album)
        top_row.addLayout(text_col, stretch=1)

        # Espectrograma integrado en la cabecera (a la derecha, como Winamp).
        self._spectrum = SpectrumWidget()
        self._spectrum.setVisible(self._settings.show_spectrum)
        top_row.addWidget(self._spectrum, alignment=Qt.AlignmentFlag.AlignVCenter)
        header_v.addLayout(top_row)

        bottom_row = QHBoxLayout()
        self._label_format = QLabel("")
        self._label_format.setObjectName("labelFormat")
        small_font = self._label_format.font()
        small_font.setPointSize(max(7, small_font.pointSize() - 2))
        self._label_format.setFont(small_font)
        self._label_format.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        bottom_row.addWidget(self._label_format, stretch=1)
        self._label_time = QLabel("0:00 / 0:00")
        self._label_time.setObjectName("labelTime")
        fixed_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self._label_time.setFont(fixed_font)
        bottom_row.addWidget(self._label_time)
        header_v.addLayout(bottom_row)

        # --- barra de posición dentro del recuadro (debajo del tiempo) ---
        self._slider_seek = QSlider(Qt.Orientation.Horizontal)
        self._slider_seek.setRange(0, 0)
        self._slider_seek.setToolTip(tr("Posición de reproducción"))
        self._slider_seek.setAccessibleName(tr("Posición"))
        self._slider_seek.sliderReleased.connect(self._on_seek_released)
        self._slider_seek.sliderMoved.connect(self._on_seek_moved)
        header_v.addWidget(self._slider_seek)

        # --- transporte dentro del recuadro: play/pausa + favorito + volumen ---
        transport_row = QHBoxLayout()
        self._button_prev = self._make_button(
            QStyle.StandardPixmap.SP_MediaSkipBackward,
            f"{tr('Anterior')} ({SHORTCUT_DEFAULTS['prev']})",
            self._player.prev,
        )
        self._button_play = self._make_button(
            QStyle.StandardPixmap.SP_MediaPlay,
            f"{tr('Reproducir')} ({SHORTCUT_DEFAULTS['play_pause']})",
            self._on_play_clicked,
        )
        self._button_next = self._make_button(
            QStyle.StandardPixmap.SP_MediaSkipForward,
            f"{tr('Siguiente')} ({SHORTCUT_DEFAULTS['next']})",
            self._player.next,
        )
        for button in (
            self._button_prev,
            self._button_play,
            self._button_next,
        ):
            transport_row.addWidget(button)

        self._button_shuffle = QToolButton()
        self._button_shuffle.setText("🔀")
        self._button_shuffle.setCheckable(True)
        self._button_shuffle.setToolTip(tr("Aleatorio: siguiente pista al azar"))
        self._button_shuffle.setAccessibleName(tr("Aleatorio"))
        self._button_shuffle.setChecked(self._settings.shuffle)
        self._button_shuffle.toggled.connect(self._on_shuffle_toggled)
        transport_row.addWidget(self._button_shuffle)

        self._button_repeat = QToolButton()
        self._button_repeat.setText("🔁")
        self._button_repeat.setCheckable(True)
        self._button_repeat.setToolTip(
            tr("Repetir: al terminar la playlist se vuelve a la primera")
        )
        self._button_repeat.setAccessibleName(tr("Repetir"))
        self._button_repeat.setChecked(self._settings.repeat)
        self._button_repeat.toggled.connect(self._on_repeat_toggled)
        transport_row.addWidget(self._button_repeat)

        transport_row.addStretch(1)

        self._button_favorite = QToolButton()
        self._button_favorite.setText("★")
        self._button_favorite.setCheckable(True)
        self._button_favorite.setToolTip(tr("Marcar la pista actual como favorita"))
        self._button_favorite.setAccessibleName(tr("Favorito"))
        self._button_favorite.clicked.connect(self._on_favorite_clicked)
        transport_row.addWidget(self._button_favorite)

        self._button_mute = QToolButton()
        self._button_mute.setCheckable(True)
        self._button_mute.setToolTip(tr("Silenciar (mute)"))
        self._button_mute.setAccessibleName(tr("Silenciar"))
        self._button_mute.toggled.connect(self._on_mute_toggled)
        transport_row.addWidget(self._button_mute)

        self._slider_volume = QSlider(Qt.Orientation.Horizontal)
        self._slider_volume.setRange(0, 100)
        self._slider_volume.setValue(self._settings.volume)
        self._slider_volume.setFixedWidth(VOLUME_SLIDER_WIDTH)
        self._slider_volume.setToolTip(tr("Volumen"))
        self._slider_volume.setAccessibleName(tr("Volumen"))
        self._slider_volume.valueChanged.connect(self._on_volume_slider_changed)
        transport_row.addWidget(self._slider_volume)
        header_v.addLayout(transport_row)

        # Panel oscuro fijo (el borde de la carátula es propio del widget);
        # los colores concretos los pone el tema activo (_apply_theme).
        self._header_panel = header_panel
        layout.addWidget(header_panel)

        # --- vistas a todo el ancho (menú Ver): canciones | biblioteca | favoritos ---
        self._songs_table = SongsTable(self._library)
        self._favorites_table = SongsTable(self._library)
        self._favorites_table.set_favorites_only(True)
        self._library_panel = LibraryPanel(self._library)
        self._stacked = QStackedWidget()
        self._stacked.addWidget(self._songs_table)  # índice 0: canciones
        self._stacked.addWidget(self._library_panel)  # índice 1: biblioteca
        self._stacked.addWidget(self._favorites_table)  # índice 2: favoritos
        layout.addWidget(self._stacked, stretch=1)

        self.setCentralWidget(central)
        self._build_menus()
        self._apply_theme(self._theme, save=False)
        self._on_state_changed(STATE_STOPPED)
        self._update_mute_icon(self._settings.muted)
        self._cover_label.setVisible(self._settings.show_cover)
        self._songs_table.refresh()
        self._favorites_table.refresh()
        self._library_panel.refresh()
        self._set_view(self._settings.view_mode, save=False)

    def _build_menus(self) -> None:
        """Menú Archivo con las operaciones de playlist."""
        file_menu = self.menuBar().addMenu(tr("&Archivo"))

        action_open_files = QAction(tr("Abrir &archivo(s)..."), self)
        action_open_files.triggered.connect(self._on_open_files)
        self._register_shortcut("open_files", action_open_files)
        file_menu.addAction(action_open_files)

        action_open_folder = QAction(tr("Abrir &carpeta..."), self)
        action_open_folder.triggered.connect(self._on_open_folder)
        self._action_open_folder = action_open_folder
        self._register_shortcut("open_folder", action_open_folder)
        file_menu.addAction(action_open_folder)

        action_scan = QAction(tr("Escanear carpeta en &biblioteca..."), self)
        action_scan.triggered.connect(self._on_scan_library)
        self._action_scan = action_scan
        file_menu.addAction(action_scan)

        file_menu.addSeparator()

        action_load = QAction(tr("&Cargar playlist..."), self)
        action_load.triggered.connect(self._on_load_playlist)
        self._register_shortcut("load_playlist", action_load)
        file_menu.addAction(action_load)

        action_save = QAction(tr("&Guardar playlist como..."), self)
        action_save.triggered.connect(self._on_save_playlist)
        self._register_shortcut("save_playlist", action_save)
        file_menu.addAction(action_save)

        file_menu.addSeparator()

        action_clear = QAction(tr("&Vaciar lista"), self)
        action_clear.triggered.connect(self._on_clear_playlist)
        file_menu.addAction(action_clear)

        file_menu.addSeparator()

        action_quit = QAction(tr("&Salir"), self)
        action_quit.triggered.connect(self.close)
        self._register_shortcut("quit", action_quit)
        file_menu.addAction(action_quit)

        # --- menú Ver: tipo de vista (persistida en QSettings) ---
        view_menu = self.menuBar().addMenu(tr("&Ver"))
        self._action_view_canciones = QAction(tr("Canciones (&tabla)"), self)
        self._action_view_canciones.setCheckable(True)
        self._action_view_canciones.triggered.connect(lambda: self._set_view(VIEW_CANCIONES))
        self._register_shortcut("view_canciones", self._action_view_canciones)
        self._action_view_biblioteca = QAction(tr("&Biblioteca (árbol)"), self)
        self._action_view_biblioteca.setCheckable(True)
        self._action_view_biblioteca.triggered.connect(lambda: self._set_view(VIEW_BIBLIOTECA))
        self._register_shortcut("view_biblioteca", self._action_view_biblioteca)
        self._action_view_favoritos = QAction(tr("F&avoritos (★)"), self)
        self._action_view_favoritos.setCheckable(True)
        self._action_view_favoritos.triggered.connect(lambda: self._set_view(VIEW_FAVORITOS))
        self._register_shortcut("view_favoritos", self._action_view_favoritos)
        view_group = QActionGroup(self)
        view_group.setExclusive(True)
        view_group.addAction(self._action_view_canciones)
        view_group.addAction(self._action_view_biblioteca)
        view_group.addAction(self._action_view_favoritos)
        view_menu.addAction(self._action_view_canciones)
        view_menu.addAction(self._action_view_biblioteca)
        view_menu.addAction(self._action_view_favoritos)

        view_menu.addSeparator()

        self._action_show_spectrum = QAction(tr("Mostrar es&trograma"), self)
        self._action_show_spectrum.setCheckable(True)
        self._action_show_spectrum.setChecked(self._settings.show_spectrum)
        self._action_show_spectrum.triggered.connect(self._on_toggle_spectrum)
        view_menu.addAction(self._action_show_spectrum)

        self._action_show_cover = QAction(tr("Mostrar &imagen"), self)
        self._action_show_cover.setCheckable(True)
        self._action_show_cover.setChecked(self._settings.show_cover)
        self._action_show_cover.triggered.connect(self._on_toggle_cover)
        view_menu.addAction(self._action_show_cover)

        action_lyrics = QAction(tr("Ver &letra"), self)
        action_lyrics.triggered.connect(self._on_show_lyrics)
        self._register_shortcut("lyrics", action_lyrics)
        view_menu.addAction(action_lyrics)

        # Submenú de temas (mismo catálogo que Ajustes → Apariencia).
        themes_menu = view_menu.addMenu(tr("&Tema"))
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        for theme in load_themes().values():
            action = QAction(theme.name, self)
            action.setCheckable(True)
            action.setData(theme.id)
            action.triggered.connect(lambda checked=False, tid=theme.id: self._apply_theme_id(tid))
            theme_group.addAction(action)
            themes_menu.addAction(action)
            self._theme_actions[theme.id] = action

        # --- menú Editar ---
        edit_menu = self.menuBar().addMenu(tr("&Editar"))

        action_edit_lyrics = QAction(tr("&Editar letra..."), self)
        action_edit_lyrics.setToolTip(tr("Editar o escribir la letra de la canción seleccionada"))
        action_edit_lyrics.triggered.connect(self._on_edit_lyrics)
        edit_menu.addAction(action_edit_lyrics)

        edit_menu.addSeparator()

        action_settings = QAction(tr("&Ajustes..."), self)
        action_settings.triggered.connect(self._on_open_settings)
        self._register_shortcut("settings", action_settings)
        edit_menu.addAction(action_settings)

        self._build_shortcuts()

    def _register_shortcut(self, shortcut_id: str, action: QAction) -> None:
        """Vincula la acción a su atajo (personalizado o por defecto).

        Todas las acciones se quedan registradas en
        ``_shortcut_actions`` para poder reasignarlas en caliente desde
        Ajustes (``apply_shortcuts``) sin reconstruir los menús.
        """
        self._shortcut_actions[shortcut_id] = action
        default = SHORTCUT_DEFAULTS[shortcut_id]
        sequence = self._settings.shortcuts.get(shortcut_id, default)
        action.setShortcut(QKeySequence(sequence))

    def _apply_shortcuts(self) -> None:
        """Reaplica los atajos (personalizados o por defecto) a las acciones."""
        custom = self._settings.shortcuts
        for shortcut_id, action in self._shortcut_actions.items():
            sequence = custom.get(shortcut_id, SHORTCUT_DEFAULTS[shortcut_id])
            action.setShortcut(QKeySequence(sequence))
        self._refresh_shortcut_labels()

    def _shortcut_label(self, shortcut_id: str) -> str:
        """Texto actual del atajo (para tooltips y nombres visibles)."""
        action = self._shortcut_actions.get(shortcut_id)
        if action is None:
            return SHORTCUT_DEFAULTS[shortcut_id]
        return action.shortcut().toString(QKeySequence.SequenceFormat.PortableText)

    def _refresh_shortcut_labels(self) -> None:
        """Actualiza los tooltips del transporte que citan sus teclas."""
        prev_label = f"{tr('Anterior')} ({self._shortcut_label('prev')})"
        self._button_prev.setToolTip(prev_label)
        self._button_prev.setAccessibleName(prev_label)
        next_label = f"{tr('Siguiente')} ({self._shortcut_label('next')})"
        self._button_next.setToolTip(next_label)
        self._button_next.setAccessibleName(next_label)
        self._on_state_changed(self._player.state)

    def _build_shortcuts(self) -> None:
        """Teclas multimedia (fijas) y atajos de transporte reasignables.

        Las teclas multimedia usan los enums ``Qt.Key`` (el parse por
        nombre «MediaPlay» no produce una secuencia portable en Qt6) y
        quedan fuera del catálogo personalizable: son teclas de hardware.
        F9/F10/F11 sí pasan por ``_register_shortcut`` (Ajustes → Atajos).
        """
        media_shortcuts: tuple[tuple[QKeySequence, str, Callable[..., Any]], ...] = (
            (
                QKeySequence(Qt.Key.Key_MediaPrevious),
                tr("Pista anterior (multimedia)"),
                self._player.prev,
            ),
            (
                QKeySequence(Qt.Key.Key_MediaTogglePlayPause),
                tr("Reproducir/pausar (multimedia)"),
                self._on_play_clicked,
            ),
            (
                QKeySequence(Qt.Key.Key_MediaPlay),
                tr("Reproducir (multimedia)"),
                self._player.play,
            ),
            (
                QKeySequence(Qt.Key.Key_MediaPause),
                tr("Pausar (multimedia)"),
                self._player.pause,
            ),
            (
                QKeySequence(Qt.Key.Key_MediaNext),
                tr("Pista siguiente (multimedia)"),
                self._player.next,
            ),
        )
        for sequence, name, slot in media_shortcuts:
            action = QAction(name, self)
            action.setShortcut(sequence)
            action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
            action.triggered.connect(slot)
            self.addAction(action)  # la ventana mantiene viva la acción

        for shortcut_id, name, slot in (
            ("prev", tr("Pista anterior"), self._player.prev),
            ("play_pause", tr("Reproducir/pausar"), self._on_play_clicked),
            ("next", tr("Pista siguiente"), self._player.next),
        ):
            action = QAction(name, self)
            action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
            action.triggered.connect(slot)
            self.addAction(action)
            self._register_shortcut(shortcut_id, action)
        self._refresh_shortcut_labels()

    def _make_button(
        self,
        icon: QStyle.StandardPixmap,
        tooltip: str,
        slot: Callable[..., Any],
    ) -> QToolButton:
        """Crea un botón de transporte con icono del tema y tooltip."""
        button = QToolButton()
        self._icon_buttons[button] = icon
        button.setIcon(self._transport_icon(icon))
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.clicked.connect(slot)
        return button

    def _transport_icon(self, standard: QStyle.StandardPixmap) -> QIcon:
        """Icono nativo teñido con el color de iconos del tema activo.

        Los iconos del escritorio heredan su color del tema del sistema:
        en un tema claro como «Arena clara» quedaban claros sobre fondo
        claro y no se veían. Teñirlos garantiza contraste en cualquier
        tema.
        """
        base = self.style().standardIcon(standard)
        pixmap = base.pixmap(24, 24)
        if pixmap.isNull():
            return base
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), QColor(self._theme.color("icon")))
        painter.end()
        return QIcon(pixmap)

    def _refresh_icon_buttons(self) -> None:
        """Re-tiñe todos los iconos de transporte con el tema activo."""
        for button, standard in self._icon_buttons.items():
            button.setIcon(self._transport_icon(standard))

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
        self._songs_table.refresh_requested.connect(self._on_refresh_songs)
        self._favorites_table.track_activated.connect(self._on_library_track_activated)
        self._favorites_table.favorite_toggled.connect(self._on_favorite_row_toggled)
        self._favorites_table.refresh_requested.connect(self._on_refresh_songs)
        self._library_panel.track_activated.connect(self._on_library_track_activated)
        self._library_panel.selection_changed.connect(self._on_library_selection_changed)

        if not player.is_available:
            self.statusBar().showMessage(player.backend_error or tr("Audio no disponible"), 0)

    # ------------------------------------------------------------- acciones
    def _on_open_files(self) -> None:
        """Diálogo multi-archivo: añade a la playlist."""
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            tr("Abrir archivos de audio"),
            self._last_folder,
            tr("Archivos de audio ({filters});;Todos los archivos (*)").format(
                filters=audio_filter_string()
            ),
        )
        if paths:
            self._last_folder = str(Path(paths[0]).parent)
        self._add_paths(paths)

    def _on_open_folder(self) -> None:
        """Diálogo de carpeta: encola en 2.º plano y actualiza la biblioteca."""
        if self._folder_loader is not None and self._folder_loader.isRunning():
            return
        folder = QFileDialog.getExistingDirectory(self, tr("Abrir carpeta"), self._last_folder)
        if not folder:
            return
        self._last_folder = folder
        self._action_open_folder.setEnabled(False)
        self.statusBar().showMessage(tr("Escaneando {folder} ...").format(folder=folder), 0)
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
            self.statusBar().showMessage(
                tr("No se encontraron archivos de audio"), ERROR_TIMEOUT_MS
            )
            return
        self._add_paths([str(p) for p in paths])
        self.statusBar().showMessage(
            tr("{count} pistas añadidas").format(count=len(paths)), ERROR_TIMEOUT_MS
        )

    def _on_folder_finished(self) -> None:
        self._folder_loader = None
        self._action_open_folder.setEnabled(True)

    # ------------------------------------------------- biblioteca (Fase 2)
    def _on_scan_library(self) -> None:
        """Diálogo de carpeta → escaneo de biblioteca en QThread."""
        if self._scanner is not None and self._scanner.isRunning():
            return
        folder = QFileDialog.getExistingDirectory(
            self, tr("Escanear carpeta para la biblioteca"), self._last_folder
        )
        if not folder:
            return
        self._last_folder = folder
        self._start_scan(folder)

    def _start_scan(self, folder: str) -> None:
        """Lanza el escáner de biblioteca en QThread (nunca bloquea la UI)."""
        if self._scanner is not None and self._scanner.isRunning():
            return
        self._remember_scan_folder(folder)
        self._action_scan.setEnabled(False)
        self.statusBar().showMessage(tr("Escaneando {folder} ...").format(folder=folder), 0)
        scanner = ScannerThread(self._library.path, folder, self)
        scanner.progress.connect(self._on_scan_progress)
        scanner.scan_finished.connect(self._on_scan_finished)
        scanner.scan_error.connect(self._on_error)
        self._scanner = scanner
        scanner.start()

    def _remember_scan_folder(self, folder: str) -> None:
        """Apunta la carpeta escaneada para poder re-escanearla (Refrescar)."""
        try:
            resolved = str(Path(folder).expanduser().resolve())
        except OSError:
            resolved = str(Path(folder).expanduser())
        folders = self._settings.library_folders
        if resolved not in folders:
            folders.append(resolved)
            self._settings.library_folders = folders

    def _on_refresh_songs(self) -> None:
        """Botón «Refrescar canciones»: re-escanea TODAS las carpetas guardadas.

        A diferencia de «Escanear carpeta...» (una carpeta elegida), el
        refresco busca todas las canciones de las carpetas seleccionadas
        previamente en la biblioteca (las recordadas en QSettings).
        """
        if self._scanner is not None and self._scanner.isRunning():
            self.statusBar().showMessage(tr("Ya hay un escaneo en curso"), ERROR_TIMEOUT_MS)
            return
        folders = [
            folder
            for folder in self._settings.library_folders
            if Path(folder).expanduser().is_dir()
        ]
        if not folders:
            self._songs_table.refresh()
            self._favorites_table.refresh()
            self.statusBar().showMessage(
                tr("Sin carpetas guardadas — «Archivo → Escanear carpeta en biblioteca...»"),
                ERROR_TIMEOUT_MS,
            )
            return
        self._scan_queue = list(folders)
        self._start_next_scan()

    def _start_next_scan(self) -> None:
        """Escanea la siguiente carpeta en cola (o termina la tanda)."""
        if not self._scan_queue:
            self._action_scan.setEnabled(True)
            return
        self._start_scan(self._scan_queue.pop(0))

    def _on_scan_progress(self, processed: int, current: str) -> None:
        self.statusBar().showMessage(
            tr("Escaneando… {processed} archivos ({current})").format(
                processed=processed, current=current
            ),
            0,
        )

    def _on_scan_finished(self, summary: object) -> None:
        """Resumen del escaneo (hilo de UI); sigue la cola si queda carpetas."""
        self._scanner = None
        if self._scan_queue:
            self._start_next_scan()
        else:
            self._action_scan.setEnabled(True)
        if not isinstance(summary, dict):
            return
        message = tr(
            "Biblioteca: {added} añadidas, {updated} actualizadas, {skipped} sin cambios, "
            "{removed} eliminadas"
        ).format(
            added=summary["added"],
            updated=summary["updated"],
            skipped=summary["skipped"],
            removed=summary["removed"],
        )
        if summary.get("errors"):
            message += tr(", {errors} errores").format(errors=summary["errors"])
        if summary.get("cancelled"):
            message += tr(" (escaneo cancelado)")
        self.statusBar().showMessage(message, ERROR_TIMEOUT_MS)
        self._library_panel.refresh()
        self._songs_table.refresh()
        self._favorites_table.refresh()

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
            tr("▶ {name} ({count} pistas en cola)").format(
                name=track.display_name, count=len(tracks)
            ),
            ERROR_TIMEOUT_MS,
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
                tr("{count} pistas en cola — ▶ para reproducir").format(count=len(tracks)),
                ERROR_TIMEOUT_MS,
            )

    def _on_load_playlist(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("Cargar playlist"),
            str(PLAYLISTS_DIR),
            tr("Playlists (*.m3u *.m3u8);;Todos los archivos (*)"),
        )
        if not path:
            return
        try:
            count = self._player.load_playlist(path)
        except OSError as exc:
            self._on_error(tr("No se pudo cargar la playlist: {error}").format(error=exc))
            return
        self.statusBar().showMessage(
            tr("Playlist cargada ({count} pistas en cola)").format(count=count), ERROR_TIMEOUT_MS
        )
        if count:
            current = self._player.current_track
            if current is not None:
                self._show_track(current)

    def _on_save_playlist(self) -> None:
        if len(self._player.playlist) == 0:
            self.statusBar().showMessage(tr("La playlist está vacía"), ERROR_TIMEOUT_MS)
            return
        suggested = str(PLAYLISTS_DIR / "playlist.m3u")
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("Guardar playlist como"),
            suggested,
            tr("Playlist M3U (*.m3u);;Todos los archivos (*)"),
        )
        if not path:
            return
        if not Path(path).suffix:
            path += ".m3u"
        try:
            self._player.save_playlist(path)
        except OSError as exc:
            self._on_error(tr("No se pudo guardar la playlist: {error}").format(error=exc))
            return
        self.statusBar().showMessage(
            tr("Playlist guardada en {path}").format(path=path), ERROR_TIMEOUT_MS
        )

    def _on_clear_playlist(self) -> None:
        self._player.stop()
        self._player.playlist.clear()
        self._label_title.setText(WINDOW_TITLE)
        self._label_artist.setText("—")
        if self._lyrics_window is not None:
            self._lyrics_window.reset()
        self.statusBar().showMessage(tr("Playlist vaciada"), ERROR_TIMEOUT_MS)

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
        self._label_album.setText(track.album or "")
        self._label_album.setVisible(bool(track.album))
        self._label_format.setText(format_audio_info(track))
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
        play_label = self._shortcut_label("play_pause")
        if playing:
            icon = QStyle.StandardPixmap.SP_MediaPause
            tooltip = f"{tr('Pausar')} ({play_label})"
        elif state == STATE_PAUSED:
            icon = QStyle.StandardPixmap.SP_MediaPlay
            tooltip = f"{tr('Reanudar')} ({play_label})"
        else:
            icon = QStyle.StandardPixmap.SP_MediaPlay
            tooltip = f"{tr('Reproducir')} ({play_label})"
        self._icon_buttons[self._button_play] = icon
        self._button_play.setIcon(self._transport_icon(icon))
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
        elif mode == VIEW_FAVORITOS:
            self._stacked.setCurrentIndex(2)
            self._favorites_table.refresh()  # ★ puede haber cambiado
            action = self._action_view_favoritos
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
        dialog.apply_language.connect(self._on_apply_language)
        dialog.apply_settings.connect(self._apply_notification_settings)
        dialog.apply_appearance.connect(self._apply_appearance_from_dialog)
        dialog.apply_shortcuts.connect(self._apply_shortcuts_from_dialog)
        dialog.test_notification.connect(self._send_test_notification)
        dialog.exec()

    def _on_apply_language(self, code: str) -> None:
        """Ajustes → General: guarda el idioma y reinicia para aplicarlo.

        Si el idioma no cambia, no se reinicia nada. El reinicio se aplaza
        al bucle de eventos (``QTimer.singleShot(0, ...)``) para que el
        diálogo termine de cerrarse antes.
        """
        language = str(code).strip().lower()
        if language == self._settings.language:
            return
        self._settings.language = language
        set_language(language)
        QTimer.singleShot(0, self._restart_app)

    def _restart_app(self) -> None:
        """Relanza PyAmp (mismo proceso/argumentos) para aplicar el idioma."""
        program = sys.executable
        if getattr(sys, "frozen", False):  # binario de PyInstaller
            args = list(sys.argv[1:])
        else:
            args = [str(Path(sys.argv[0]).resolve()), *sys.argv[1:]]
        logger.info("Reiniciando PyAmp para aplicar el idioma (%s)", program)
        QProcess.startDetached(program, args)
        QApplication.quit()

    def _apply_appearance_from_dialog(self, theme_id: str, spectrum: bool, cover: bool) -> None:
        """Ajustes → Apariencia: tema, espectrograma y carátula al vuelo."""
        self._apply_theme_id(str(theme_id))
        if bool(spectrum) != self._action_show_spectrum.isChecked():
            self._action_show_spectrum.setChecked(bool(spectrum))
            self._on_toggle_spectrum(bool(spectrum))
        if bool(cover) != self._action_show_cover.isChecked():
            self._action_show_cover.setChecked(bool(cover))
            self._on_toggle_cover(bool(cover))

    def _apply_shortcuts_from_dialog(self, mapping: dict) -> None:
        """Persiste los atajos elegidos y los reaplica al vuelo."""
        clean = {key: str(value) for key, value in dict(mapping).items()}
        self._settings.shortcuts = clean
        self._apply_shortcuts()
        self.statusBar().showMessage(tr("Atajos de teclado actualizados"), ERROR_TIMEOUT_MS)

    def _apply_notification_settings(self, enabled: bool, timeout_ms: int) -> None:
        """Persiste en QSettings y actualiza el Notifier en caliente."""
        self._settings.notifications_enabled = enabled
        self._settings.notifications_timeout_ms = timeout_ms
        self._notifier.enabled = enabled
        self._notifier.timeout_ms = timeout_ms
        self.statusBar().showMessage(
            tr("Ajustes aplicados: notificaciones {state}, {seconds} s").format(
                state=tr("activadas") if enabled else tr("desactivadas"),
                seconds=timeout_ms // 1000,
            ),
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
            self._notifier.notify(
                tr("Notificación de prueba"), tr("PyAmp funciona correctamente ✓")
            )
        except Exception as exc:  # noqa: BLE001 - nunca romper la UI
            logger.warning("Notificación de prueba falló: %s", exc)
            self.statusBar().showMessage(
                tr("La notificación falló: {error}").format(error=exc), ERROR_TIMEOUT_MS
            )
        else:
            self.statusBar().showMessage(tr("Notificación de prueba enviada"), ERROR_TIMEOUT_MS)

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
            self.statusBar().showMessage(
                tr("Favorito no guardado: {error}").format(error=exc), ERROR_TIMEOUT_MS
            )
            return
        current = self._player.current_track
        if current is not None and current.path == track.path:
            self._button_favorite.setChecked(favorite)
        # Aplazado: evitar reset del modelo dentro de la señal activated.
        QTimer.singleShot(0, self._songs_table.refresh)
        QTimer.singleShot(0, self._favorites_table.refresh)
        self.statusBar().showMessage(
            tr("★ Añadida a favoritos") if favorite else tr("★ Quitada de favoritos"),
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
            tr("Espectrograma visible") if checked else tr("Espectrograma oculto"),
            ERROR_TIMEOUT_MS,
        )

    def _on_toggle_cover(self, checked: bool) -> None:
        """Ver → Mostrar imagen: oculta/muestra y persiste."""
        self._settings.show_cover = checked
        self._cover_label.setVisible(checked)
        self.statusBar().showMessage(
            tr("Imagen visible") if checked else tr("Imagen oculta"), ERROR_TIMEOUT_MS
        )

    # ------------------------------------------------------------ temas (0.1.6)
    def _apply_theme_id(self, theme_id: str) -> None:
        """Aplica un tema por id y lo persiste (menú Ver o Ajustes)."""
        self._apply_theme(get_theme(theme_id), save=True)

    def _apply_theme(self, theme: Theme, *, save: bool = True) -> None:
        """Aplica el tema a toda la app (QSS global, cabecera y espectro)."""
        self._theme = theme
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setStyleSheet(theme.qss)  # vacío si es «native» (estilo del sistema)
        self._header_panel.setStyleSheet(theme.header_stylesheet())
        self._spectrum.set_hue(theme.spectrum_hue)
        self._spectrum.set_spectrum_colors(theme.color("spectrum_bg"), theme.color("spectrum_line"))
        self._refresh_icon_buttons()
        action = self._theme_actions.get(theme.id)
        if action is not None:
            action.setChecked(True)
        if save:
            self._settings.theme_id = theme.id
        logger.info("Tema aplicado: %s (%s)", theme.name, theme.id)

    # ------------------------------------------------- 0.1.6: aleatorio/repetir
    def _on_shuffle_toggled(self, checked: bool) -> None:
        """🔀: alterna el modo aleatorio (persistido en QSettings)."""
        self._player.shuffle = checked
        self.statusBar().showMessage(
            tr("Aleatorio activado") if checked else tr("Aleatorio desactivado"), ERROR_TIMEOUT_MS
        )

    def _on_repeat_toggled(self, checked: bool) -> None:
        """🔁: alterna la repetición de playlist (persistida en QSettings)."""
        self._player.repeat = checked
        self.statusBar().showMessage(
            tr("Repetición activada") if checked else tr("Repetición desactivada"), ERROR_TIMEOUT_MS
        )

    # ------------------------------------------------ 0.1.6: editor de letras
    def _on_edit_lyrics(self) -> None:
        """Editar → Editar letra: crea/edita el .lrc de la canción elegida.

        La pista es la seleccionada en la vista activa (o, si no hay
        selección, la que está sonando). Si ya tiene letra se abre ese
        archivo; si no, se guardará una nueva con el nombre de la canción.
        """
        track = self._selected_track()
        if track is None or not track.path:
            self.statusBar().showMessage(
                tr("Selecciona una canción para editar su letra (o reproduce una)"),
                ERROR_TIMEOUT_MS,
            )
            return
        dialog = LyricsEditorDialog(track, self)
        dialog.lyrics_saved.connect(self._on_lyrics_saved)
        dialog.exec()

    def _selected_track(self) -> Track | None:
        """Pista seleccionada en la vista activa, o la que está sonando."""
        current = self._stacked.currentWidget()
        if current is self._library_panel:
            for item in self._library_panel.tree.selectedItems():
                track = item.data(0, ROLE_TRACK)
                if isinstance(track, Track):
                    return track
        elif current is self._favorites_table:
            selected = self._favorites_table.selected_track()
            if selected is not None:
                return selected
        else:
            selected = self._songs_table.selected_track()
            if selected is not None:
                return selected
        return self._player.current_track

    def _on_lyrics_saved(self, path: str) -> None:
        """Letra guardada: recargar la ventana de letra si está visible."""
        self.statusBar().showMessage(
            tr("Letra guardada en {path}").format(path=path), ERROR_TIMEOUT_MS
        )
        track = self._player.current_track
        if (
            self._lyrics_window is not None
            and self._lyrics_window.isVisible()
            and track is not None
        ):
            self._lyrics_window.show_track(track)

    def _on_show_lyrics(self) -> None:
        """Ver → Ver letra: ventana al lado con la letra de la pista actual."""
        if self._lyrics_window is None:
            self._lyrics_window = LyricsWindow(self)
            self._lyrics_window.destroyed.connect(self._on_lyrics_destroyed)
            # Doble clic en una línea → saltar ahí y seguir reproduciendo.
            self._lyrics_window.seek_requested.connect(self._on_lyrics_seek)
        window = self._lyrics_window
        window.show_track(self._player.current_track)
        window.show()
        window.raise_()
        window.activateWindow()
        # Justo al lado de la principal (el compositor puede ajustarlo).
        window.move(self.x() + self.width() + LYRICS_GAP_PX, self.y())

    def _on_lyrics_seek(self, position_ms: int) -> None:
        """La letra pedida: salta el cursor y la reproducción continúa."""
        if self._player.current_track is None:
            return
        if self._player.state == STATE_STOPPED:
            # Arranca y, en cuanto VLC tiene la pista, salta al punto pedido.
            self._player.play()
            QTimer.singleShot(150, lambda: self._player.seek(position_ms))
        else:
            self._player.seek(position_ms)
            if self._player.state == STATE_PAUSED:
                self._player.play()  # reanuda desde ese punto
        self.statusBar().showMessage(
            tr("▶ Saltado a {time} (letra)").format(time=format_time(position_ms)), ERROR_TIMEOUT_MS
        )

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
        standard = (
            QStyle.StandardPixmap.SP_MediaVolumeMuted
            if muted
            else QStyle.StandardPixmap.SP_MediaVolume
        )
        self._icon_buttons[self._button_mute] = standard
        self._button_mute.setIcon(self._transport_icon(standard))

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
