"""Diálogo de Ajustes de PyAmp (Fase 4).

Solo opciones con respaldo real en QSettings de la Fase 1:

* Notificaciones: activar/desactivar y duración (1–60 s).
* Atajos de teclado: reasignar las combinaciones del catálogo
  ``SHORTCUT_DEFAULTS`` (las teclas multimedia del hardware quedan fijas).
* Botón «Probar notificación» para verificar el camino D-Bus delante del
  usuario (el envío lo hace la ventana, que es quien posee el Notifier).
* Información: versión, backend de notificaciones y totales de la BD.

El diálogo **no escribe** nada por su cuenta: emite ``apply_settings`` y
``apply_shortcuts`` y la ventana persiste en QSettings y reaplica al vuelo.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QKeySequenceEdit,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.settings import (
    MAX_TIMEOUT_MS,
    MIN_TIMEOUT_MS,
    SHORTCUT_DEFAULTS,
    Settings,
)

#: Etiquetas (en español) de cada atajo personalizable, por ID.
SHORTCUT_LABELS: dict[str, str] = {
    "prev": "Pista anterior",
    "play_pause": "Reproducir/Pausar",
    "next": "Pista siguiente",
    "lyrics": "Ver letra",
    "view_canciones": "Ver: Canciones",
    "view_biblioteca": "Ver: Biblioteca",
    "open_files": "Abrir archivo(s)",
    "open_folder": "Abrir carpeta",
    "load_playlist": "Cargar playlist",
    "save_playlist": "Guardar playlist",
    "settings": "Ajustes",
    "quit": "Salir",
}

#: Filas de la rejilla de atajos (2 columnas de pares etiqueta+tecla).
SHORTCUT_ROWS = 6


class SettingsDialog(QDialog):
    """Ajustes modales. Señales: apply_settings, apply_shortcuts, test_notification."""

    apply_settings = Signal(bool, int)
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
        self.setWindowTitle("Ajustes de PyAmp")
        self.setModal(True)

        layout = QVBoxLayout(self)

        # --- notificaciones ---
        notif_group = QGroupBox("Notificaciones")
        notif_form = QFormLayout(notif_group)
        self._check_enabled = QCheckBox("Activar notificaciones de escritorio")
        self._check_enabled.setChecked(settings.notifications_enabled)
        notif_form.addRow(self._check_enabled)

        self._spin_timeout = QSpinBox()
        self._spin_timeout.setRange(MIN_TIMEOUT_MS // 1000, MAX_TIMEOUT_MS // 1000)
        self._spin_timeout.setSuffix(" s")
        self._spin_timeout.setValue(max(1, settings.notifications_timeout_ms // 1000))
        self._spin_timeout.setToolTip("Duración en pantalla de cada notificación")
        notif_form.addRow("Duración:", self._spin_timeout)

        self._button_test = QPushButton("Probar notificación")
        self._button_test.setToolTip("Envía una notificación de prueba ahora")
        self._button_test.clicked.connect(self.test_notification.emit)
        notif_form.addRow(self._button_test)
        layout.addWidget(notif_group)

        # --- atajos de teclado (personalizables; ver SHORTCUT_DEFAULTS) ---
        shortcuts_group = QGroupBox("Atajos de teclado")
        shortcuts_layout = QVBoxLayout(shortcuts_group)
        hint = QLabel("Pulsa la combinación nueva en cada recuadro. Vacío = valor por defecto.")
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
            label = QLabel(f"{SHORTCUT_LABELS[shortcut_id]} ({default}):")
            edit = QKeySequenceEdit(QKeySequence(custom.get(shortcut_id, default)))
            edit.setAccessibleName(SHORTCUT_LABELS[shortcut_id])
            self._shortcut_edits[shortcut_id] = edit
            grid.addWidget(label, row, column)
            grid.addWidget(edit, row, column + 1)
        shortcuts_layout.addLayout(grid)
        layout.addWidget(shortcuts_group)

        # --- información ---
        info_group = QGroupBox("Información")
        info_form = QFormLayout(info_group)
        info_form.addRow("Versión:", QLabel(version))
        info_form.addRow("Notificador:", QLabel(notifier_backend))
        if library_stats is not None:
            info_form.addRow(
                "Biblioteca:",
                QLabel(
                    f"{library_stats.get('tracks', 0)} pistas · "
                    f"{library_stats.get('artists', 0)} artistas · "
                    f"{library_stats.get('albums', 0)} álbumes"
                ),
            )
        layout.addWidget(info_group)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accepted)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accepted(self) -> None:
        self.apply_settings.emit(self._check_enabled.isChecked(), self._spin_timeout.value() * 1000)
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
