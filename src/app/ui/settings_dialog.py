"""Diálogo de Ajustes de PyAmp (Fase 4).

Solo opciones con respaldo real en QSettings de la Fase 1:

* Notificaciones: activar/desactivar y duración (1–60 s).
* Botón «Probar notificación» para verificar el camino D-Bus delante del
  usuario (el envío lo hace la ventana, que es quien posee el Notifier).
* Información: versión, backend de notificaciones y totales de la BD.

El diálogo **no escribe** nada por su cuenta: emite ``apply_settings`` y
la ventana persiste en QSettings y actualiza el Notifier al vuelo.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.settings import MAX_TIMEOUT_MS, MIN_TIMEOUT_MS, Settings


class SettingsDialog(QDialog):
    """Ajustes modales. Señales: apply_settings(enabled, timeout_ms), test_notification()."""

    apply_settings = Signal(bool, int)
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
        self.accept()
