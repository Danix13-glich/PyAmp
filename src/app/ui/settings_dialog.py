from __future__ import annotations

import platform
import sys

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import Qt, Signal, qVersion
from PySide6.QtGui import QColor, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.settings import (
    MAX_TIMEOUT_MS,
    MAX_WINDOW_HEIGHT,
    MAX_WINDOW_WIDTH,
    MIN_TIMEOUT_MS,
    MIN_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    SHORTCUT_DEFAULTS,
    Settings,
)
from app.i18n import LANGUAGES, tr
from app.themes import (
    DEFAULT_THEME_ID,
    create_custom_theme,
    delete_custom_theme,
    is_custom_theme,
    load_themes,
    rename_custom_theme,
)
from app.ui.install_dialog import InstallDialog
from app.utils.installer import is_frozen, is_installed_application, remove_installer

#: Valor centinela del combo de temas para «crear uno nuevo».
CREATE_THEME_SENTINEL = "__create_theme__"

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


def _distribution_kind() -> str:
    if not is_frozen():
        return tr("Código fuente (Python)")
    if sys.platform.startswith("win"):
        return tr("Ejecutable de Windows (.exe)")
    if sys.platform == "darwin":
        return tr("Aplicación de macOS (.app)")
    return tr("AppImage de Linux")


