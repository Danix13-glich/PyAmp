from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from app.core.player import STATE_PLAYING, Player
from app.core.settings import Settings
from app.library.models import RadioStation
from app.radio import RadioLibrary
from app.ui.radio_panel import RadioPanel


def _settings(tmp_path: Path) -> Settings:
    return Settings(tmp_path / "radio-test.conf")


def test_last_radio_station_roundtrip(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    assert settings.last_radio_station is None
    settings.last_radio_station = {
        "name": "Radio Uno",
        "url": "http://uno",
        "genre": "Pop",
        "country": "España",
    }
    assert _settings(tmp_path).last_radio_station == {
        "name": "Radio Uno",
        "url": "http://uno",
        "genre": "Pop",
        "country": "España",
    }
    settings.last_radio_station = None
    assert _settings(tmp_path).last_radio_station is None


def test_stations_start_empty(tmp_path: Path) -> None:
    library = RadioLibrary(_settings(tmp_path))
    assert library.stations() == []
    assert library.custom_stations() == []
    assert library.found_stations() == []


def test_add_and_remove_custom_station(tmp_path: Path) -> None:
    library = RadioLibrary(_settings(tmp_path))
    station = RadioStation("Mi emisora", "http://example.com/a", "Rock", "España")

    assert library.add(station) is True
    assert library.add(station) is False  # URL repetida
    assert library.custom_stations() == [station]

    library.remove(station.url)
    assert library.custom_stations() == []


def test_custom_stations_persist_between_instances(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    RadioLibrary(settings).add(RadioStation("Fija", "http://example.com/f", "Jazz"))

    again = RadioLibrary(Settings(tmp_path / "radio-test.conf")).custom_stations()
    assert [station.name for station in again] == ["Fija"]


def test_update_custom_station(tmp_path: Path) -> None:
    library = RadioLibrary(_settings(tmp_path))
    library.add(RadioStation("Vieja", "http://example.com/v"))
    assert (
        library.update("http://example.com/v", RadioStation("Nueva", "http://example.com/v"))
        is True
    )
    assert [station.name for station in library.custom_stations()] == ["Nueva"]
    assert library.update("http://example.com/otra", RadioStation("X", "http://x")) is False


def test_found_stations_persist_and_are_listed(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    library = RadioLibrary(settings)
    found = [
        RadioStation("Jazz FM", "http://example.com/j", "Jazz", "España"),
        RadioStation("Suiza Pop", "http://example.com/s", "Pop", "Suiza"),
    ]
    library.set_found_stations(found)

    again = RadioLibrary(Settings(tmp_path / "radio-test.conf")).stations()
    assert [station.name for station in again] == ["Jazz FM", "Suiza Pop"]


def test_corrupt_json_is_ignored(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.radio_stations = "{no es json"
    assert RadioLibrary(settings).custom_stations() == []


def test_search_matches_name_genre_and_country(tmp_path: Path) -> None:
    library = RadioLibrary(_settings(tmp_path))
    library.set_found_stations(
        [
            RadioStation("Jazz FM", "http://example.com/j", "Jazz", "España"),
            RadioStation("Suiza Pop", "http://example.com/s", "Pop", "Suiza"),
        ]
    )
    assert library.search("jazz")
    assert library.search("suiza")
    assert library.search("") == library.stations()
    assert library.search("no-existe-xyz") == []


def test_found_station_can_be_edited(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    library = RadioLibrary(settings)
    library.set_found_stations([RadioStation("Vieja", "http://example.com/v", "Pop", "España")])
    base = library.stations()[0]
    edited = RadioStation("Nombre nuevo", base.url, "Rock", "España")

    assert library.update(base.url, edited) is True
    current = RadioLibrary(settings).stations()[0]
    assert current.name == "Nombre nuevo"
    assert current.genre == "Rock"
    assert current.country == "España"
    assert library.custom_stations() == []


def test_found_station_can_be_removed(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    library = RadioLibrary(settings)
    library.set_found_stations([RadioStation("Vieja", "http://example.com/v")])
    url = library.stations()[0].url

    library.remove(url)

    assert all(station.url != url for station in library.stations())
    assert all(station.url != url for station in RadioLibrary(settings).stations())


def test_parse_stations_ignores_broken_entries() -> None:
    from app.radio import parse_stations

    payload = [
        {"name": "Buena", "url_resolved": "http://a", "tags": "pop,rock", "country": "España"},
        {"name": "Repetida", "url_resolved": "http://a"},
        {"name": "", "url_resolved": "http://vacia"},
        {"name": "Sin URL"},
        "no soy un dict",
    ]

    stations = parse_stations(payload)
    assert len(stations) == 1
    assert stations[0].name == "Buena"
    assert stations[0].genre == "pop"


def test_radio_dialog_includes_country(qapp: QApplication, tmp_path: Path) -> None:
    from app.ui.radio_panel import RadioStationDialog

    dialog = RadioStationDialog(RadioStation("E", "http://e", "Pop", "Suiza"))
    assert dialog.station().country == "Suiza"


class FakeBackend:
    def __init__(self) -> None:
        self.on_finished = None
        self.on_error = None
        self.loaded: list[str] = []

    def load(self, path: str) -> None:
        self.loaded.append(path)

    def play(self) -> None: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def stop(self) -> None: ...
    def seek(self, position_ms: int) -> None: ...
    def set_volume(self, volume: int) -> None: ...
    def get_volume(self) -> int:
        return 100

    def set_muted(self, muted: bool) -> None: ...
    def is_muted(self) -> bool:
        return False

    def is_playing(self) -> bool:
        return True

    def is_paused(self) -> bool:
        return False

    def position_ms(self) -> int:
        return 0

    def duration_ms(self) -> int:
        return 0

    def release(self) -> None: ...


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_player_play_stream_emits_track(qapp: QApplication, tmp_path: Path) -> None:
    backend = FakeBackend()
    player = Player(backend=backend, settings=_settings(tmp_path))  # type: ignore[arg-type]
    received: list[object] = []
    player.track_changed.connect(received.append)
    try:
        assert player.play_stream("http://example.com/live", "Emisora", "Radio") is True
        assert backend.loaded == ["http://example.com/live"]
        assert player.state == STATE_PLAYING
        assert received and received[0].title == "Emisora"
        # MPRIS y el sistema deben ver la emisora como pista actual.
        assert player.is_stream is True
        current = player.current_track
        assert current is not None and current.title == "Emisora"
        player.stop()
        assert player.is_stream is False
    finally:
        player.shutdown()


def test_panel_emits_play_for_selected_station(qapp: QApplication, tmp_path: Path) -> None:
    library = RadioLibrary(_settings(tmp_path))
    library.set_found_stations([RadioStation("Uno", "http://uno", "Pop", "España")])
    panel = RadioPanel(library)
    received: list[RadioStation] = []
    panel.play_requested.connect(received.append)

    panel._table.setCurrentCell(0, 0)  # noqa: SLF001 - tests
    panel._play_selected()  # noqa: SLF001 - tests

    assert len(received) == 1
    assert received[0].name == "Uno"
    assert received[0].url == "http://uno"


def test_panel_empty_state_offers_search(qapp: QApplication, tmp_path: Path) -> None:
    library = RadioLibrary(_settings(tmp_path))
    panel = RadioPanel(library)
    requested: list[int] = []
    panel.search_requested.connect(lambda: requested.append(1))

    assert panel._normal.isHidden() and not panel._empty.isHidden()  # noqa: SLF001 - tests
    assert panel._button_search.isEnabled()  # noqa: SLF001 - tests

    panel._button_search.click()  # noqa: SLF001 - tests
    assert requested == [1]


def test_panel_select_relative_wraps_and_plays(qapp: QApplication, tmp_path: Path) -> None:
    library = RadioLibrary(_settings(tmp_path))
    library.set_found_stations(
        [
            RadioStation("Uno", "http://uno", "Pop", "España"),
            RadioStation("Dos", "http://dos", "Rock", "España"),
        ]
    )
    panel = RadioPanel(library)
    played: list[RadioStation] = []
    panel.play_requested.connect(played.append)

    panel.select_relative(1)
    panel.select_relative(1)  # avanza a la segunda
    panel.select_relative(-1)  # vuelve a la primera

    assert [station.name for station in played] == ["Uno", "Dos", "Uno"]


def test_panel_bottom_buttons_are_edit_remove_new(qapp: QApplication, tmp_path: Path) -> None:
    library = RadioLibrary(_settings(tmp_path))
    library.set_found_stations([RadioStation("Uno", "http://uno", "Pop", "España")])
    panel = RadioPanel(library)
    textos = [
        panel._button_edit.text(),  # noqa: SLF001 - tests
        panel._button_remove.text(),  # noqa: SLF001 - tests
        panel._button_add.text(),  # noqa: SLF001 - tests
    ]
    assert textos == ["Editar", "Eliminar", "Nuevo"]
    assert not hasattr(panel, "_button_play")
    assert not hasattr(panel, "_button_stop")
