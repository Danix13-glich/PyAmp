"""Interfaz abstracta del backend de audio.

Regla del proyecto: el backend es intercambiable (VLC en la Fase 1, otro
motor en el futuro). Toda la reproducción pasa por esta interfaz;
``core/player.py`` es la única fachada que la usa y la UI jamás toca el
backend directamente.

Los eventos (``on_finished`` / ``on_error``) se ejecutan en el hilo del
backend (p. ej. el hilo interno de VLC): dentro de ellos NO se debe llamar
a ningún método del backend (riesgo de deadlock en VLC) — se emite una
señal Qt y el hilo principal decide.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable


class BackendError(Exception):
    """Error del backend de audio (libVLC ausente, archivo no encontrado...)."""


class AudioBackend(ABC):
    """Interfaz abstracta de reproducción de audio.

    Implementaciones: :class:`app.audio.vlc_backend.VlcBackend`.
    """

    #: Se ejecuta cuando la pista actual termina (hilo del backend).
    on_finished: Callable[[], None] | None = None
    #: Se ejecuta con un mensaje de error de reproducción (hilo del backend).
    on_error: Callable[[str], None] | None = None

    @abstractmethod
    def load(self, path: str) -> None:
        """Carga un archivo de audio sin reproducirlo aún.

        Args:
            path: Ruta absoluta o relativa del archivo.

        Raises:
            BackendError: Si el archivo no existe o no se puede cargar.
        """

    @abstractmethod
    def play(self) -> None:
        """Inicia (o reanuda) la reproducción de la pista cargada."""

    @abstractmethod
    def pause(self) -> None:
        """Pausa la reproducción conservando la posición."""

    @abstractmethod
    def resume(self) -> None:
        """Reanuda desde la posición de pausa."""

    @abstractmethod
    def stop(self) -> None:
        """Detiene la reproducción y deja la pista al inicio."""

    @abstractmethod
    def seek(self, position_ms: int) -> None:
        """Mueve el cursor de reproducción.

        Args:
            position_ms: Posición objetivo en milisegundos (>= 0).
        """

    @abstractmethod
    def set_volume(self, volume: int) -> None:
        """Ajusta el volumen.

        Args:
            volume: Volumen entero 0..100.
        """

    @abstractmethod
    def get_volume(self) -> int:
        """Devuelve el volumen actual 0..100."""

    @abstractmethod
    def set_muted(self, muted: bool) -> None:
        """Activa o desactiva el silencio.

        Args:
            muted: True para silenciar.
        """

    @abstractmethod
    def is_muted(self) -> bool:
        """True si el audio está silenciado."""

    @abstractmethod
    def is_playing(self) -> bool:
        """True si la reproducción está activa (no pausada ni detenida)."""

    @abstractmethod
    def is_paused(self) -> bool:
        """True si la reproducción está en pausa."""

    @abstractmethod
    def position_ms(self) -> int:
        """Posición actual en milisegundos (0 si no disponible)."""

    @abstractmethod
    def duration_ms(self) -> int:
        """Duración total en milisegundos (0 si aún no se conoce)."""

    @abstractmethod
    def release(self) -> None:
        """Libera los recursos del backend (llamar al cerrar la app)."""
