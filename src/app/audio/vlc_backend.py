"""Backend de audio basado en libVLC (python-vlc).

Implementa :class:`app.audio.base_backend.AudioBackend` sobre VLC.

Notas técnicas importantes:

* ``import vlc`` carga libVLC **al importar** y falla con ``NotImplementedError``
  si no hay libVLC en el sistema — por eso la importación va dentro de una
  función y el error se convierte en :class:`BackendError` (la app no crashea:
  lo muestra y sigue viva, según los RNF).
* Los callbacks de VLC llegan desde un hilo interno de VLC. Aquí **no se
  llama nunca a VLC** dentro de un callback (deadlock conocido): solo se
  invocan ``on_finished`` / ``on_error``, que el player traduce a señales Qt.
"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from typing import Any

from .base_backend import AudioBackend, BackendError

logger = logging.getLogger(__name__)

VLC_NOT_FOUND_MSG = (
    "libVLC no está instalado. En Fedora: sudo dnf install vlc · "
    "En Debian/Ubuntu: sudo apt install vlc · En Windows/macOS: instala VLC "
    "desde videolan.org"
)


def _load_vlc() -> Any:
    """Importa python-vlc y devuelve el módulo.

    Returns:
        El módulo ``vlc``.

    Raises:
        BackendError: Si libVLC no está instalado o no se puede cargar.
    """
    try:
        import vlc
    except Exception as exc:  # noqa: BLE001 - ImportError, NotImplementedError, OSError...
        raise BackendError(f"{VLC_NOT_FOUND_MSG} ({exc})") from exc
    return vlc


class VlcBackend(AudioBackend):
    """Backend de reproducción sobre libVLC.

    Raises:
        BackendError: Si libVLC no está disponible en el sistema.
    """

    def __init__(self) -> None:
        self._vlc = _load_vlc()
        self._instance = self._vlc.Instance("--no-video", "--quiet")
        if self._instance is None:
            raise BackendError("No se pudo crear la instancia de libVLC")
        self._player = self._instance.media_player_new()
        if self._player is None:
            raise BackendError("No se pudo crear el reproductor de libVLC")
        # Estado de audio en memoria: libVLC (Fedora 44 / VLC 3.0.23) hace
        # SIGSEGV si se llama audio_set_volume/audio_set_mute antes de que
        # exista una salida de audio (aout). Por eso se guarda el valor y se
        # difiere la llamada real hasta que is_playing() sea True (el poll
        # del player refresca vía position_ms()).
        self._volume = 100
        self._muted = False
        self._audio_dirty = False
        self._has_media = False

        events = self._player.event_manager()
        events.event_attach(self._vlc.EventType.MediaPlayerEndReached, self._on_end)
        events.event_attach(self._vlc.EventType.MediaPlayerEncounteredError, self._on_error_event)
        logger.info("Backend VLC listo (libVLC %s)", self._vlc.libvlc_get_version())

    # ------------------------------------------------------------------ carga
    def load(self, path: str) -> None:
        """Carga el archivo en el reproductor (sin reproducir).

        Raises:
            BackendError: Si el archivo no existe o VLC no lo acepta.
        """
        file_path = Path(path).expanduser()
        if not file_path.is_file():
            raise BackendError(f"Archivo no encontrado: {path}")
        media = self._instance.media_new_path(str(file_path.resolve()))
        if media is None:
            raise BackendError(f"VLC no pudo cargar: {path}")
        self._player.set_media(media)
        self._has_media = True
        with contextlib.suppress(Exception):  # el player mantiene su referencia
            media.release()

    # ------------------------------------------------------------- transporte
    def play(self) -> None:
        """Inicia la reproducción."""
        self._player.play()

    def pause(self) -> None:
        """Pausa la reproducción."""
        self._player.set_pause(1)

    def resume(self) -> None:
        """Reanuda la reproducción."""
        self._player.set_pause(0)

    def stop(self) -> None:
        """Detiene la reproducción."""
        self._player.stop()

    def seek(self, position_ms: int) -> None:
        """Mueve el cursor a ``position_ms`` (milisegundos reales).

        Usa ``set_time()`` (ms directos). ``set_position()`` espera una
        **fracción 0..1** — pasarle segundos hacía que VLC saltara al
        final del archivo (fin de pista → siguiente canción; bug Fase 5).
        Se conserva como fallback fracción×duración si el tiempo
        absoluto no lo admite el formato.
        """
        if not self._has_media:
            return  # sin media cargada: evitar llamadas fragiles a libVLC
        target = max(0, int(position_ms))
        length = self._player.get_length()
        if length and length > 0:
            target = min(target, int(length))
        applied = self._player.set_time(target)
        if applied is not None and applied >= 0:
            return
        # Fallback: posición relativa (0..1) cuando set_time no aplica.
        length = self._player.get_length()
        if length and length > 0:
            self._player.set_position(target / float(length))

    # ---------------------------------------------------------------- volumen
    def set_volume(self, volume: int) -> None:
        """Fija el volumen 0..100 (aplicación real diferida si no hay aout)."""
        self._volume = max(0, min(100, int(volume)))
        self._audio_dirty = True
        self._apply_audio_if_ready()

    def get_volume(self) -> int:
        """Devuelve el volumen actual 0..100 (estado en memoria)."""
        return self._volume

    def set_muted(self, muted: bool) -> None:
        """Silencia o restablece el audio (aplicación diferida si no hay aout)."""
        self._muted = bool(muted)
        self._audio_dirty = True
        self._apply_audio_if_ready()

    def is_muted(self) -> bool:
        """True si está silenciado (estado en memoria)."""
        return self._muted

    def _apply_audio_if_ready(self) -> bool:
        """Aplica volumen/silencio SOLO cuando hay contexto de audio.

        Llamar a ``audio_set_volume``/``audio_set_mute`` sin salida de audio
        provoca SIGSEGV en este libVLC (comprobado en Fedora 44). El guard es
        ``is_playing()``: cuando devuelve True, la aout ya existe.

        Returns:
            True si se aplicó; False si sigue pendiente.
        """
        if not self._audio_dirty or not self.is_playing():
            return False
        self._player.audio_set_volume(self._volume)
        self._player.audio_set_mute(self._muted)
        self._audio_dirty = False
        logger.debug("Audio aplicado: volumen=%d mute=%s", self._volume, self._muted)
        return True

    # ------------------------------------------------------------------ estado
    def is_playing(self) -> bool:
        """True si VLC está reproduciendo (estado Playing)."""
        return self._player.get_state() == self._vlc.State.Playing

    def is_paused(self) -> bool:
        """True si VLC está en pausa."""
        return self._player.get_state() == self._vlc.State.Paused

    def position_ms(self) -> int:
        """Posición actual en ms (0 si VLC devuelve -1 = no disponible).

        Usa ``get_time()`` (milisegundos directos). ``get_position()``
        devuelve una **fracción 0..1**, no ms — con la duración completa
        multiplicada daba una barra prácticamente congelada en MP3
        largos (bug Fase 4); se conserva solo como fallback.

        Además es el punto de refresco (lo llama el poll del player) para
        aplicar volumen/mute pendientes en cuanto hay aout — ver
        :meth:`_apply_audio_if_ready`.
        """
        self._apply_audio_if_ready()
        time_ms = self._player.get_time()
        if time_ms is not None and time_ms >= 0:
            return int(time_ms)
        # Fallback: fracción (0..1) × duración conocida.
        position = self._player.get_position()
        if position is None or position < 0:
            return 0
        length = self._player.get_length()
        if not length or length < 0:
            return 0
        return int(position * length)

    def duration_ms(self) -> int:
        """Duración en ms (0 si aún no la conoce VLC)."""
        length = self._player.get_length()
        if not length or length < 0:
            return 0
        return int(length)

    def release(self) -> None:
        """Detiene y libera los recursos de libVLC (mejor esfuerzo)."""
        try:
            self._player.stop()
        except Exception as exc:  # noqa: BLE001
            logger.debug("release: stop falló (%s)", exc)
        try:
            self._instance.release()
        except Exception as exc:  # noqa: BLE001
            logger.debug("release: instance.release falló (%s)", exc)

    # ----------------------------------------------------------------- eventos
    def _on_end(self, _event: Any) -> None:
        """Callback de fin de pista (HILO DE VLC — no llamar a VLC aquí)."""
        if self.on_finished is not None:
            self.on_finished()

    def _on_error_event(self, _event: Any) -> None:
        """Callback de error de reproducción (HILO DE VLC — no llamar a VLC)."""
        if self.on_error is not None:
            self.on_error("VLC informó un error al reproducir la pista")
