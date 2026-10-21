from __future__ import annotations

import logging

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from app.audio.base_backend import SPECTRUM_CHUNK, SPECTRUM_RATE

logger = logging.getLogger(__name__)

#: Número de barras dibujadas (11 bandas iguales; la última del rango
#: agudo no se usaba y se eliminó para no dejar una barra muerta).
BAR_COUNT = 11

#: Parámetros del análisis (float32 mono).
SAMPLE_RATE = SPECTRUM_RATE
CHUNK_FRAMES = SPECTRUM_CHUNK

#: Repintado (~30 fps) y caída de las barras.
TICK_MS = 33
DECAY = 0.86

#: Rango de frecuencias cubierto por las barras (Hz).
FREQ_MIN = 40.0
FREQ_MAX = 16000.0

#: Altura del widget (las barras llegan a ~60 px
#: de alto total, arriba y abajo de la línea central).
SPECTRUM_HEIGHT = 64

#: Ancho del widget (fijo: 5 barras caben sin estirarse; en la cabecera
#: horizontal un QWidget sin ancho mínimo colapsaba a 0 y no se veía).
SPECTRUM_WIDTH_PX = 120

#: Tono azul de las barras (HSV: azul-cian según el nivel).
BAR_HUE = 210

#: Fondo y línea central por defecto (look histórico); el tema activo los
#: sustituye con ``set_spectrum_colors``.
DEFAULT_BG = "#181818"
DEFAULT_LINE = "#464646"


class SpectrumWidget(QWidget):
    # El audio llega del hilo de libVLC como muestras ya decodificadas:
    # nunca se captura el micrófono ni la salida del sistema.

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(SPECTRUM_HEIGHT)
        self.setFixedWidth(SPECTRUM_WIDTH_PX)
        self.setToolTip("Espectro de la salida de audio")

        self._bars = np.zeros(BAR_COUNT, dtype=np.float32)
        self._pending: np.ndarray | None = None
        self._playing = False
        self._hue = BAR_HUE
        self._bg_color = QColor(DEFAULT_BG)
        self._line_color = QColor(DEFAULT_LINE)
        # None = aún sin datos; True = el backend entrega audio analizable.
        self._available: bool | None = None

        # Máscaras de banda precomputadas (el tamaño de chunk es fijo).
        freqs = np.fft.rfftfreq(CHUNK_FRAMES, d=1.0 / SAMPLE_RATE)
        edges = np.logspace(np.log10(FREQ_MIN), np.log10(FREQ_MAX), BAR_COUNT + 1)
        self._masks = [
            (freqs >= edges[index]) & (freqs < edges[index + 1]) for index in range(BAR_COUNT)
        ]

        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._tick)

    # ------------------------------------------------------------- control
    def set_playing(self, playing: bool) -> None:
        if playing == self._playing:
            return
        self._playing = playing
        if playing:
            self._timer.start()
        else:
            self._timer.stop()
            self._pending = None
            self._bars *= DECAY
            self.update()

    def push_samples(self, chunk: np.ndarray) -> None:
        if chunk.size == 0:
            return
        # Llega del hilo de VLC (señal encolada): solo se guarda el último
        # bloque y el temporizador de la UI hace la FFT.
        self._available = True
        self._pending = np.asarray(chunk, dtype=np.float32)

    def set_hue(self, hue: int) -> None:
        self._hue = max(0, min(359, int(hue)))
        self.update()

    def set_spectrum_colors(self, background: str, line: str) -> None:
        bg = QColor(background)
        if bg.isValid():
            self._bg_color = bg
        line_color = QColor(line)
        if line_color.isValid():
            self._line_color = line_color
        self.update()

    @property
    def available(self) -> bool | None:
        return self._available

    def stop_capture(self) -> None:
        # Se conserva el nombre por compatibilidad: aquí solo se descarta el
        # último bloque pendiente.
        self._pending = None

    def shutdown(self) -> None:
        self._timer.stop()
        self.stop_capture()

    # ------------------------------------------------------------- repintado
    def _tick(self) -> None:
        chunk = self._pending
        if chunk is not None and self._playing:
            self._pending = None
            spectrum = self._compute(chunk)
            if spectrum is not None:
                self._bars = np.maximum(spectrum, self._bars * DECAY)
            else:
                self._bars *= DECAY
        else:
            self._bars *= DECAY
        self.update()

    def _compute(self, chunk: np.ndarray) -> np.ndarray | None:
        if chunk.size < 512:
            return None
        window = np.hanning(chunk.size)
        magnitudes = np.abs(np.fft.rfft(chunk * window))
        # Normalizar a amplitud 0..1 (un seno a escala completa da 1.0).
        # Sin esto, las magnitudes crudas de la FFT (cientos) saturaban la
        # escala dB y TODAS las barras se quedaban pegadas al máximo.
        magnitudes /= max(1e-9, float(window.sum()) / 2.0)
        bands = np.array(
            [magnitudes[mask].max() if mask.any() else 0.0 for mask in self._masks],
            dtype=np.float32,
        )
        # Escala dB: −60 dB (ruido) .. 0 dB (fuerte) → 0..1.
        levels = (20.0 * np.log10(bands + 1e-9) + 60.0) / 60.0
        return np.clip(levels, 0.0, 1.0).astype(np.float32)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        painter.fillRect(rect, self._bg_color)

        gap = 2
        width = rect.width()
        height = rect.height()
        mid = height // 2  # línea central: cada barra crece hacia arriba y abajo
        max_half = max(1, (height - 4) // 2)  # altura máxima = alto completo
        # Reparto que ocupa todo el ancho: sin franja vacía en el extremo derecho.
        bar_width = max(1, (width - gap * (BAR_COUNT - 1)) // BAR_COUNT)
        used = bar_width * BAR_COUNT + gap * (BAR_COUNT - 1)
        offset = max(0, (width - used) // 2)
        for index, level in enumerate(np.asarray(self._bars)):
            half = int(float(level) * max_half)
            if half <= 0:
                continue
            x = offset + index * (bar_width + gap)
            # Tono del tema, más brillante cuanto más fuerte es el nivel.
            color = QColor.fromHsv(self._hue, 190, 150 + int(105 * float(level)))
            painter.fillRect(x, mid - half, bar_width, half * 2, color)
        painter.setPen(self._line_color)
        painter.drawLine(0, mid, width, mid)  # línea divisoria en la mitad
        painter.end()
