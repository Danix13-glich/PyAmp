from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class AppSignals(QObject):

    #: Nueva pista sonando (objeto Track). Emitida por core/player.py.
    track_changed = Signal(object)
    #: Estado de reproducción: "playing" | "paused" | "stopped".
    playback_state_changed = Signal(str)
    #: Posición de reproducción en milisegundos.
    position_changed = Signal(int)
    #: Duración total en milisegundos (0 si desconocida).
    duration_changed = Signal(int)
    #: Volumen actual 0..100.
    volume_changed = Signal(int)
    #: Mensaje de error (no fatal: la reproducción continúa).
    error_occurred = Signal(str)


#: Instancia global del bus de señales.
app_signals = AppSignals()
