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


def test_builtin_stations_are_listed(tmp_path: Path) -> None:
    library = RadioLibrary(_settings(tmp_path))
    stations = library.stations()
    assert stations
    assert all(station.builtin for station in stations)
    assert library.custom_stations() == []


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


def test_corrupt_json_is_ignored(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    settings.radio_stations = "{no es json"
    assert RadioLibrary(settings).custom_stations() == []


def test_search_matches_name_genre_and_country(tmp_path: Path) -> None:
    library = RadioLibrary(_settings(tmp_path))
    assert library.search("jazz")
    assert library.search("suiza")
    assert library.search("") == library.stations()
    assert library.search("no-existe-xyz") == []


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
    finally:
        player.shutdown()


def test_panel_emits_play_for_selected_station(qapp: QApplication, tmp_path: Path) -> None:
    library = RadioLibrary(_settings(tmp_path))
    panel = RadioPanel(library)
    received: list[RadioStation] = []
    panel.play_requested.connect(received.append)

    panel._table.setCurrentCell(0, 0)  # noqa: SLF001 - tests
    panel._button_play.click()  # noqa: SLF001 - tests

    assert received and received[0] is library.stations()[0]
