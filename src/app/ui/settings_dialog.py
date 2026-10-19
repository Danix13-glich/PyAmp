"""Diálogo de Ajustes de PyAmp, organizado en pestañas (0.1.6).

Pestañas y opciones (todas con respaldo real en QSettings):

* **General**: idioma de la interfaz (español/English). Al aceptar, la
  ventana principal reinicia la app para aplicarlo.
* **Notificaciones**: activar/desactivar, duración (1–60 s) y botón
  «Probar notificación» (el envío lo hace la ventana, dueña del Notifier).
* **Apariencia**: tema visual (Ver → Temas), espectrograma e imagen.
* **Atajos de teclado**: reasignar las combinaciones del catálogo
  ``SHORTCUT_DEFAULTS`` (las teclas multimedia del hardware quedan fijas).
* **Información**: versión, backend de notificaciones y totales de la BD.

El diálogo **no escribe** nada por su cuenta: emite ``apply_language``,
``apply_settings``, ``apply_appearance`` y ``apply_shortcuts`` y la ventana
persiste en QSettings y reaplica al vuelo.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QKeySequenceEdit,
    QLabel,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.settings import (
    MAX_TIMEOUT_MS,
    MIN_TIMEOUT_MS,
    SHORTCUT_DEFAULTS,
    Settings,
)
from app.i18n import LANGUAGES, tr
from app.themes import DEFAULT_THEME_ID, load_themes

#: Etiquetas (en español) de cada atajo personalizable, por ID.
SHORTCUT_LABELS: dict[str, str] = {
    "prev": "Pista anterior",
    "play_pause": "Reproducir/Pausar",
    "next": "Pista siguiente",
    "lyrics": "Ver letra",
    "view_canciones": "Ver: Canciones",
    "view_biblioteca": "Ver: Biblioteca",
    "view_favoritos": "Ver: Favoritos",
    "open_files": "Abrir archivo(s)",
    "open_folder": "Abrir carpeta",
    "load_playlist": "Cargar playlist",
    "save_playlist": "Guardar playlist",
    "settings": "Ajustes",
    "quit": "Salir",
}

#: Filas de la rejilla de atajos (2 columnas de pares etiqueta+tecla).
SHORTCUT_ROWS = 6

#: Tamaño mínimo del diálogo: cuadrado y holgado, no una franja aplastada.
DIALOG_MIN_SIZE = (620, 560)


class SettingsDialog(QDialog):
    """Ajustes modales en pestañas.

    Señales: apply_language, apply_settings, apply_appearance,
    apply_shortcuts, test_notification.
    """

    apply_language = Signal(str)
    apply_settings = Signal(bool, int)
    apply_appearance = Signal(str, bool, bool)  # tema, espectro, carátula
    apply_shortcuts = Signal(dict)
    test_notification = Signal()

    def __init__(
        self,
        settings: Settings,
        notifier_backend: str,
        version: str,
        library_stats: dict[str, int] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Ajustes de PyAmp"))
        self.setModal(True)
        self.setMinimumSize(*DIALOG_MIN_SIZE)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # --- pestaña General (idioma; se aplica al reiniciar la app) ---
        general_page = QWidget()
        general_form = QFormLayout(general_page)
        self._combo_language = QComboBox()
        for code, name in LANGUAGES.items():
            self._combo_language.addItem(name, code)
        language_index = self._combo_language.findData(settings.language)
        self._combo_language.setCurrentIndex(language_index if language_index >= 0 else 0)
        self._combo_language.setToolTip(
            tr("Idioma de la aplicación. Al aceptar, PyAmp se reinicia en el idioma elegido.")
        )
        general_form.addRow(tr("Idioma:"), self._combo_language)
        tabs.addTab(general_page, tr("General"))

        # --- pestaña Notificaciones ---
        notif_page = QWidget()
        notif_form = QFormLayout(notif_page)
        self._check_enabled = QCheckBox(tr("Activar notificaciones de escritorio"))
        self._check_enabled.setChecked(settings.notifications_enabled)
        notif_form.addRow(self._check_enabled)

        self._spin_timeout = QSpinBox()
        self._spin_timeout.setRange(MIN_TIMEOUT_MS // 1000, MAX_TIMEOUT_MS // 1000)
        self._spin_timeout.setSuffix(" s")
        self._spin_timeout.setValue(max(1, settings.notifications_timeout_ms // 1000))
        self._spin_timeout.setToolTip(tr("Duración en pantalla de cada notificación"))
        notif_form.addRow(tr("Duración:"), self._spin_timeout)

        self._button_test = QPushButton(tr("Probar notificación"))
        self._button_test.setToolTip(tr("Envía una notificación de prueba ahora"))
        self._button_test.clicked.connect(self.test_notification.emit)
        notif_form.addRow(self._button_test)
        tabs.addTab(notif_page, tr("Notificaciones"))

        # --- pestaña Apariencia (tema, espectrograma, carátula) ---
        appearance_page = QWidget()
        appearance_form = QFormLayout(appearance_page)

        self._combo_theme = QComboBox()
        themes = load_themes()
        for theme in themes.values():
            self._combo_theme.addItem(theme.name, theme.id)
        wanted = settings.theme_id or DEFAULT_THEME_ID
        index = self._combo_theme.findData(wanted)
        self._combo_theme.setCurrentIndex(index if index >= 0 else 0)
        self._combo_theme.setToolTip(tr("Tema visual de toda la aplicación"))
        appearance_form.addRow(tr("Tema:"), self._combo_theme)

        self._check_spectrum = QCheckBox(tr("Mostrar espectrograma en la cabecera"))
        self._check_spectrum.setChecked(settings.show_spectrum)
        appearance_form.addRow(self._check_spectrum)

        self._check_cover = QCheckBox(tr("Mostrar imagen en la cabecera"))
        self._check_cover.setChecked(settings.show_cover)
        appearance_form.addRow(self._check_cover)
        tabs.addTab(appearance_page, tr("Apariencia"))

        # --- pestaña Atajos de teclado (ver SHORTCUT_DEFAULTS) ---
        shortcuts_page = QWidget()
        shortcuts_layout = QVBoxLayout(shortcuts_page)
        hint = QLabel(tr("Pulsa la combinación nueva en cada recuadro. Vacío = valor por defecto."))
        hint.setWordWrap(True)
        shortcuts_layout.addWidget(hint)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)
        custom = settings.shortcuts
        self._shortcut_edits: dict[str, QKeySequenceEdit] = {}
        for index, (shortcut_id, default) in enumerate(SHORTCUT_DEFAULTS.items()):
            row = index % SHORTCUT_ROWS
            column = (index // SHORTCUT_ROWS) * 2
            label_text = tr(SHORTCUT_LABELS[shortcut_id])
            label = QLabel(f"{label_text} ({default}):")
            edit = QKeySequenceEdit(QKeySequence(custom.get(shortcut_id, default)))
            edit.setAccessibleName(label_text)
            self._shortcut_edits[shortcut_id] = edit
            grid.addWidget(label, row, column)
            grid.addWidget(edit, row, column + 1)
        shortcuts_layout.addLayout(grid)
        tabs.addTab(shortcuts_page, tr("Atajos"))

        # --- pestaña Información ---
        info_page = QWidget()
        info_form = QFormLayout(info_page)
        info_form.addRow(tr("Versión:"), QLabel(version))
        info_form.addRow(tr("Notificador:"), QLabel(notifier_backend))
        if library_stats is not None:
            info_form.addRow(
                tr("Biblioteca:"),
                QLabel(
                    tr("{tracks} pistas · {artists} artistas · {albums} álbumes").format(
                        tracks=library_stats.get("tracks", 0),
                        artists=library_stats.get("artists", 0),
                        albums=library_stats.get("albums", 0),
                    )
                ),
            )
        tabs.addTab(info_page, tr("Información"))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accepted)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accepted(self) -> None:
        self.apply_language.emit(str(self._combo_language.currentData() or "es"))
        self.apply_settings.emit(self._check_enabled.isChecked(), self._spin_timeout.value() * 1000)
        self.apply_appearance.emit(
            str(self._combo_theme.currentData() or DEFAULT_THEME_ID),
            self._check_spectrum.isChecked(),
            self._check_cover.isChecked(),
        )
        self.apply_shortcuts.emit(self._collect_shortcuts())
        self.accept()

    def _collect_shortcuts(self) -> dict[str, str]:
        """Secuencias que difieren de su default (portable; vacío = default).

        Solo se emiten las personalizaciones reales: un atajo igual al
        default (o borrado) no se guarda, así los defaults futuros siguen
        aplicando a los usuarios que no lo tocaron.
        """
        mapping: dict[str, str] = {}
        for shortcut_id, edit in self._shortcut_edits.items():
            sequence = edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
            if sequence and sequence != SHORTCUT_DEFAULTS[shortcut_id]:
                mapping[shortcut_id] = sequence
        return mapping