class SettingsDialog(QDialog):

    apply_language = Signal(str)
    apply_settings = Signal(bool, int)
    apply_appearance = Signal(str, bool, bool)  # tema, espectro, carátula
    apply_window_size = Signal(int, int)
    apply_show_hidden = Signal(bool)
    apply_shortcuts = Signal(dict)
    test_notification = Signal()
    factory_reset = Signal()

    def __init__(
        self,
        settings: Settings,
        notifier_backend: str,
        version: str,
        library_stats: dict[str, int] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
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
        tabs.addTab(self._build_advanced(), tr("Avanzado"))

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
        info_form.addRow(tr("Autor:"), QLabel("Danix13-glich"))
        info_form.addRow(
            tr("Sistema:"),
            QLabel(f"{platform.system()} {platform.release()} ({platform.machine()})"),
        )
        info_form.addRow(tr("Python:"), QLabel(platform.python_version()))
        info_form.addRow(tr("Qt:"), QLabel(f"PySide6 {pyside_version} (Qt {qVersion()})"))
        info_form.addRow(tr("Formato:"), QLabel(_distribution_kind()))
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

        install_box = QWidget()
        install_layout = QVBoxLayout(install_box)
        install_layout.setContentsMargins(0, 6, 0, 0)
        install_layout.setSpacing(4)
        self._button_install = QPushButton(tr("Instalar"))
        self._button_install.setToolTip(tr("Instala PyAmp en este equipo"))
        self._button_install.clicked.connect(self._on_install)
        install_layout.addWidget(self._button_install)
        if is_installed_application():
            # Ya se ejecuta desde la copia instalada: no hay nada que instalar.
            self._button_install.hide()
            install_box.hide()
        info_form.addRow(install_box)
        outer.addWidget(info_group)
        outer.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        return scroll

    def _build_appearance(self, settings: Settings) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        themes = load_themes()
        self._themes = themes

        # Selector, nombre y borrado en la misma línea, a la derecha del tema.
        self._combo_theme = QComboBox()
        for theme in themes.values():
            self._combo_theme.addItem(theme.name, theme.id)
        self._combo_theme.addItem(tr("Crear tema nuevo…"), CREATE_THEME_SENTINEL)
        wanted = settings.theme_id or DEFAULT_THEME_ID
        index = self._combo_theme.findData(wanted)
        self._combo_theme.setCurrentIndex(index if index >= 0 else 0)
        self._combo_theme.setToolTip(tr("Tema visual de toda la aplicación"))
        self._combo_theme.currentIndexChanged.connect(self._on_theme_changed)

        self._edit_current_name = QLineEdit()
        self._edit_current_name.setMaximumWidth(180)
        self._edit_current_name.setPlaceholderText(tr("Nombre del tema actual"))
        self._edit_current_name.setToolTip(tr("Solo se pueden renombrar los temas personalizados"))
        self._btn_delete_theme = QPushButton(tr("Eliminar"))
        self._btn_delete_theme.setToolTip(tr("Eliminar tema"))
        self._btn_delete_theme.clicked.connect(self._on_delete_theme)

        theme_row = QWidget()
        theme_layout = QHBoxLayout(theme_row)
        theme_layout.setContentsMargins(0, 0, 0, 0)
        theme_layout.addWidget(self._combo_theme, stretch=1)
        theme_layout.addWidget(self._edit_current_name)
        theme_layout.addWidget(self._btn_delete_theme)
        form.addRow(tr("Tema:"), theme_row)

        self._color_values: dict[str, str] = {
            "bg": "#17171b",
            "text": "#e8e8ee",
            "accent": "#3d7bd9",
        }
        self._create_group = QGroupBox(tr("Crear tema nuevo"))
        create_form = QFormLayout(self._create_group)
        self._edit_theme_name = QLineEdit()
        self._edit_theme_name.setPlaceholderText(tr("Mi tema"))
        self._edit_theme_name.setToolTip(tr("Nombre para el nuevo tema"))
        create_form.addRow(tr("Nombre del tema:"), self._edit_theme_name)
        self._btn_color_bg = self._make_color_button("bg", "Fondo")
        self._btn_color_text = self._make_color_button("text", "Texto")
        self._btn_color_accent = self._make_color_button("accent", "Color de acento")
        create_form.addRow(tr("Fondo:"), self._btn_color_bg)
        create_form.addRow(tr("Texto:"), self._btn_color_text)
        create_form.addRow(tr("Acento:"), self._btn_color_accent)
        self._create_group.setVisible(False)
        form.addRow(self._create_group)

        size_row = QHBoxLayout()
        self._spin_width = QSpinBox()
        self._spin_width.setRange(MIN_WINDOW_WIDTH, MAX_WINDOW_WIDTH)
        self._spin_width.setSuffix(" px")
        self._spin_width.setValue(settings.window_width)
        self._spin_height = QSpinBox()
        self._spin_height.setRange(MIN_WINDOW_HEIGHT, MAX_WINDOW_HEIGHT)
        self._spin_height.setSuffix(" px")
        self._spin_height.setValue(settings.window_height)
        size_row.addWidget(QLabel(tr("Ancho")))
        size_row.addWidget(self._spin_width)
        size_row.addWidget(QLabel(tr("Alto")))
        size_row.addWidget(self._spin_height)
        size_row.addStretch(1)
        size_widget = QWidget()
        size_widget.setLayout(size_row)
        self._spin_width.setToolTip(tr("Tamaño por defecto de la ventana principal"))
        form.addRow(tr("Tamaño de la ventana:"), size_widget)

        self._check_spectrum = QCheckBox(tr("Mostrar espectrograma en la cabecera"))
        self._check_spectrum.setChecked(settings.show_spectrum)
        form.addRow(self._check_spectrum)

        self._check_cover = QCheckBox(tr("Mostrar imagen en la cabecera"))
        self._check_cover.setChecked(settings.show_cover)
        form.addRow(self._check_cover)

        self._check_hidden = QCheckBox(tr("Mostrar archivos ocultos"))
        self._check_hidden.setChecked(settings.show_hidden)
        self._check_hidden.setToolTip(
            tr("Los archivos ocultos aparecen al principio, con un «-» delante.")
        )
        form.addRow(self._check_hidden)
        self._on_theme_changed()
        return page

    def _make_color_button(self, role: str, label: str) -> QPushButton:
        button = QPushButton()
        button.setMinimumWidth(120)
        button.setToolTip(label)
        button.clicked.connect(lambda: self._pick_color(role))
        self._apply_color_style(button, self._color_values[role])
        return button

    def _apply_color_style(self, button: QPushButton, color: str) -> None:
        text = "#000000" if QColor(color).lightness() > 140 else "#ffffff"
        button.setText(color.upper())
        button.setStyleSheet(
            f"QPushButton {{ background-color: {color}; color: {text};"
            " border: 1px solid #808080; border-radius: 4px; padding: 4px 12px; }"
        )

    def _pick_color(self, role: str) -> None:
        current = QColor(self._color_values[role])
        chosen = QColorDialog.getColor(current, self, tr("Elegir color"))
        if not chosen.isValid():
            return
        self._color_values[role] = chosen.name()
        button = {
            "bg": self._btn_color_bg,
            "text": self._btn_color_text,
            "accent": self._btn_color_accent,
        }[role]
        self._apply_color_style(button, chosen.name())

    def _on_theme_changed(self) -> None:
        selected = str(self._combo_theme.currentData() or "")
        creating = selected == CREATE_THEME_SENTINEL
        custom = not creating and is_custom_theme(selected)
        self._create_group.setVisible(creating)
        self._edit_current_name.setEnabled(custom)
        self._btn_delete_theme.setEnabled(custom)
        theme = self._themes.get(selected) if custom else None
        self._edit_current_name.setText(theme.name if theme is not None else "")

    def _on_delete_theme(self) -> None:
        theme_id = str(self._combo_theme.currentData() or "")
        theme = self._themes.get(theme_id)
        if theme is None or not is_custom_theme(theme_id):
            return
        answer = QMessageBox.question(
            self,
            tr("Eliminar tema"),
            tr("¿Eliminar el tema «{name}»?").format(name=theme.name),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if not delete_custom_theme(theme_id):
            return
        index = self._combo_theme.findData(theme_id)
        if index >= 0:
            self._combo_theme.removeItem(index)
        self._themes = load_themes()
        default_index = self._combo_theme.findData(DEFAULT_THEME_ID)
        self._combo_theme.setCurrentIndex(default_index if default_index >= 0 else 0)
        self._on_theme_changed()

    def _build_advanced(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        reset_group = QGroupBox(tr("Restaurar valores de fábrica"))
        reset_layout = QVBoxLayout(reset_group)
        hint = QLabel(
            tr(
                "Restaura todos los ajustes de PyAmp a sus valores originales.\n"
                "La biblioteca y tus archivos de música no se tocan."
            )
        )
        hint.setWordWrap(True)
        reset_layout.addWidget(hint)
        self._button_factory_reset = QPushButton(tr("Restaurar valores de fábrica"))
        self._button_factory_reset.clicked.connect(self._on_factory_reset)
        reset_layout.addWidget(self._button_factory_reset, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(reset_group)
        layout.addStretch(1)
        return page

    def _on_factory_reset(self) -> None:
        answer = QMessageBox.warning(
            self,
            tr("Restaurar valores de fábrica"),
            tr(
                "¿Restaurar todos los ajustes a sus valores de fábrica?\n"
                "Se perderán tus preferencias, el tema activo, las emisoras y los "
                "atajos personalizados. La biblioteca y tus archivos de música no se tocan."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._settings.reset()
        self.accept()
        self.factory_reset.emit()

    # ------------------------------------------------------------ instalación
    def _on_install(self) -> None:
        self._button_install.setEnabled(False)
        dialog = InstallDialog(self)
        dialog.start()
        dialog.exec()
        self._button_install.setEnabled(True)

        if dialog.error:
            QMessageBox.warning(
                self,
                tr("Instalación de PyAmp"),
                tr("No se pudo instalar: {error}").format(error=dialog.error),
            )
            return
        installed = dialog.install_result
        if installed is None:
            return
        if not (installed.installer_removable and installed.installer_path):
            QMessageBox.information(self, tr("Instalación completada"), installed.message)
            return
        answer = QMessageBox.question(
            self,
            tr("Instalación completada"),
            tr("¿Quieres eliminar el archivo instalador?\n{path}").format(
                path=installed.installer_path
            ),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if not remove_installer(installed.installer_path):
            QMessageBox.warning(
                self,
                tr("Instalación de PyAmp"),
                tr("No se pudo eliminar el archivo instalador."),
            )

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
        selected = str(self._combo_theme.currentData() or DEFAULT_THEME_ID)
        if selected != CREATE_THEME_SENTINEL and is_custom_theme(selected):
            new_name = self._edit_current_name.text().strip()
            if new_name:
                rename_custom_theme(selected, new_name)
        self.apply_appearance.emit(
            self._resolve_theme_id(),
            self._check_spectrum.isChecked(),
            self._check_cover.isChecked(),
        )
        self.apply_window_size.emit(self._spin_width.value(), self._spin_height.value())
        self.apply_show_hidden.emit(self._check_hidden.isChecked())
        self.apply_shortcuts.emit(self._collect_shortcuts())
        self.accept()

    def _resolve_theme_id(self) -> str:
        selected = str(self._combo_theme.currentData() or DEFAULT_THEME_ID)
        if selected != CREATE_THEME_SENTINEL:
            return selected
        try:
            theme = create_custom_theme(
                self._color_values["bg"],
                self._color_values["text"],
                self._color_values["accent"],
                name=self._edit_theme_name.text(),
            )
        except Exception:  # noqa: BLE001 - un tema no debe impedir guardar
            return DEFAULT_THEME_ID
        return theme.id

    def _collect_shortcuts(self) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for shortcut_id, edit in self._shortcut_edits.items():
            sequence = edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
            if sequence and sequence != SHORTCUT_DEFAULTS[shortcut_id]:
                mapping[shortcut_id] = sequence
        return mapping
