from __future__ import annotations

import wave
from pathlib import Path

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.player import RESUME_SEEK_DELAY_MS, STATE_PLAYING, Player
from app.core.settings import Settings, get_settings

#: Duración del WAV de prueba y espera del tick de sondeo.
WAV_SECONDS = 3
SAMPLE_WAIT_MS = 1100


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def make_wav(path: Path, seconds: int = WAV_SECONDS) -> Path:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"\x00\x00" * 8000 * seconds)
    return path


def test_position_advances_in_real_milliseconds(qapp: QApplication, tmp_path: Path) -> None:
    wav = make_wav(tmp_path / "posicion.wav")
    player = Player(settings=get_settings())
    if not player.is_available:
        pytest.skip("VLC no disponible en este entorno")
    try:
        positions: list[int] = []
        player.position_changed.connect(positions.append)

        player.add_paths([str(wav)])
        assert player.play_index(0) is True
        assert player.state == STATE_PLAYING

        loop = QEventLoop()
        QTimer.singleShot(SAMPLE_WAIT_MS, loop.quit)
        loop.exec()

        # Varias muestras crecientes y en milisegundos reales.
        assert len(positions) >= 3, positions
        real = [position for position in positions if position > 0]
        assert real, positions
        assert real == sorted(real), positions
        assert max(real) > 500, f"avance demasiado pequeño: {positions}"
        assert max(real) < WAV_SECONDS * 1000 + 500, f"position imposible: {positions}"
    finally:
        player.shutdown()


def test_toggle_pause_roundtrip(qapp: QApplication, tmp_path: Path) -> None:
    wav = make_wav(tmp_path / "pausa.wav", seconds=2)
    player = Player(settings=get_settings())
    if not player.is_available:
        pytest.skip("VLC no disponible en este entorno")
    try:
        player.add_paths([str(wav)])
        player.play_index(0)
        assert player.state == STATE_PLAYING

        player.toggle_pause()
        assert player.state == "paused"

        player.toggle_pause()
        assert player.state == STATE_PLAYING
    finally:
        player.shutdown()


def test_play_merges_real_codec_from_file(qapp: QApplication, tmp_path: Path) -> None:
    wav = make_wav(tmp_path / "codec-merge.wav", seconds=1)
    player = Player(settings=get_settings())
    if not player.is_available:
        pytest.skip("VLC no disponible en este entorno")
    try:
        player.add_paths([str(wav)])
        assert player.play_index(0) is True

        current = player.current_track
        assert current is not None
        assert current.codec == "WAV"  # leído del archivo, no adivinado
    finally:
        player.shutdown()


# --------------------------------------------- aleatorio y repetir (0.1.6)
class FakeBackend:

    def __init__(self) -> None:
        self.on_finished = None
        self.on_error = None
        self.loaded: list[str] = []
        self.seeks: list[int] = []
        self._muted = False

    def load(self, path: str) -> None:
        self.loaded.append(path)

    def play(self) -> None: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def stop(self) -> None: ...
    def seek(self, position_ms: int) -> None:
        self.seeks.append(position_ms)

    def set_volume(self, volume: int) -> None: ...
    def get_volume(self) -> int:
        return 100

    def set_muted(self, muted: bool) -> None:
        self._muted = bool(muted)

    def is_muted(self) -> bool:
        return self._muted

    def is_playing(self) -> bool:
        return True

    def is_paused(self) -> bool:
        return False

    def position_ms(self) -> int:
        return 0

    def duration_ms(self) -> int:
        return 0

    def release(self) -> None: ...


def _fake_player(
    track_count: int = 5, settings: Settings | None = None
) -> tuple[Player, FakeBackend]:
    from app.core.playlist import PlaylistModel
    from app.library.models import Track

    backend = FakeBackend()
    playlist = PlaylistModel([Track(path=f"/tmp/fake-{index}.wav") for index in range(track_count)])
    player = Player(backend=backend, playlist=playlist, settings=settings)  # type: ignore[arg-type]
    player.playlist.set_current(0)
    return player, backend


def _isolated_settings(tmp_path: Path) -> Settings:
    from app.core.settings import Settings

    return Settings(tmp_path / "PyAmp-test.conf")


def test_shuffle_picks_random_other_index(qapp: QApplication, tmp_path, monkeypatch) -> None:
    settings = _isolated_settings(tmp_path)
    player, _backend = _fake_player(settings=settings)
    try:
        player.shuffle = True
        monkeypatch.setattr("app.core.player.random.choices", lambda population, weights, k: [3])
        assert player.next() is True
        assert player.playlist.current_index == 3  # salta la actual (0)

        monkeypatch.setattr("app.core.player.random.choices", lambda population, weights, k: [4])
        assert player.next() is True
        assert player.playlist.current_index == 4
    finally:
        player.shutdown()


