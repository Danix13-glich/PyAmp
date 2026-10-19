from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.library.models import RadioStation
from app.radio import RadioLibrary

#: Rol donde se guarda la emisora completa de cada fila.
ROLE_STATION = Qt.ItemDataRole.UserRole


class RadioStationDialog(QDialog):

    def __init__(self, station: RadioStation | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Emisora de radio"))
        self.setModal(True)

        form = QFormLayout(self)
        self._edit_name = QLineEdit(station.name if station else "")
        self._edit_url = QLineEdit(station.url if station else "")
        self._edit_genre = QLineEdit(station.genre if station else "")
        self._edit_country = QLineEdit(station.country if station else "")
        form.addRow(tr("Nombre:"), self._edit_name)
        form.addRow(tr("Dirección (URL):"), self._edit_url)
        form.addRow(tr("Género:"), self._edit_genre)
        form.addRow(tr("País:"), self._edit_country)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def station(self) -> RadioStation:
        return RadioStation(
            name=self._edit_name.text().strip(),
            url=self._edit_url.text().strip(),
            genre=self._edit_genre.text().strip(),
            country=self._edit_country.text().strip(),
        )


class RadioPanel(QWidget):

    play_requested = Signal(object)  # RadioStation
    stop_requested = Signal()
    station_selected = Signal(object)  # RadioStation

    def __init__(self, radio: RadioLibrary, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._radio = radio

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        top = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText(tr("Buscar emisora, género o país..."))
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(lambda _text: self.refresh())
        top.addWidget(self._search, stretch=1)
        layout.addLayout(top)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels([tr("Emisora"), tr("Género"), tr("País")])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.doubleClicked.connect(lambda *_: self._play_selected())
        self._table.itemSelectionChanged.connect(self._emit_selected)
        layout.addWidget(self._table, stretch=1)

        buttons = QHBoxLayout()
        self._button_play = QPushButton(tr("Reproducir"))
        self._button_play.clicked.connect(self._play_selected)
        self._button_stop = QPushButton(tr("Detener"))
        self._button_stop.clicked.connect(self.stop_requested.emit)
        self._button_add = QPushButton(tr("Añadir"))
        self._button_add.clicked.connect(self._on_add)
        self._button_edit = QPushButton(tr("Editar"))
        self._button_edit.clicked.connect(self._on_edit)
        self._button_remove = QPushButton(tr("Eliminar"))
        self._button_remove.clicked.connect(self._on_remove)
        for button in (
            self._button_play,
            self._button_stop,
            self._button_add,
            self._button_edit,
            self._button_remove,
        ):
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self._status = QLabel("")
        layout.addWidget(self._status)

        self.refresh()

    def refresh(self) -> None:
        stations = self._radio.search(self._search.text())
        self._table.blockSignals(True)
        self._table.setRowCount(0)
        for station in stations:
            row = self._table.rowCount()
            self._table.insertRow(row)
            name_item = QTableWidgetItem(station.name)
            name_item.setData(ROLE_STATION, station)
            self._table.setItem(row, 0, name_item)
            self._table.setItem(
                row, 1, QTableWidgetItem(tr(station.genre) if station.genre else "")
            )
            self._table.setItem(
                row, 2, QTableWidgetItem(tr(station.country) if station.country else "")
            )
        self._table.blockSignals(False)
        self._status.setText(
            tr("{shown} de {total} emisoras").format(
                shown=len(stations), total=len(self._radio.stations())
            )
        )

    def selected_station(self) -> RadioStation | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        if item is None:
            return None
        station = item.data(ROLE_STATION)
        return station if isinstance(station, RadioStation) else None

    def select_relative(self, delta: int) -> None:
        # Anterior/siguiente en la vista de radio: cambia de emisora y la pone.
        count = self._table.rowCount()
        if count == 0:
            self._status.setText(tr("No hay emisoras: busca o añade una"))
            return
        row = self._table.currentRow()
        row = (0 if delta > 0 else count - 1) if row < 0 else (row + delta) % count
        self._table.setCurrentCell(row, 0)
        self._play_selected()

    def show_message(self, text: str) -> None:
        self._status.setText(text)

    def _emit_selected(self) -> None:
        station = self.selected_station()
        if station is not None:
            self.station_selected.emit(station)

    def _play_selected(self) -> None:
        station = self.selected_station()
        if station is None:
            self._status.setText(tr("Selecciona una emisora"))
            return
        self.play_requested.emit(station)

    def _on_add(self) -> None:
        dialog = RadioStationDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        station = dialog.station()
        if not station.name or not station.url:
            return
        if not self._radio.add(station):
            QMessageBox.information(self, tr("Radio"), tr("Esa emisora ya está en la lista."))
            return
        self.refresh()

    def _on_edit(self) -> None:
        self._edit_station(self.selected_station())

    def _on_remove(self) -> None:
        station = self.selected_station()
        if station is None:
            self._status.setText(tr("Selecciona una emisora"))
            return
        self._confirm_remove(station)

    def _on_context_menu(self, position: QPoint) -> None:
        row = self._table.rowAt(position.y())
        if row < 0:
            return
        self._table.setCurrentCell(row, 0)
        station = self.selected_station()
        if station is None:
            return
        menu = QMenu(self)
        action_play = menu.addAction(tr("Reproducir"))
        action_play.triggered.connect(lambda: self.play_requested.emit(station))
        menu.addSeparator()
        action_edit = menu.addAction(tr("Editar Valores"))
        action_edit.triggered.connect(lambda: self._edit_station(station))
        action_remove = menu.addAction(tr("Eliminar"))
        action_remove.triggered.connect(lambda: self._confirm_remove(station))
        menu.exec(self._table.viewport().mapToGlobal(position))

    def _edit_station(self, station: RadioStation | None) -> None:
        if station is None:
            self._status.setText(tr("Selecciona una emisora"))
            return
        dialog = RadioStationDialog(station, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        edited = dialog.station()
        if not edited.name or not edited.url:
            return
        if not self._radio.update(station.url, edited):
            QMessageBox.information(self, tr("Radio"), tr("Esa emisora ya está en la lista."))
            return
        self.refresh()

    def _confirm_remove(self, station: RadioStation) -> None:
        confirm = QMessageBox.question(
            self,
            tr("Radio"),
            tr("¿Eliminar «{name}»?").format(name=station.name),
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._radio.remove(station.url)
        self.refresh()
