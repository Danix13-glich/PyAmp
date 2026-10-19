from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable


class BackendError(Exception):
    pass


class AudioBackend(ABC):

    #: Se ejecuta cuando la pista actual termina (hilo del backend).
    on_finished: Callable[[], None] | None = None
    #: Se ejecuta con un mensaje de error de reproducción (hilo del backend).
    on_error: Callable[[str], None] | None = None

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