def test_shuffle_favors_favorites(qapp: QApplication, tmp_path, monkeypatch) -> None:
    settings = _isolated_settings(tmp_path)
    player, _backend = _fake_player(settings=settings)
    try:
        player.shuffle = True
        player.playlist[2].is_favorite = True
        captured: dict[str, list[float] | list[int]] = {}

        def fake_choices(population, weights, k):
            captured["population"] = list(population)
            captured["weights"] = list(weights)
            return [population[0]]

        monkeypatch.setattr("app.core.player.random.choices", fake_choices)
        player.playlist.set_current(0)
        player.next()

        population = captured["population"]
        weights = captured["weights"]
        assert 0 not in population  # nunca la actual
        assert weights[population.index(2)] == player.FAVORITE_SHUFFLE_WEIGHT
        assert weights[population.index(1)] == 1.0
    finally:
        player.shutdown()


def test_shuffle_off_uses_sequential_order(qapp: QApplication, tmp_path) -> None:
    settings = _isolated_settings(tmp_path)
    player, _backend = _fake_player(track_count=3, settings=settings)
    try:
        player.shuffle = False
        assert player.next() is True
        assert player.playlist.current_index == 1
        assert player.next() is True
        assert player.playlist.current_index == 2
        assert player.next() is False  # última sin repetición
    finally:
        player.shutdown()


def test_repeat_replays_current_once_then_turns_off(qapp: QApplication, tmp_path) -> None:
    settings = _isolated_settings(tmp_path)
    player, _backend = _fake_player(track_count=3, settings=settings)
    try:
        player.repeat = True
        player.playlist.set_current(2)
        emitted: list[bool] = []
        player.repeat_consumed.connect(lambda: emitted.append(True))

        player._auto_advance()  # noqa: SLF001 - fin de pista simulado

        assert player.playlist.current_index == 2  # se repite la misma pista
        assert player.repeat is False
        assert settings.repeat is False
        assert emitted == [True]
    finally:
        player.shutdown()


def test_shuffle_and_repeat_persist_in_settings(qapp: QApplication, tmp_path) -> None:
    settings = _isolated_settings(tmp_path)
    assert settings.shuffle is False and settings.repeat is False

    player, _backend = _fake_player(settings=settings)
    try:
        player.shuffle = True
        player.repeat = True
        assert settings.shuffle is True and settings.repeat is True
        player.shuffle = False
        player.repeat = False
        assert settings.shuffle is False and settings.repeat is False
    finally:
        player.shutdown()


def test_vlc_end_callback_no_llama_a_vlc_reentrante() -> None:
    from app.audio.vlc_backend import VlcBackend

    backend = VlcBackend.__new__(VlcBackend)
    calls: list[str] = []

    class _Analyzer:
        def stop(self) -> None:
            calls.append("stop")

    backend._analyzer = _Analyzer()  # noqa: SLF001 - test del callback
    backend.on_finished = lambda: calls.append("finished")
    backend._on_end(None)  # noqa: SLF001 - test del callback

    assert calls == ["finished"]


def test_last_playback_roundtrip(tmp_path: Path) -> None:
    settings = _isolated_settings(tmp_path)
    assert settings.last_playback is None

    settings.last_playback = {
        "path": "/tmp/cancion.mp3",
        "position_ms": 42000,
        "state": "playing",
    }

    restored = _isolated_settings(tmp_path).last_playback
    assert restored == {
        "path": "/tmp/cancion.mp3",
        "position_ms": 42000,
        "state": "playing",
    }

    settings.last_playback = {"path": "/tmp/cancion.mp3", "position_ms": 0}
    assert _isolated_settings(tmp_path).last_playback is None


def test_resume_position_se_aplica_tras_arrancar(qapp: QApplication, tmp_path: Path) -> None:
    settings = _isolated_settings(tmp_path)
    player, backend = _fake_player(settings=settings)
    try:
        player.set_resume_position(42000, "/tmp/fake-0.wav")
        assert player.play_index(0) is True
        assert backend.seeks == []  # VLC necesita un instante para cargar

        QTest.qWait(RESUME_SEEK_DELAY_MS + 100)

        assert backend.seeks == [42000]
    finally:
        player.shutdown()


def test_resume_position_no_afecta_a_otra_pista(qapp: QApplication, tmp_path: Path) -> None:
    settings = _isolated_settings(tmp_path)
    player, backend = _fake_player(settings=settings)
    try:
        player.set_resume_position(42000, "/tmp/fake-2.wav")
        assert player.play_index(0) is True

        QTest.qWait(RESUME_SEEK_DELAY_MS + 100)

        assert backend.seeks == []
    finally:
        player.shutdown()
