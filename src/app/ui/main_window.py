from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from datetime import datetime
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
    QMouseEvent,
    QPainter,
    QPalette,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
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
    VIEW_CANCIONES,
    VIEW_FAVORITOS,
    VIEW_RADIO,
    Settings,
    get_settings,
)
from app.i18n import set_language, tr
from app.library.covers import extract_cover
from app.library.database import LibraryDatabase, previous_month_key
from app.library.metadata import format_audio_info, read_metadata, write_metadata
from app.library.models import RadioStation, Track
from app.library.scanner import ScannerThread
from app.lyrics.online import OnlineLyricsWorker
from app.notifications.notifier import Notifier
from app.radio import RadioLibrary, RadioSearchWorker
from app.themes import DEFAULT_THEME_ID, Theme, get_theme, load_themes, reload_themes
from app.ui.cover_widget import CoverLabel
from app.ui.history_window import HistoryWindow
from app.ui.lyrics_editor import LyricsEditorDialog
from app.ui.lyrics_window import LyricsWindow, find_lrc_path
from app.ui.metadata_editor import MetadataEditorDialog
from app.ui.radio_panel import RadioPanel
from app.ui.settings_dialog import SettingsDialog
from app.ui.songs_table import (
    ACTION_DELETE,
    ACTION_EDIT_METADATA,
    ACTION_FAVORITE,
    ACTION_HIDE,
    ACTION_RENAME,
    ACTION_UNFAVORITE,
    ACTION_UNHIDE,
    SongsTable,
)
from app.ui.spectrum_widget import SpectrumWidget
from app.utils.paths import PLAYLISTS_DIR
from app.utils.time_format import format_time
from app.version import __version__

logger = logging.getLogger(__name__)

WINDOW_TITLE = "PyAmp"
ERROR_TIMEOUT_MS = 10000
VOLUME_SLIDER_WIDTH = 140

#: Separación (px) entre la ventana principal y la de letra.
LYRICS_GAP_PX = 8


