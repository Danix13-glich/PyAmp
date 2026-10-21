from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialog, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from app.i18n import tr
from app.utils.installer import InstallResult, InstallWorker

#: La barra se detiene aquí un momento antes de terminar.
HOLD_VALUE = 90
HOLD_MS = 1000


class InstallDialog(QDialog):

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Instalando PyAmp"))
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(10)
        self._label = QLabel(tr("Instalando PyAmp…"))
        self._label.setWordWrap(True)
        layout.addWidget(self._label)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        layout.addWidget(self._bar)

        self._button_close = QPushButton(tr("Cerrar"))
        self._button_close.clicked.connect(self.reject)
        self._button_close.setVisible(False)
        layout.addWidget(self._button_close, alignment=Qt.AlignmentFlag.AlignCenter)

        self.install_result: InstallResult | None = None
        self.error = ""
        self._pending: InstallResult | None = None
        self._held = False
        self._released = False
        self._failed = False
        self._worker: InstallWorker | None = None

    def start(self) -> None:
        worker = InstallWorker(self)
        self._worker = worker
        worker.progress.connect(self._on_progress)
        worker.finished_ok.connect(self._on_ok)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_finished)
        QTimer.singleShot(0, worker.start)

    def _on_progress(self, value: int, text: str) -> None:
        if self._failed:
            return
        if text:
            self._label.setText(text)
        if self._held:
            return
        if value >= HOLD_VALUE:
            # Se muestra el 90 % y se espera un segundo antes de completar.
            self._bar.setValue(HOLD_VALUE)
            self._held = True
            QTimer.singleShot(HOLD_MS, self._release)
            return
        self._bar.setValue(max(0, min(value, HOLD_VALUE - 1)))

    def _release(self) -> None:
        self._released = True
        if self._pending is not None:
            self._finish(self._pending)

    def _on_ok(self, result: object) -> None:
        if not isinstance(result, InstallResult):
            return
        self._pending = result
        if self._released:
            self._finish(result)

    def _finish(self, result: InstallResult) -> None:
        self.install_result = result
        self._bar.setValue(100)
        self._label.setText(result.message)
        QTimer.singleShot(150, self.accept)

    def _on_failed(self, message: str) -> None:
        self._failed = True
        self.error = message
        self._label.setText(tr("No se pudo instalar: {error}").format(error=message))
        self._bar.setVisible(False)
        self._button_close.setVisible(True)

    def _on_finished(self) -> None:
        self._worker = None

    def done(self, result: int) -> None:
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.wait()
        super().done(result)
