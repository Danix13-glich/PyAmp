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
from app.core.settings import get_settings

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