class _FolderLoader(QThread):

    #: Emite la lista de rutas encontradas (llega encolada al hilo de UI).
    paths_loaded = Signal(list)

    def __init__(self, folder: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._folder = folder

    def run(self) -> None:
        try:
            paths = collect_audio_files(self._folder)
        except Exception as exc:  # noqa: BLE001 - un error de disco no debe tumbar la app
            logger.error("Error escaneando %s: %s", self._folder, exc)
            paths = []
        self.paths_loaded.emit(paths)


class ClickSlider(QSlider):
    """Deslizador horizontal que salta a la posición pulsada y permite arrastrar."""

    def _value_at(self, x: float) -> int:
        return QStyle.sliderValueFromPosition(
            self.minimum(), self.maximum(), int(x), max(1, self.width())
        )

    def _move_to(self, x: float) -> None:
        value = self._value_at(x)
        self.setValue(value)
        self.sliderMoved.emit(value)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.orientation() == (
            Qt.Orientation.Horizontal
        ):
            # setSliderDown inicia el arrastre y hace que la barra no sea
            # sobrescrita por position_changed mientras se mueve.
            self.setSliderDown(True)
            self._move_to(event.position().x())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self.isSliderDown():
            self._move_to(event.position().x())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.isSliderDown():
            self._move_to(event.position().x())
            # setSliderDown(False) emite sliderReleased y aplica el seek.
            self.setSliderDown(False)
            event.accept()
            return
        super().mouseReleaseEvent(event)


def _assets_dir() -> Path:
    base = getattr(sys, "_MEIPASS", None)
    return (Path(str(base)) if base else Path(__file__).resolve().parents[3]) / "assets"


class MainWindow(QMainWindow):

    #: Peticiones MPRIS llegadas del bus (hilo ajeno → hilo de UI).
    _raise_requested = Signal()
    _quit_requested = Signal()
    #: Pulsar la notificación del historial (hilo D-Bus → hilo de UI).
    _history_requested = Signal()

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
        self._lyrics_search: OnlineLyricsWorker | None = None
        self._lyrics_pending: Track | None = None
        self._radio_station: RadioStation | None = None
        self._radio_search: RadioSearchWorker | None = None
        #: True mientras la vista activa es la de radio (oculta transporte local).
        self._radio_view = False
        self._shortcut_actions: dict[str, QAction] = {}
        self._theme_actions: dict[str, QAction] = {}
        #: Icono nativo de cada botón de transporte (para re-teñirlo por tema).
        self._icon_buttons: dict[QToolButton, QStyle.StandardPixmap] = {}
        self._emoji_buttons: dict[QToolButton, str] = {}
        self._theme: Theme = get_theme(self._settings.theme_id or DEFAULT_THEME_ID)

        self._build_ui()
        self._connect_signals()
        self._restore_state()
        self._init_mpris()
        self._maybe_notify_history()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumSize(480, 360)
        self.resize(self._settings.window_width, self._settings.window_height)

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
        self._slider_seek = ClickSlider(Qt.Orientation.Horizontal)
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
            self._on_prev,
        )
        self._button_play = self._make_button(
            QStyle.StandardPixmap.SP_MediaPlay,
            f"{tr('Reproducir')} ({SHORTCUT_DEFAULTS['play_pause']})",
            self._on_play_clicked,
        )
        self._button_next = self._make_button(
            QStyle.StandardPixmap.SP_MediaSkipForward,
            f"{tr('Siguiente')} ({SHORTCUT_DEFAULTS['next']})",
            self._on_next,
        )
        for button in (
            self._button_prev,
            self._button_play,
            self._button_next,
        ):
            transport_row.addWidget(button)

        self._button_shuffle = QToolButton()
        # El emoji se usa como imagen: Qt no pinta el texto emoji en todos
        # los equipos (Breeze/KDE lo dejaba en blanco).
        self._button_shuffle.setIcon(self._emoji_icon("shuffle"))
        self._emoji_buttons[self._button_shuffle] = "shuffle"
        self._button_shuffle.setCheckable(True)
        self._button_shuffle.setToolTip(tr("Aleatorio: siguiente pista al azar"))
        self._button_shuffle.setAccessibleName(tr("Aleatorio"))
        self._button_shuffle.setChecked(self._settings.shuffle)
        self._button_shuffle.toggled.connect(self._on_shuffle_toggled)
        transport_row.addWidget(self._button_shuffle)

        self._button_repeat = QToolButton()
        self._button_repeat.setIcon(self._emoji_icon("repeat"))
        self._emoji_buttons[self._button_repeat] = "repeat"
        self._button_repeat.setCheckable(True)
        self._button_repeat.setToolTip(tr("Repetir: repite la pista actual una vez y se desactiva"))
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

        # --- vistas a todo el ancho (menú Ver): canciones | favoritos | radio ---
        self._songs_table = SongsTable(self._library)
        self._favorites_table = SongsTable(self._library)
        self._favorites_table.set_favorites_only(True)
        show_hidden = self._settings.show_hidden
        self._songs_table.set_show_hidden(show_hidden)
        self._favorites_table.set_show_hidden(show_hidden)
        self._radio = RadioLibrary(self._settings)
        self._radio_panel = RadioPanel(self._radio)
        self._stacked = QStackedWidget()
        self._stacked.addWidget(self._songs_table)  # índice 0: canciones
        self._stacked.addWidget(self._favorites_table)  # índice 1: favoritos
        self._stacked.addWidget(self._radio_panel)  # índice 2: radio
        layout.addWidget(self._stacked, stretch=1)

        self.setCentralWidget(central)
        self._build_menus()
        self._apply_theme(self._theme, save=False)
        self._on_state_changed(STATE_STOPPED)
        self._update_mute_icon(self._settings.muted)
        self._cover_label.setVisible(self._settings.show_cover)
        self._songs_table.refresh()
        self._favorites_table.refresh()
        self._set_view(self._settings.view_mode, save=False)

    def _build_menus(self) -> None:
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
        self._action_view_favoritos = QAction(tr("F&avoritos (★)"), self)
        self._action_view_favoritos.setCheckable(True)
        self._action_view_favoritos.triggered.connect(lambda: self._set_view(VIEW_FAVORITOS))
        self._register_shortcut("view_favoritos", self._action_view_favoritos)
        self._action_view_radio = QAction(tr("&Radio online"), self)
        self._action_view_radio.setCheckable(True)
        self._action_view_radio.triggered.connect(lambda: self._set_view(VIEW_RADIO))
        self._register_shortcut("view_radio", self._action_view_radio)
        view_group = QActionGroup(self)
        view_group.setExclusive(True)
        view_group.addAction(self._action_view_canciones)
        view_group.addAction(self._action_view_favoritos)
        view_group.addAction(self._action_view_radio)
        view_menu.addAction(self._action_view_canciones)
        view_menu.addAction(self._action_view_favoritos)
        view_menu.addAction(self._action_view_radio)

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
        self._themes_menu = view_menu.addMenu(tr("&Tema"))
        self._theme_group = QActionGroup(self)
        self._theme_group.setExclusive(True)
        self._populate_theme_menu()

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

        # --- menú Historial: ranking mensual (siempre visible) ---
        history_menu = self.menuBar().addMenu(tr("&Historial"))
        action_history = QAction(tr("Ver historial del mes"), self)
        action_history.triggered.connect(self._on_show_history)
        history_menu.addAction(action_history)

        self._build_shortcuts()

    def _register_shortcut(self, shortcut_id: str, action: QAction) -> None:
        self._shortcut_actions[shortcut_id] = action
        default = SHORTCUT_DEFAULTS[shortcut_id]
        sequence = self._settings.shortcuts.get(shortcut_id, default)
        action.setShortcut(QKeySequence(sequence))

    def _apply_shortcuts(self) -> None:
        custom = self._settings.shortcuts
        for shortcut_id, action in self._shortcut_actions.items():
            sequence = custom.get(shortcut_id, SHORTCUT_DEFAULTS[shortcut_id])
            action.setShortcut(QKeySequence(sequence))
        self._refresh_shortcut_labels()

    def _shortcut_label(self, shortcut_id: str) -> str:
        action = self._shortcut_actions.get(shortcut_id)
        if action is None:
            return SHORTCUT_DEFAULTS[shortcut_id]
        return action.shortcut().toString(QKeySequence.SequenceFormat.PortableText)

    def _refresh_shortcut_labels(self) -> None:
        prev_label = f"{tr('Anterior')} ({self._shortcut_label('prev')})"
        self._button_prev.setToolTip(prev_label)
        self._button_prev.setAccessibleName(prev_label)
        next_label = f"{tr('Siguiente')} ({self._shortcut_label('next')})"
        self._button_next.setToolTip(next_label)
        self._button_next.setAccessibleName(next_label)
        self._on_state_changed(self._player.state)

    def _build_shortcuts(self) -> None:
        media_shortcuts: tuple[tuple[QKeySequence, str, Callable[..., Any]], ...] = (
            (
                QKeySequence(Qt.Key.Key_MediaPrevious),
                tr("Pista anterior (multimedia)"),
                self._on_prev,
            ),
            (
                QKeySequence(Qt.Key.Key_MediaTogglePlayPause),
                tr("Reproducir/pausar (multimedia)"),
                self._on_play_clicked,
            ),
            (
                QKeySequence(Qt.Key.Key_MediaPlay),
                tr("Reproducir (multimedia)"),
                self._on_play_clicked,
            ),
            (
                QKeySequence(Qt.Key.Key_MediaPause),
                tr("Pausar (multimedia)"),
                self._player.pause,
            ),
            (
                QKeySequence(Qt.Key.Key_MediaNext),
                tr("Pista siguiente (multimedia)"),
                self._on_next,
            ),
        )
        for sequence, name, slot in media_shortcuts:
            action = QAction(name, self)
            action.setShortcut(sequence)
            action.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
            action.triggered.connect(slot)
            self.addAction(action)  # la ventana mantiene viva la acción

        for shortcut_id, name, slot in (
            ("prev", tr("Pista anterior"), self._on_prev),
            ("play_pause", tr("Reproducir/pausar"), self._on_play_clicked),
            ("next", tr("Pista siguiente"), self._on_next),
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
        button = QToolButton()
        self._icon_buttons[button] = icon
        button.setIcon(self._transport_icon(icon))
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.clicked.connect(slot)
        return button

    def _icon_color(self) -> QColor:
        # Los temas nativos usan los botones del sistema: el color del icono
        # debe ser el del texto real del botón, no el del tema de PyAmp.
        if self._theme.native:
            return self.palette().color(QPalette.ColorRole.ButtonText)
        return QColor(self._theme.color("icon"))

    def _transport_icon(self, standard: QStyle.StandardPixmap) -> QIcon:
        base = self.style().standardIcon(standard)
        pixmap = base.pixmap(24, 24)
        if pixmap.isNull():
            return base
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), self._icon_color())
        painter.end()
        return QIcon(pixmap)

    def _emoji_icon(self, name: str) -> QIcon:
        path = _assets_dir() / f"{name}.png"
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return QIcon()
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), self._icon_color())
        painter.end()
        return QIcon(pixmap)

    def _refresh_icon_buttons(self) -> None:
        for button, standard in self._icon_buttons.items():
            button.setIcon(self._transport_icon(standard))
        for button, name in self._emoji_buttons.items():
            button.setIcon(self._emoji_icon(name))

    # --------------------------------------------------------------- señales
    def _connect_signals(self) -> None:
        player = self._player
        player.track_changed.connect(self._on_track_changed)
        player.playback_state_changed.connect(self._on_state_changed)
        player.position_changed.connect(self._on_position_changed)
        player.duration_changed.connect(self._on_duration_changed)
        player.volume_changed.connect(self._on_volume_changed)
        player.error_occurred.connect(self._on_error)
        player.repeat_consumed.connect(self._on_repeat_consumed)
        # El espectro se alimenta del audio decodificado por VLC, nunca de
        # una captura del micrófono ni de la salida del sistema.
        player.spectrum_samples.connect(self._spectrum.push_samples)
        # La biblioteca acumula estadísticas en cada cambio de pista real.
        player.track_changed.connect(self._record_library_play)

        # Peticiones MPRIS (llegan desde el hilo del bus → hilo de UI).
        self._raise_requested.connect(self._raise_and_activate)
        self._quit_requested.connect(self.close)
        self._history_requested.connect(self._on_show_history)

        self._songs_table.track_activated.connect(self._on_library_track_activated)
        self._songs_table.favorite_toggled.connect(self._on_favorite_row_toggled)
        self._songs_table.refresh_requested.connect(self._on_refresh_songs)
        self._songs_table.action_requested.connect(self._on_songs_action)
        self._favorites_table.track_activated.connect(self._on_library_track_activated)
        self._favorites_table.favorite_toggled.connect(self._on_favorite_row_toggled)
        self._favorites_table.refresh_requested.connect(self._on_refresh_songs)
        self._favorites_table.action_requested.connect(self._on_songs_action)
        self._radio_panel.play_requested.connect(self._on_radio_play)
        self._radio_panel.stop_requested.connect(self._on_radio_stop)
        self._radio_panel.station_selected.connect(self._on_radio_selection)
        self._radio_panel.search_requested.connect(self._on_radio_search)

        if not player.is_available:
            self.statusBar().showMessage(player.backend_error or tr("Audio no disponible"), 0)

    # ------------------------------------------------------------- acciones
    def _on_open_files(self) -> None:
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
        # La carpeta también pasa a la biblioteca (en 2.º plano),
        # de modo que las canciones siempre aparecen en la vista Canciones.
        self._start_scan(folder)

    def _on_paths_loaded(self, paths: list) -> None:
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

    # ------------------------------------------------------ biblioteca
    def _on_scan_library(self) -> None:
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
        try:
            resolved = str(Path(folder).expanduser().resolve())
        except OSError:
            resolved = str(Path(folder).expanduser())
        folders = self._settings.library_folders
        if resolved not in folders:
            folders.append(resolved)
            self._settings.library_folders = folders

    def _on_refresh_songs(self) -> None:
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
        self._songs_table.refresh()
        self._favorites_table.refresh()

    def _record_library_play(self, track: object) -> None:
        if not isinstance(track, Track) or not track.path:
            return
        if not Path(track.path).is_file():  # las emisoras de radio no van a la BD
            return
        try:
            self._library.record_play_by_path(track.path)
        except Exception as exc:  # noqa: BLE001 - la música no se detiene
            logger.warning("No se pudo registrar la reproducción: %s", exc)

    def _on_library_track_activated(self, track: object, context: object) -> None:
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

    def _cover_for(self, track: Track) -> str | None:
        if track.cover_path:
            return track.cover_path
        try:
            return extract_cover(track.path)
        except Exception as exc:  # noqa: BLE001 - la música no se detiene
            logger.debug("Sin carátula para %s: %s", track.path, exc)
            return None

    def _add_paths(self, paths: list[str]) -> None:
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
        if isinstance(track, Track):
            self._show_track(track)
            self._ensure_online_lyrics(track)

    def _show_track(self, track: Track) -> None:
        self._label_title.setText(track.display_title)
        self._label_title.setToolTip(track.path)
        self._label_artist.setText(track.display_artist)
        self._label_artist.setToolTip(track.path)
        self._label_album.setText(track.album or "")
        self._label_album.setVisible(bool(track.album))
        self._label_format.setText(format_audio_info(track))
        if "://" in track.path:
            self._show_station_badge(track.display_title)
            cover = None
        else:
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

    def _reset_header(self) -> None:
        # Cabecera en reposo: sin restos de la última canción.
        self._label_title.setText(WINDOW_TITLE)
        self._label_title.setToolTip("")
        self._label_artist.setText("")
        self._label_artist.setToolTip("")
        self._label_album.setText("")
        self._label_album.setVisible(False)
        self._label_format.setText("")
        self._cover_label.set_cover(None)
        self._duration_ms = 0
        self._slider_seek.setRange(0, 0)
        self._slider_seek.setValue(0)
        self._update_time_label(0)
        self._button_favorite.setEnabled(False)
        self._button_favorite.setChecked(False)
        if self._mpris is not None:
            self._mpris.update_metadata("")

    def _on_state_changed(self, state: str) -> None:
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

    # -------------------------------------------------------- vistas/ajustes
    def _on_play_clicked(self) -> None:
        # En radio, si no hay nada sonando, el botón retoma la última emisora
        # escuchada en lugar de arrancar la lista de canciones locales.
        if self._radio_view and self._player.state == STATE_STOPPED and not self._player.is_stream:
            self._play_last_radio()
            return
        self._player.toggle_pause()

    def _play_last_radio(self) -> bool:
        data = self._settings.last_radio_station
        if data is None:
            self.statusBar().showMessage(
                tr("Selecciona una emisora para reproducirla"), ERROR_TIMEOUT_MS
            )
            return False
        station = RadioStation(
            name=data["name"] or data["url"],
            url=data["url"],
            genre=data["genre"],
            country=data["country"],
        )
        self._radio_station = station
        self._on_radio_play(station)
        return self._player.state == STATE_PLAYING

    def _on_prev(self) -> None:
        # En la vista de radio, anterior/siguiente cambian de emisora.
        if self._radio_view:
            self._radio_panel.select_relative(-1)
        else:
            self._player.prev()

    def _on_next(self) -> None:
        if self._radio_view:
            self._radio_panel.select_relative(1)
        else:
            self._player.next()

    def _set_view(self, mode: str, *, save: bool = True) -> None:
        if mode == VIEW_FAVORITOS:
            self._stacked.setCurrentIndex(1)
            self._favorites_table.refresh()  # ★ puede haber cambiado
            action = self._action_view_favoritos
        elif mode == VIEW_RADIO:
            self._stacked.setCurrentIndex(2)
            action = self._action_view_radio
        else:
            mode = VIEW_CANCIONES
            self._stacked.setCurrentIndex(0)
            action = self._action_view_canciones
        action.setChecked(True)
        self._update_radio_controls(mode == VIEW_RADIO)
        if mode == VIEW_RADIO:
            # Al entrar en Radio sin reproducción no se arrastra la canción
            # anterior: la cabecera vuelve a su estado de reposo.
            if self._player.state == STATE_STOPPED and not self._player.is_stream:
                self._reset_header()
        elif not self._player.is_stream and self._player.current_track is not None:
            self._show_track(self._player.current_track)
        if save:
            self._settings.view_mode = mode

    def _update_radio_controls(self, radio: bool) -> None:
        # La radio no usa la barra de posición, el aleatorio, el repetir ni
        # el favorito (las emisoras no son pistas).
        self._radio_view = radio
        self._slider_seek.setVisible(not radio)
        self._button_shuffle.setVisible(not radio)
        self._button_repeat.setVisible(not radio)
        self._button_favorite.setVisible(not radio)
        self._update_time_label(self._slider_seek.value())

    def _on_radio_play(self, station: object) -> None:
        if not isinstance(station, RadioStation):
            return
        self._radio_station = station
        if self._player.play_stream(station.url, station.name, tr("Radio online")):
            self._settings.last_radio_station = {
                "name": station.name,
                "url": station.url,
                "genre": station.genre,
                "country": station.country,
            }
            self._radio_panel.show_message(tr("Reproduciendo {name}").format(name=station.name))
            self.statusBar().showMessage(
                tr("▶ {name} (radio)").format(name=station.name), ERROR_TIMEOUT_MS
            )

    def _on_radio_stop(self) -> None:
        self._player.stop()
        self._radio_station = None
        self._radio_panel.show_message(tr("Radio detenida"))

    def _on_radio_search(self) -> None:
        if self._radio_search is not None and self._radio_search.isRunning():
            return
        self._radio_panel.set_searching(True)
        worker = RadioSearchWorker(self)
        self._radio_search = worker
        worker.finished_ok.connect(self._on_radio_search_done)
        worker.failed.connect(self._on_radio_search_failed)
        worker.finished.connect(self._on_radio_search_finished)
        worker.start()

    def _on_radio_search_done(self, stations: object) -> None:
        results = stations if isinstance(stations, list) else []
        known = {station.url for station in self._radio.stations()}
        merged = self._radio.found_stations()
        added = 0
        for station in results:
            if not isinstance(station, RadioStation) or station.url in known:
                continue
            known.add(station.url)
            merged.append(station)
            added += 1
        self._radio.set_found_stations(merged)
        self._radio_panel.refresh()
        self.statusBar().showMessage(
            tr("Se encontraron {n} emisoras").format(n=added), ERROR_TIMEOUT_MS
        )

    def _on_radio_search_failed(self, message: str) -> None:
        self.statusBar().showMessage(
            tr("No se pudieron buscar emisoras: {error}").format(error=message), ERROR_TIMEOUT_MS
        )

    def _on_radio_search_finished(self) -> None:
        self._radio_panel.set_searching(False)
        self._radio_search = None

    def _on_radio_selection(self, station: object) -> None:
        if isinstance(station, RadioStation):
            self._radio_station = station
            self._show_station_badge(station.name)

    def _show_station_badge(self, name: str) -> None:
        self._cover_label.setVisible(self._settings.show_cover)
        if not self._settings.show_cover:
            return
        self._cover_label.set_station_badge(
            name, self._theme.color("accent"), self._theme.color("accent_text")
        )

    def _on_songs_action(self, action: str, track: object) -> None:
        if not isinstance(track, Track) or not track.path:
            return
        if action == ACTION_FAVORITE:
            if not track.is_favorite:
                self._toggle_favorite(track)
        elif action == ACTION_UNFAVORITE:
            if track.is_favorite:
                self._toggle_favorite(track)
        elif action == ACTION_HIDE:
            self._set_hidden(track, True)
        elif action == ACTION_UNHIDE:
            self._set_hidden(track, False)
        elif action == ACTION_RENAME:
            self._rename_track(track)
        elif action == ACTION_DELETE:
            self._delete_track(track)
        elif action == ACTION_EDIT_METADATA:
            self._edit_track_metadata(track)

    def _set_hidden(self, track: Track, hidden: bool) -> None:
        try:
            self._library.set_hidden(track.path, hidden)
        except Exception as exc:  # noqa: BLE001 - la música no se detiene
            logger.warning("No se pudo ocultar/mostrar: %s", exc)
            return
        track.is_hidden = hidden
        self._songs_table.refresh()
        self._favorites_table.refresh()
        self.statusBar().showMessage(
            tr("Pista oculta") if hidden else tr("Pista visible"), ERROR_TIMEOUT_MS
        )

    def _rename_track(self, track: Track) -> None:
        source = Path(track.path)
        if not source.is_file():
            self._on_error(tr("No se encontró el archivo: {path}").format(path=track.path))
            return
        new_stem, accepted = QInputDialog.getText(
            self, tr("Renombrar"), tr("Nuevo nombre:"), text=source.stem
        )
        new_stem = str(new_stem).strip()
        if not accepted or not new_stem or new_stem == source.stem:
            return
        target = source.with_name(new_stem + source.suffix)
        if target.exists():
            self._on_error(tr("Ya existe un archivo con ese nombre"))
            return
        try:
            source.rename(target)
        except OSError as exc:
            self._on_error(tr("No se pudo renombrar: {error}").format(error=exc))
            return
        new_path = str(target)
        try:
            self._library.rename_track_path(track.path, new_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("No se pudo actualizar la ruta en la biblioteca: %s", exc)
        self._player.playlist.rename_path(track.path, new_path)
        track.path = new_path
        self._songs_table.refresh()
        self._favorites_table.refresh()
        current = self._player.current_track
        if current is not None and current.path == new_path:
            self._show_track(current)
        self.statusBar().showMessage(
            tr("Renombrado a {name}").format(name=target.name), ERROR_TIMEOUT_MS
        )

    def _delete_track(self, track: Track) -> None:
        confirm = QMessageBox.question(
            self,
            tr("Eliminar"),
            tr("¿Quitar «{name}» de la biblioteca?\n(El archivo no se borra del disco.)").format(
                name=track.display_name
            ),
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self._library.remove_track(track.path)
        except Exception as exc:  # noqa: BLE001
            self._on_error(tr("No se pudo eliminar: {error}").format(error=exc))
            return
        self._songs_table.refresh()
        self._favorites_table.refresh()
        self.statusBar().showMessage(tr("Pista eliminada de la biblioteca"), ERROR_TIMEOUT_MS)

    def _edit_track_metadata(self, track: Track) -> None:
        dialog = MetadataEditorDialog(track, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            write_metadata(track.path, values)
        except Exception as exc:  # noqa: BLE001 - un tag no debe tumbar la app
            self._on_error(tr("No se pudo guardar la metadata: {error}").format(error=exc))
            return
        for field, value in values.items():
            setattr(track, field, value)
        try:
            self._library.update_track_fields(track.path, values)
        except Exception as exc:  # noqa: BLE001
            logger.warning("No se pudo actualizar la biblioteca: %s", exc)
        self._songs_table.refresh()
        self._favorites_table.refresh()
        current = self._player.current_track
        if current is not None and current.path == track.path:
            self._show_track(current)
        self.statusBar().showMessage(tr("Metadata actualizada"), ERROR_TIMEOUT_MS)

    def _on_open_settings(self) -> None:
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
        dialog.apply_window_size.connect(self._apply_window_size_from_dialog)
        dialog.apply_show_hidden.connect(self._apply_show_hidden_from_dialog)
        dialog.apply_shortcuts.connect(self._apply_shortcuts_from_dialog)
        dialog.test_notification.connect(self._send_test_notification)
        dialog.exec()

    def _on_apply_language(self, code: str) -> None:
        language = str(code).strip().lower()
        if language == self._settings.language:
            return
        self._settings.language = language
        set_language(language)
        QTimer.singleShot(0, self._restart_app)

    def _restart_app(self) -> None:
        program = sys.executable
        if getattr(sys, "frozen", False):  # binario de PyInstaller
            args = list(sys.argv[1:])
        else:
            args = [str(Path(sys.argv[0]).resolve()), *sys.argv[1:]]
        logger.info("Reiniciando PyAmp para aplicar el idioma (%s)", program)
        QProcess.startDetached(program, args)
        QApplication.quit()

    def _apply_appearance_from_dialog(self, theme_id: str, spectrum: bool, cover: bool) -> None:
        reload_themes()
        self._populate_theme_menu()
        self._apply_theme_id(str(theme_id))
        if bool(spectrum) != self._action_show_spectrum.isChecked():
            self._action_show_spectrum.setChecked(bool(spectrum))
            self._on_toggle_spectrum(bool(spectrum))
        if bool(cover) != self._action_show_cover.isChecked():
            self._action_show_cover.setChecked(bool(cover))
            self._on_toggle_cover(bool(cover))

    def _apply_window_size_from_dialog(self, width: int, height: int) -> None:
        self._settings.window_width = int(width)
        self._settings.window_height = int(height)
        self.resize(self._settings.window_width, self._settings.window_height)
        self.statusBar().showMessage(
            tr("Tamaño de ventana: {width}×{height}").format(
                width=self._settings.window_width, height=self._settings.window_height
            ),
            ERROR_TIMEOUT_MS,
        )

    def _apply_show_hidden_from_dialog(self, show_hidden: bool) -> None:
        self._settings.show_hidden = bool(show_hidden)
        self._songs_table.set_show_hidden(bool(show_hidden))
        self._favorites_table.set_show_hidden(bool(show_hidden))
        self.statusBar().showMessage(
            tr("Mostrando archivos ocultos") if show_hidden else tr("Ocultando archivos ocultos"),
            ERROR_TIMEOUT_MS,
        )

    def _apply_shortcuts_from_dialog(self, mapping: dict) -> None:
        clean = {key: str(value) for key, value in dict(mapping).items()}
        self._settings.shortcuts = clean
        self._apply_shortcuts()
        self.statusBar().showMessage(tr("Atajos de teclado actualizados"), ERROR_TIMEOUT_MS)

    def _apply_notification_settings(self, enabled: bool, timeout_ms: int) -> None:
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
        try:
            self._notifier.notify(tr("Notificación de prueba"), tr("PyAmp funciona correctamente"))
        except Exception as exc:  # noqa: BLE001 - nunca romper la UI
            logger.warning("Notificación de prueba falló: %s", exc)
            self.statusBar().showMessage(
                tr("La notificación falló: {error}").format(error=exc), ERROR_TIMEOUT_MS
            )
        else:
            self.statusBar().showMessage(tr("Notificación de prueba enviada"), ERROR_TIMEOUT_MS)

    def _on_favorite_clicked(self) -> None:
        track = self._player.current_track
        if track is None or not track.path:
            self._button_favorite.setChecked(False)
            return
        self._toggle_favorite(track)

    def _on_favorite_row_toggled(self, track: object) -> None:
        if isinstance(track, Track) and track.path:
            self._toggle_favorite(track)

    def _toggle_favorite(self, track: Track) -> None:
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

    # -------------------------------------------------- Ver/espectro/letra
    def _on_toggle_spectrum(self, checked: bool) -> None:
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
        self._settings.show_cover = checked
        self._cover_label.setVisible(checked)
        if checked and self._radio_station is not None:
            self._show_station_badge(self._radio_station.name)
        self.statusBar().showMessage(
            tr("Imagen visible") if checked else tr("Imagen oculta"), ERROR_TIMEOUT_MS
        )

    # ------------------------------------------------------------ temas (0.1.6)
    def _populate_theme_menu(self) -> None:
        self._themes_menu.clear()
        for action in list(self._theme_actions.values()):
            self._theme_group.removeAction(action)
        self._theme_actions.clear()
        for theme in load_themes().values():
            action = QAction(theme.name, self)
            action.setCheckable(True)
            action.setData(theme.id)
            action.triggered.connect(lambda checked=False, tid=theme.id: self._apply_theme_id(tid))
            self._theme_group.addAction(action)
            self._themes_menu.addAction(action)
            self._theme_actions[theme.id] = action
        active = self._theme_actions.get(self._theme.id)
        if active is not None:
            active.setChecked(True)

    def _apply_theme_id(self, theme_id: str) -> None:
        self._apply_theme(get_theme(theme_id), save=True)

    def _apply_theme(self, theme: Theme, *, save: bool = True) -> None:
        self._theme = theme
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setStyleSheet(theme.qss)  # vacío si es «native» (estilo del sistema)
        self._header_panel.setStyleSheet(theme.header_stylesheet())
        self._spectrum.set_hue(theme.spectrum_hue)
        # El fondo del espectro iguala el de la cabecera (como en Verde terminal):
        # así Arena clara y los temas personalizados no muestran costura.
        self._spectrum.set_spectrum_colors(theme.color("header_bg"), theme.color("spectrum_line"))
        self._refresh_icon_buttons()
        action = self._theme_actions.get(theme.id)
        if action is not None:
            action.setChecked(True)
        if save:
            self._settings.theme_id = theme.id
        if self._radio_station is not None:
            self._show_station_badge(self._radio_station.name)
        logger.info("Tema aplicado: %s (%s)", theme.name, theme.id)

    # ------------------------------------------------- 0.1.6: aleatorio/repetir
    def _on_shuffle_toggled(self, checked: bool) -> None:
        self._player.shuffle = checked
        self.statusBar().showMessage(
            tr("Aleatorio activado") if checked else tr("Aleatorio desactivado"), ERROR_TIMEOUT_MS
        )

    def _on_repeat_toggled(self, checked: bool) -> None:
        self._player.repeat = checked
        self.statusBar().showMessage(
            tr("Repetición activada") if checked else tr("Repetición desactivada"), ERROR_TIMEOUT_MS
        )

    def _on_repeat_consumed(self) -> None:
        # El reproductor repitió la pista una vez y desactivó el repetir.
        self._button_repeat.blockSignals(True)
        self._button_repeat.setChecked(False)
        self._button_repeat.blockSignals(False)
        self.statusBar().showMessage(
            tr("Repetición desactivada (repetida una vez)"), ERROR_TIMEOUT_MS
        )

    # ------------------------------------------------------------- historial
    def _on_show_history(self) -> None:
        ready = datetime.now().day == 1
        entries = self._library.monthly_top(previous_month_key(), 10) if ready else []
        window = HistoryWindow(entries, ready=ready and bool(entries), parent=self)
        window.exec()

    def _maybe_notify_history(self) -> None:
        # El día 1 de cada mes se avisa; al pulsar la notificación se abre el
        # ranking del último mes terminado. Solo una vez por mes.
        now = datetime.now()
        if now.day != 1 or not self._notifier.enabled:
            return
        month = now.strftime("%Y-%m")
        if self._settings.history_notified_month == month:
            return
        try:
            self._notifier.notify_history(self._history_requested.emit)
        except Exception as exc:  # noqa: BLE001 - nunca romper el arranque
            logger.warning("Aviso del historial falló: %s", exc)
        else:
            self._settings.history_notified_month = month

    # ------------------------------------------------ 0.1.6: editor de letras
    def _on_edit_lyrics(self) -> None:
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
        current = self._stacked.currentWidget()
        if current is self._favorites_table:
            selected = self._favorites_table.selected_track()
        elif current is self._songs_table:
            selected = self._songs_table.selected_track()
        else:
            selected = None
        return selected if selected is not None else self._player.current_track

    def _on_lyrics_saved(self, path: str) -> None:
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

    def _ensure_online_lyrics(self, track: Track) -> None:
        if not track.path or "://" in track.path:
            return
        if find_lrc_path(track.path) is not None:
            return
        if self._lyrics_search is not None and self._lyrics_search.isRunning():
            # Solo se guarda la última pista: las respuestas viejas se ignoran.
            self._lyrics_pending = track
            return
        self._start_online_lyrics(track)

    def _start_online_lyrics(self, track: Track) -> None:
        self._lyrics_pending = None
        worker = OnlineLyricsWorker(track, self)
        self._lyrics_search = worker
        worker.found.connect(self._on_online_lyrics_found)
        worker.missing.connect(self._on_online_lyrics_missing)
        worker.finished.connect(self._on_online_lyrics_finished)
        worker.finished.connect(worker.deleteLater)
        if self._lyrics_window is not None and self._lyrics_window.isVisible():
            self._lyrics_window.set_status(tr("Buscando letra en internet…"))
        worker.start()

    def _on_online_lyrics_found(self, track_path: str, lrc_path: str) -> None:
        current = self._player.current_track
        if current is None or current.path != track_path:
            return
        logger.info("Letra online guardada: %s", lrc_path)
        self.statusBar().showMessage(tr("Letra encontrada en internet"), ERROR_TIMEOUT_MS)
        if self._lyrics_window is not None and self._lyrics_window.isVisible():
            self._lyrics_window.show_track(current)

    def _on_online_lyrics_missing(self, track_path: str) -> None:
        current = self._player.current_track
        if current is None or current.path != track_path:
            return
        if self._lyrics_window is not None and self._lyrics_window.isVisible():
            self._lyrics_window.set_status(tr("No se encontró letra en internet"))

    def _on_online_lyrics_finished(self) -> None:
        self._lyrics_search = None
        pending = self._lyrics_pending
        self._lyrics_pending = None
        current = self._player.current_track
        if pending is not None and current is not None and pending.path == current.path:
            self._ensure_online_lyrics(pending)

    def _on_show_lyrics(self) -> None:
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
        self._lyrics_window = None

    def _init_mpris(self) -> None:
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
        self.show()
        self.raise_()
        self.activateWindow()

    # -------------------------------------------------------------- helpers
    def _update_time_label(self, position_ms: int) -> None:
        if self._radio_view:
            # Un flujo de radio no tiene duración: símbolo de infinito.
            self._label_time.setText("∞ / ∞")
            return
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
                if self._settings.view_mode == VIEW_RADIO:
                    self._reset_header()
                else:
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
        self._settings.window_geometry = self.saveGeometry()
        self._settings.playlist_paths = [track.path for track in self._player.playlist]
        self._settings.playlist_index = self._player.playlist.current_index

        if self._folder_loader is not None and self._folder_loader.isRunning():
            self._folder_loader.wait(5000)
        if self._scanner is not None and self._scanner.isRunning():
            self._scanner.cancel()
            self._scanner.wait(10000)
        if (
            self._lyrics_search is not None
            and self._lyrics_search.isRunning()
            and not self._lyrics_search.wait(8000)
        ):
            self._lyrics_search.terminate()
            self._lyrics_search.wait(1000)
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
