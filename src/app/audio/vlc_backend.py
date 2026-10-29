from __future__ import annotations

import contextlib
import ctypes
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from .base_backend import SPECTRUM_CHUNK, SPECTRUM_RATE, AudioBackend, BackendError

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

        # Segundo reproductor solo para el espectro: decodifica el mismo
        # audio y entrega las muestras por callback, sin tocar la salida de
        # sonido ni capturar el micrófono. Los callbacks de audio de libVLC
        # sustituyen la salida de ese reproductor, no la del principal.
        self._analyzer: Any = None
        self._analyzer_cb: Any = None
        self._spectrum_sink: Callable[[np.ndarray], None] | None = None
        self._spectrum_buffer = np.zeros(0, dtype=np.float32)
        self._init_analyzer()

        events = self._player.event_manager()
        events.event_attach(self._vlc.EventType.MediaPlayerEndReached, self._on_end)
        events.event_attach(self._vlc.EventType.MediaPlayerEncounteredError, self._on_error_event)
        logger.info("Backend VLC listo (libVLC %s)", self._vlc.libvlc_get_version())

    # --------------------------------------------------------------- espectro
    def set_spectrum_sink(self, sink: Callable[[np.ndarray], None] | None) -> None:
        self._spectrum_sink = sink
        self._spectrum_buffer = np.zeros(0, dtype=np.float32)

    def _init_analyzer(self) -> None:
        try:
            analyzer = self._instance.media_player_new()
            if analyzer is None:
                return
            analyzer.audio_set_format("S16N", SPECTRUM_RATE, 1)
            callback = self._vlc.CallbackDecorators.AudioPlayCb(self._on_analyzer_audio)
            analyzer.audio_set_callbacks(callback, None, None, None, None, None)
            self._analyzer = analyzer
            self._analyzer_cb = callback
            logger.info("Espectro: análisis en paralelo con libVLC (sin captura)")
        except Exception as exc:  # noqa: BLE001 - el espectro es opcional
            self._analyzer = None
            self._analyzer_cb = None
            logger.info("Espectro no disponible: %s", exc)

    def _on_analyzer_audio(self, _data: int, samples: int, count: int, _pts: int) -> None:
        sink = self._spectrum_sink
        if sink is None or not samples or count <= 0:
            return
        try:
            raw = ctypes.string_at(samples, int(count) * 2)
        except Exception:  # noqa: BLE001 - puntero inválido al cerrar
            return
        chunk = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
        if chunk.size == 0:
            return
        buffer = np.concatenate((self._spectrum_buffer, chunk))
        while buffer.size >= SPECTRUM_CHUNK:
            block = buffer[:SPECTRUM_CHUNK]
            buffer = buffer[SPECTRUM_CHUNK:]
            try:
                sink(block)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Espectro: fallo al entregar muestras (%s)", exc)
                break
        self._spectrum_buffer = buffer

    def _load_analyzer(self, text: str) -> None:
        if self._analyzer is None:
            return
        # El analizador necesita su propio objeto Media: compartirlo con el
        # reproductor principal hace que libVLC libere eventos dos veces al
        # cambiar de pista y termine en SIGSEGV.
        with contextlib.suppress(Exception):
            if "://" in text:
                media = self._instance.media_new_location(text)
            else:
                media = self._instance.media_new_path(str(Path(text).expanduser().resolve()))
            if media is not None:
                self._analyzer.set_media(media)
                media.release()
        self._spectrum_buffer = np.zeros(0, dtype=np.float32)

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
        # Cambiar de media mientras suena (o justo al acabar) es una de las
        # causas de SIGSEGV en libVLC. Se detienen ambos reproductores desde
        # el hilo de UI antes de asignar la pista nueva.
        self._stop_players()
        self._player.set_media(media)
        self._load_analyzer(text)
        self._has_media = True
        with contextlib.suppress(Exception):  # el player mantiene su referencia
            media.release()

    # ------------------------------------------------------------- transporte
    def play(self) -> None:
        self._player.play()
        if self._analyzer is not None:
            with contextlib.suppress(Exception):
                self._analyzer.play()

    def pause(self) -> None:
        self._player.set_pause(1)
        if self._analyzer is not None:
            with contextlib.suppress(Exception):
                self._analyzer.set_pause(1)

    def resume(self) -> None:
        self._player.set_pause(0)
        if self._analyzer is not None:
            with contextlib.suppress(Exception):
                self._analyzer.set_pause(0)

    def _stop_players(self) -> None:
        if not self._has_media:
            return
        with contextlib.suppress(Exception):
            self._player.stop()
        if self._analyzer is not None:
            with contextlib.suppress(Exception):
                self._analyzer.stop()

    def stop(self) -> None:
        self._stop_players()
        self._has_media = False
        self._spectrum_buffer = np.zeros(0, dtype=np.float32)

    def seek(self, position_ms: int) -> None:
        if not self._has_media:
            return  # sin media cargada: evitar llamadas fragiles a libVLC
        target = max(0, int(position_ms))
        length = self._player.get_length()
        if length and length > 0:
            target = min(target, int(length))
        applied = self._player.set_time(target)
        if self._analyzer is not None:
            with contextlib.suppress(Exception):
                self._analyzer.set_time(target)
        if applied is not None and applied >= 0:
            return
        # Fallback: posición relativa (0..1) cuando set_time no aplica.
        length = self._player.get_length()
        if length and length > 0:
            self._player.set_position(target / float(length))

    # --------------------------------------------------------------- velocidad
    def set_rate(self, rate: float) -> None:
        value = max(0.25, min(4.0, float(rate)))
        with contextlib.suppress(Exception):
            self._player.set_rate(value)
        if self._analyzer is not None:
            with contextlib.suppress(Exception):
                self._analyzer.set_rate(value)

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
            self._player.release()
        except Exception as exc:  # noqa: BLE001
            logger.debug("release: stop/release falló (%s)", exc)
        if self._analyzer is not None:
            with contextlib.suppress(Exception):
                self._analyzer.stop()
                self._analyzer.release()
            self._analyzer = None
            self._analyzer_cb = None
        try:
            self._instance.release()
        except Exception as exc:  # noqa: BLE001
            logger.debug("release: instance.release falló (%s)", exc)

    # ----------------------------------------------------------------- eventos
    def _on_end(self, _event: Any) -> None:
        # Este callback se ejecuta en el hilo de eventos de libVLC. Llamar
        # aquí a cualquier función de VLC (por ejemplo analyzer.stop()) es
        # reentrante y termina en SIGSEGV. Solo se avisa al reproductor; la
        # parada real ocurre en el hilo de UI al cargar o detener la pista.
        if self.on_finished is not None:
            self.on_finished()

    def _on_error_event(self, _event: Any) -> None:
        if self.on_error is not None:
            self.on_error("VLC informó un error al reproducir la pista")
