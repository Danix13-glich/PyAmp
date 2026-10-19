from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from app.i18n import tr
from app.library.models import Track


class MetadataEditorDialog(QDialog):

    def __init__(self, track: Track, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Editar metadata"))
        self.setModal(True)

        form = QFormLayout(self)
        self._title = QLineEdit(track.title or "")
        self._artist = QLineEdit(track.artist or "")
        self._album = QLineEdit(track.album or "")
        self._albumartist = QLineEdit(track.albumartist or "")
        self._genre = QLineEdit(track.genre or "")
        self._year = QLineEdit(track.year or "")
        self._track_no = QSpinBox()
        self._track_no.setRange(0, 9999)
        self._track_no.setSpecialValueText("—")
        self._track_no.setValue(int(track.track_no or 0))
        self._disc_no = QSpinBox()
        self._disc_no.setRange(0, 9999)
        self._disc_no.setSpecialValueText("—")
        self._disc_no.setValue(int(track.disc_no or 0))

        form.addRow(tr("Título:"), self._title)
        form.addRow(tr("Artista:"), self._artist)
        form.addRow(tr("Álbum:"), self._album)
        form.addRow(tr("Artista del álbum:"), self._albumartist)
        form.addRow(tr("Género:"), self._genre)
        form.addRow(tr("Año:"), self._year)
        form.addRow(tr("N.º de pista:"), self._track_no)
        form.addRow(tr("N.º de disco:"), self._disc_no)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> dict[str, object]:
        return {
            "title": self._title.text().strip(),
            "artist": self._artist.text().strip(),
            "album": self._album.text().strip(),
            "albumartist": self._albumartist.text().strip(),
            "genre": self._genre.text().strip(),
            "year": self._year.text().strip(),
            "track_no": self._track_no.value() or None,
            "disc_no": self._disc_no.value() or None,
        }
