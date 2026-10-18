"""Visualizador de espectro con barras reales (numpy + QPainter, Fase 4).

Toma el audio **real** de la salida del sistema en Linux: lanza ``parec``
sobre el monitor del sink por defecto (PulseAudio/PipeWire — presente en
Fedora) y calcula la FFT con numpy en un hilo lector. En plataformas sin
``parec``/``pactl`` el widget queda en reposo indicándolo: nunca inventa
movimiento.

Reglas: la UI nunca bloquea (lectura de audio en hilo propio, el
repintado es un QTimer de ~30 fps en el hilo de UI) y al cerrar la
ventana ``shutdown()`` termina el proceso de captura.
"""

from __future__ import annotations

import contextlib
import logging
import shutil
import subprocess
import threading

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

#: Número de barras dibujadas (ajuste Fase 6: 12 bandas iguales).
BAR_COUNT = 12

#: Parámetros de la captura (float32 mono).
SAMPLE_RATE = 44100
CHUNK_FRAMES = 2048  # muestras por FFT (~46 ms)
_FLOAT32_BYTES = 4

#: Repintado (~30 fps) y caída de las barras.
TICK_MS = 33
DECAY = 0.86

#: Rango de frecuencias cubierto por las barras (Hz).
FREQ_MIN = 40.0
FREQ_MAX = 16000.0

#: Altura del widget: el doble que en Fase 5 (las barras llegan a ~60 px
#: de alto total, arriba y abajo de la línea central).
SPECTRUM_HEIGHT = 64

#: Ancho del widget (fijo: 5 barras caben sin estirarse; en la cabecera
#: horizontal un QWidget sin ancho mínimo colapsaba a 0 y no se veía).
SPECTRUM_WIDTH_PX = 120

#: Tono azul de las barras (HSV: azul-cian según el nivel).
BAR_HUE = 210

_NO_SIGNAL_TEXT = "Espectro no disponible (se requiere parec/pactl)"


class SpectrumWidget(QWidget):
    """Barras de espectro alimentadas por la captura real del sink."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(SPECTRUM_HEIGHT)
        self.setFixedWidth(SPECTRUM_WIDTH_PX)
        self.setToolTip("Espectro de la salida de audio")

        self._bars = np.zeros(BAR_COUNT, dtype=np.float32)
        self._pending: np.ndarray | None = None
        self._playing = False
        self._process: subprocess.Popen[bytes] | None = None
        self._reader: threading.Thread | None = None
        self._stop_flag = threading.Event()
        # None = aún no probado; False = sin captura disponible.
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
        """Activa o frena la captura según el estado de reproducción."""
        if playing == self._playing:
            return
        self._playing = playing
        if playing:
            self._start_capture()
            self._timer.start()
        else:
            self._timer.stop()
            self._bars *= DECAY
            self.update()

    @property
    def available(self) -> bool | None:
        """True si hay captura; False si no; None si aún no se probó."""
        return self._available

    def shutdown(self) -> None:
        """Termina la captura (idempotente; se llama en closeEvent)."""
        self._timer.stop()
        self._stop_flag.set()
        process = self._process
        if process is not None and process.poll() is None:
            with contextlib.suppress(Exception):
                process.terminate()
        if self._reader is not None:
            with contextlib.suppress(RuntimeError):
                self._reader.join(timeout=1.0)
        self._process = None
        self._reader = None

    # ------------------------------------------------------------- captura
    def _start_capture(self) -> None:
        """Lanza ``parec`` sobre el monitor del sink por defecto (una vez)."""
        if self._process is not None or self._available is False:
            return
        try:
            monitor = self._default_monitor()
            if monitor is None:
                self._available = False
                logger.info("Espectro: sin monitor de audio (falta pactl/parec)")
                return
            self._process = subprocess.Popen(
                [
                    "parec",
                    f"--device={monitor}",
                    "--format=float32le",
                    f"--rate={SAMPLE_RATE}",
                    "--channels=1",
                    "--raw",
                    "--latency=50",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:  # noqa: BLE001 - el espectro es opcional
            self._available = False
            logger.info("Espectro: captura no disponible (%s)", exc)
            return
        self._available = True
        self._stop_flag.clear()
        self._reader = threading.Thread(target=self._read_loop, name="pyamp-spectrum", daemon=True)
        self._reader.start()
        logger.info("Espectro: captura iniciada (monitor del sink por defecto)")

    @staticmethod
    def _default_monitor() -> str | None:
        """Monitor de audio del sink por defecto (None si no hay entorno)."""
        pactl = shutil.which("pactl")
        if pactl is None or shutil.which("parec") is None:
            return None
        try:
            result = subprocess.run(
                [pactl, "get-default-sink"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("pactl falló: %s", exc)
            return None
        sink = result.stdout.strip()
        return f"{sink}.monitor" if sink else None

    def _read_loop(self) -> None:
        """Hilo lector: guarda chunks fijos de float32 en ``_pending``."""
        process = self._process
        if process is None or process.stdout is None:
            return
        wanted = CHUNK_FRAMES * _FLOAT32_BYTES
        buffer = bytearray()
        while not self._stop_flag.is_set():
            try:
                data = process.stdout.read1(8192)  # type: ignore[attr-defined]
            except (OSError, ValueError):
                break
            if not data:
                break
            buffer.extend(data)
            if len(buffer) >= wanted:
                self._pending = np.frombuffer(bytes(buffer[:wanted]), dtype=np.float32)
                del buffer[:wanted]

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
        """FFT → 40 niveles 0..1 en escala logarítmica de frecuencia."""
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
        painter.fillRect(rect, QColor(24, 24, 24))
        if self._available is False:
            painter.setPen(QColor(150, 150, 150))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, _NO_SIGNAL_TEXT)
            return

        gap = 2
        width = rect.width()
        height = rect.height()
        mid = height // 2  # línea central: cada barra crece hacia arriba y abajo
        max_half = max(1, (height - 4) // 2)  # altura máxima = alto completo
        bar_width = max(2, (width - gap * (BAR_COUNT + 1)) // BAR_COUNT)
        for index, level in enumerate(np.asarray(self._bars)):
            half = int(float(level) * max_half)
            if half <= 0:
                continue
            x = gap + index * (bar_width + gap)
            # Azul: tono fijo, más brillante cuanto más fuerte es el nivel.
            color = QColor.fromHsv(BAR_HUE, 190, 150 + int(105 * float(level)))
            painter.fillRect(x, mid - half, bar_width, half * 2, color)
        painter.setPen(QColor(70, 70, 70))
        painter.drawLine(0, mid, width, mid)  # línea divisoria en la mitad
        painter.end()
