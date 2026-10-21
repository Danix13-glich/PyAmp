from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

import numpy as np

#: Formato fijo que se pide a libVLC para analizar el audio (mono, 16 bits).
SPECTRUM_RATE = 44100
SPECTRUM_CHUNK = 2048


class BackendError(Exception):
    pass


class AudioBackend(ABC):

    #: Se ejecuta cuando la pista actual termina (hilo del backend).
    on_finished: Callable[[], None] | None = None
    #: Se ejecuta con un mensaje de error de reproducción (hilo del backend).
    on_error: Callable[[str], None] | None = None

    def set_spectrum_sink(self, sink: Callable[[np.ndarray], None] | None) -> None:
        # Opcional: los backends que pueden analizar audio lo sobrescriben.
        self._spectrum_sink = sink

    @abstractmethod
    def load(self, path: str) -> None:
        pass

    @abstractmethod
    def play(self) -> None:
        pass

    @abstractmethod
    def pause(self) -> None:
        pass

    @abstractmethod
    def resume(self) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def seek(self, position_ms: int) -> None:
        pass

    @abstractmethod
    def set_volume(self, volume: int) -> None:
        pass

    @abstractmethod
    def get_volume(self) -> int:
        pass

    @abstractmethod
    def set_muted(self, muted: bool) -> None:
        pass

    @abstractmethod
    def is_muted(self) -> bool:
        pass

    @abstractmethod
    def is_playing(self) -> bool:
        pass

    @abstractmethod
    def is_paused(self) -> bool:
        pass

    @abstractmethod
    def position_ms(self) -> int:
        pass

    @abstractmethod
    def duration_ms(self) -> int:
        pass

    @abstractmethod
    def release(self) -> None:
        pass
