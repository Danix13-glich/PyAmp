from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QPushButton,
    QScrollArea,
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
    "view_favoritos": "Ver: Favoritos",
    "view_radio": "Ver: Radio",
    "open_files": "Abrir archivo(s)",
    "open_folder": "Abrir carpeta",
    "load_playlist": "Cargar playlist",
    "save_playlist": "Guardar playlist",
    "settings": "Ajustes",
    "quit": "Salir",
}

#: Tamaño mínimo del diálogo.
DIALOG_MIN_SIZE = (620, 560)


class SettingsDialog(QDialog):

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

        tabs.addTab(
            self._build_general(settings, notifier_backend, version, library_stats), tr("General")
        )
        tabs.addTab(self._build_appearance(settings), tr("Apariencia"))
        tabs.addTab(self._build_shortcuts(settings), tr("Atajos"))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accepted)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------- pestañas
    def _build_general(
        self,
        settings: Settings,
        notifier_backend: str,
        version: str,
        library_stats: dict[str, int] | None,
    ) -> QWidget:
        content = QWidget()
        outer = QVBoxLayout(content)
        outer.setSpacing(10)

        language_group = QGroupBox(tr("Idioma"))
        language_form = QFormLayout(language_group)
        self._combo_language = QComboBox()
        for code, name in LANGUAGES.items():
            self._combo_language.addItem(name, code)
        language_index = self._combo_language.findData(settings.language)
        self._combo_language.setCurrentIndex(language_index if language_index >= 0 else 0)
        self._combo_language.setToolTip(
            tr("Idioma de la aplicación. Al aceptar, PyAmp se reinicia en el idioma elegido.")
        )
        language_form.addRow(tr("Idioma:"), self._combo_language)
        outer.addWidget(language_group)

        notif_group = QGroupBox(tr("Notificaciones"))
        notif_form = QFormLayout(notif_group)
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
        outer.addWidget(notif_group)

        info_group = QGroupBox(tr("Información"))
        info_form = QFormLayout(info_group)
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
        outer.addWidget(info_group)
        outer.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        return scroll

    def _build_appearance(self, settings: Settings) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        self._combo_theme = QComboBox()
        themes = load_themes()
        for theme in themes.values():
            self._combo_theme.addItem(theme.name, theme.id)
        wanted = settings.theme_id or DEFAULT_THEME_ID
        index = self._combo_theme.findData(wanted)
        self._combo_theme.setCurrentIndex(index if index >= 0 else 0)
        self._combo_theme.setToolTip(tr("Tema visual de toda la aplicación"))
        form.addRow(tr("Tema:"), self._combo_theme)

        self._check_spectrum = QCheckBox(tr("Mostrar espectrograma en la cabecera"))
        self._check_spectrum.setChecked(settings.show_spectrum)
        form.addRow(self._check_spectrum)

        self._check_cover = QCheckBox(tr("Mostrar imagen en la cabecera"))
        self._check_cover.setChecked(settings.show_cover)
        form.addRow(self._check_cover)
        return page

    def _build_shortcuts(self, settings: Settings) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        hint = QLabel(tr("Pulsa la combinación nueva en cada recuadro. Vacío = valor por defecto."))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        custom = settings.shortcuts
        self._shortcut_edits: dict[str, QKeySequenceEdit] = {}
        items = list(SHORTCUT_DEFAULTS.items())
        half = (len(items) + 1) // 2
        columns = QHBoxLayout()
        columns.setSpacing(24)
        for chunk in (items[:half], items[half:]):
            form = QFormLayout()
            form.setVerticalSpacing(6)
            form.setHorizontalSpacing(12)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            for shortcut_id, default in chunk:
                label_text = tr(SHORTCUT_LABELS[shortcut_id])
                label = QLabel(f"{label_text} ({default}):")
                edit = QKeySequenceEdit(QKeySequence(custom.get(shortcut_id, default)))
                edit.setAccessibleName(label_text)
                self._shortcut_edits[shortcut_id] = edit
                form.addRow(label, edit)
            columns.addLayout(form)
        columns.addStretch(1)
        layout.addLayout(columns)
        layout.addStretch(1)
        return page

    # --------------------------------------------------------------- señales
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
        mapping: dict[str, str] = {}
        for shortcut_id, edit in self._shortcut_edits.items():
            sequence = edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
            if sequence and sequence != SHORTCUT_DEFAULTS[shortcut_id]:
                mapping[shortcut_id] = sequence
        return mapping
