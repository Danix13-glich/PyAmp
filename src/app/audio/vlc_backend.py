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
    try:
        import vlc
    except Exception as exc:  # noqa: BLE001 - ImportError, NotImplementedError, OSError...
        raise BackendError(f"{VLC_NOT_FOUND_MSG} ({exc})") from exc
    return vlc


class VlcBackend(AudioBackend):

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
        text = str(path).strip()
        if "://" in text:
            media = self._instance.media_new_location(text)
        else:
            file_path = Path(text).expanduser()
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
        self._player.play()

    def pause(self) -> None:
        self._player.set_pause(1)

    def resume(self) -> None:
        self._player.set_pause(0)

    def stop(self) -> None:
        self._player.stop()

    def seek(self, position_ms: int) -> None:
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
        self._volume = max(0, min(100, int(volume)))
        self._audio_dirty = True
        self._apply_audio_if_ready()

    def get_volume(self) -> int:
        return self._volume

    def set_muted(self, muted: bool) -> None:
        self._muted = bool(muted)
        self._audio_dirty = True
        self._apply_audio_if_ready()

    def is_muted(self) -> bool:
        return self._muted

    def _apply_audio_if_ready(self) -> bool:
        if not self._audio_dirty or not self.is_playing():
            return False
        self._player.audio_set_volume(self._volume)
        self._player.audio_set_mute(self._muted)
        self._audio_dirty = False
        logger.debug("Audio aplicado: volumen=%d mute=%s", self._volume, self._muted)
        return True

    # ------------------------------------------------------------------ estado
    def is_playing(self) -> bool:
        return self._player.get_state() == self._vlc.State.Playing

    def is_paused(self) -> bool:
        return self._player.get_state() == self._vlc.State.Paused

    def position_ms(self) -> int:
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
        length = self._player.get_length()
        if not length or length < 0:
            return 0
        return int(length)

    def release(self) -> None:
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
        if self.on_finished is not None:
            self.on_finished()

    def _on_error_event(self, _event: Any) -> None:
        if self.on_error is not None:
            self.on_error("VLC informó un error al reproducir la pista")
