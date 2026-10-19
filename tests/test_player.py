"""Tests del reproductor (Fase 5): regresión de la posición del backend.

Bug Fase 4: ``VlcBackend.position_ms()`` multiplicaba ``get_position()``
(frácción 0..1) por 1000 — en archivos largos la barra de posición y el
temporizador quedaban prácticamente congelados. El fix usa ``get_time()``
(ms directos); este test comprueba que la posición avanza en milisegundos
reales.
"""

from __future__ import annotations

import wave
from pathlib import Path

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from app.core.player import STATE_PLAYING, Player
from app.core.settings import Settings, get_settings

#: Duración del WAV de prueba y espera del tick de sondeo.
WAV_SECONDS = 3
SAMPLE_WAIT_MS = 1100


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    """QApplication única offscreen (el Player necesita un event loop)."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def make_wav(path: Path, seconds: int = WAV_SECONDS) -> Path:
    """WAV mono PCM válido de ``seconds`` segundos (8 kHz)."""
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
    """El play unificado (Fase 4) conmuta correctamente con música real."""
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
    """Al reproducir, el códec real (mutagen) se fusiona en la pista actual."""
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
    """Backend mínimo para probar la lógica de orden sin VLC."""

    def __init__(self) -> None:
        self.on_finished = None
        self.on_error = None
        self.loaded: list[str] = []
        self._muted = False

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
    """Player con backend falso y ``track_count`` pistas en la playlist.

    El ``settings`` debe ser SIEMPRE una instancia aislada (archivo .conf
    en tmp): los tests nunca tocan la QSettings real del usuario.
    """
    from app.core.playlist import PlaylistModel
    from app.library.models import Track

    backend = FakeBackend()
    playlist = PlaylistModel([Track(path=f"/tmp/fake-{index}.wav") for index in range(track_count)])
    player = Player(backend=backend, playlist=playlist, settings=settings)  # type: ignore[arg-type]
    player.playlist.set_current(0)
    return player, backend


def _isolated_settings(tmp_path: Path) -> Settings:
    """QSettings nueva y aislada en un archivo .conf del tmp del test.

    Se usa una ruta explícita (no ``XDG_CONFIG_HOME``): QSettings cachea
    la ruta de configuración del sistema por proceso, así que cambiar la
    variable de entorno tras el primer ``QSettings`` no aísla nada.
    """
    from app.core.settings import Settings

    return Settings(tmp_path / "PyAmp-test.conf")


def test_shuffle_picks_random_other_index(qapp: QApplication, tmp_path, monkeypatch) -> None:
    """🔀: siguiente = índice al azar distinto del actual (determinista en test)."""
    settings = _isolated_settings(tmp_path)
    player, _backend = _fake_player(settings=settings)
    try:
        player.shuffle = True
        monkeypatch.setattr("app.core.player.random.randrange", lambda _n: 2)
        assert player.next() is True
        assert player.playlist.current_index == 3  # randrange(4)=2 → 2+1 (salta la actual 0)

        # Con la actual en 3 y randrange devolviendo 3: se desplaza a 4.
        monkeypatch.setattr("app.core.player.random.randrange", lambda _n: 3)
        assert player.next() is True
        assert player.playlist.current_index == 4
    finally:
        player.shutdown()


def test_shuffle_off_uses_sequential_order(qapp: QApplication, tmp_path) -> None:
    """Sin 🔀 el orden sigue siendo secuencial."""
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


def test_repeat_wraps_to_first_at_end(qapp: QApplication, tmp_path) -> None:
    """🔁: en la última pista, «siguiente» vuelve a la primera."""
    settings = _isolated_settings(tmp_path)
    player, _backend = _fake_player(track_count=3, settings=settings)
    try:
        player.repeat = True
        player.playlist.set_current(2)
        assert player.next() is True
        assert player.playlist.current_index == 0
    finally:
        player.shutdown()


def test_shuffle_and_repeat_persist_in_settings(qapp: QApplication, tmp_path) -> None:
    """🔀 y 🔁 quedan guardados en QSettings (aislado, nunca el real)."""
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
