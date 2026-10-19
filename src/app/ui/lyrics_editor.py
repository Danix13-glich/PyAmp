from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.library.models import Track
from app.ui.lyrics_window import find_lrc_path
from app.utils.paths import LYRICS_DIR

logger = logging.getLogger(__name__)

EDITOR_MIN_SIZE = (480, 360)
HINT_TEXT = (
    "Formato: una línea por frase. Para sincronizar añade marcas de tiempo "
    "«[mm:ss]» al principio de cada línea."
)


def lyrics_target_path(track: Track) -> Path:
    if track.path:
        existing = find_lrc_path(track.path)
        if existing is not None:
            return existing
        return LYRICS_DIR / f"{Path(track.path).stem}.lrc"
    return LYRICS_DIR / "sin-titulo.lrc"


class LyricsEditorDialog(QDialog):

    lyrics_saved = Signal(str)

    def __init__(self, track: Track, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Editar letra — {title}").format(title=track.display_title))
        self.setModal(True)
        self.setMinimumSize(*EDITOR_MIN_SIZE)

        self._target = lyrics_target_path(track)

        layout = QVBoxLayout(self)

        self._label_track = QLabel(track.display_name)
        title_font = self._label_track.font()
        title_font.setBold(True)
        self._label_track.setFont(title_font)
        self._label_track.setWordWrap(True)
        layout.addWidget(self._label_track)

        path_kind = tr("Existente") if self._target.is_file() else tr("Nuevo")
        self._label_path = QLabel(f"{path_kind}: {self._target}")
        self._label_path.setWordWrap(True)
        self._label_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._label_path)

        hint = QLabel(tr(HINT_TEXT))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #9e9ea6;")
        layout.addWidget(hint)

        self._editor = QPlainTextEdit()
        monospace = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self._editor.setFont(monospace)
        self._editor.setPlaceholderText(tr("Escribe aquí la letra de la canción..."))
        layout.addWidget(self._editor, stretch=1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(tr("Guardar"))
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._load_existing()

    def _load_existing(self) -> None:
        if not self._target.is_file():
            return
        try:
            self._editor.setPlainText(self._target.read_text(encoding="utf-8", errors="replace"))
        except OSError as exc:
            logger.warning("No se pudo leer la letra %s: %s", self._target, exc)
            self._editor.setPlaceholderText(
                tr("No se pudo leer {name}: {error}").format(name=self._target.name, error=exc)
            )

    def _on_save(self) -> None:
        try:
            self._target.parent.mkdir(parents=True, exist_ok=True)
            self._target.write_text(self._editor.toPlainText(), encoding="utf-8")
        except OSError as exc:
            logger.warning("No se pudo guardar la letra %s: %s", self._target, exc)
            QMessageBox.warning(
                self,
                tr("No se pudo guardar"),
                tr("No se pudo escribir {path}:\n{error}").format(path=self._target, error=exc),
            )
            return
        self.lyrics_saved.emit(str(self._target))
        self.accept()

    @property
    def target_path(self) -> Path:
        return self._target
