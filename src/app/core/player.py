from __future__ import annotations

import logging
import random
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from app.audio.base_backend import AudioBackend, BackendError
from app.audio.vlc_backend import VlcBackend
from app.library.metadata import MetadataError, extract_cover, read_metadata
from app.library.models import Track

from .playlist import PlaylistModel
from .settings import Settings, get_settings
from .signals import app_signals

logger = logging.getLogger(__name__)

STATE_PLAYING = "playing"
STATE_PAUSED = "paused"
STATE_STOPPED = "stopped"

#: Si el cursor está más allá de este umbral, "anterior" reinicia la pista
#: (comportamiento clásico de Winamp).
PREV_RESTART_THRESHOLD_MS = 3000
POLL_INTERVAL_MS = 250
#: Pequeña espera tras "fin de pista" antes de avanzar (VLC termina su
#: limpieza interna en su propio hilo).
AUTO_ADVANCE_DELAY_MS = 100

_MERGED_FIELDS = (
    "title",
    "artist",
    "album",
    "albumartist",
    "genre",
    "year",
    "track_no",
    "disc_no",
    "bitrate",
    "samplerate",
    "channels",
    "codec",
)


class Player(QObject):

    track_changed = Signal(object)
    playback_state_changed = Signal(str)
    position_changed = Signal(int)
    duration_changed = Signal(int)
    volume_changed = Signal(int)
    error_occurred = Signal(str)

    # Señales internas: marshaling desde el hilo de VLC al hilo de UI.
    _backend_finished = Signal()
    _backend_error = Signal(str)

    def __init__(
        self,
        backend: AudioBackend | None = None,
        playlist: PlaylistModel | None = None,
        settings: Settings | None = None,
    ) -> None:
        super().__init__()
        self._settings = settings if settings is not None else get_settings()
        self._playlist = playlist if playlist is not None else PlaylistModel()
        self._state = STATE_STOPPED
        self._duration = 0
        self._shuffle = bool(self._settings.shuffle)
        self._repeat = bool(self._settings.repeat)

        # NB: `_audio_error_msg` NO se llama `_backend_error` para no pisar
        # la señal Qt `_backend_error`.
        self._backend: AudioBackend | None
        self._audio_error_msg: str | None
        if backend is not None:
            self._backend = backend
            self._audio_error_msg = None
        else:
            try:
                self._backend = VlcBackend()
                self._audio_error_msg = None
            except BackendError as exc:
                self._backend = None
                self._audio_error_msg = str(exc)
                logger.error("Audio no disponible: %s", exc)

        if self._backend is not None:
            self._backend.on_finished = self._on_backend_finished
            self._backend.on_error = self._on_backend_error
            try:
                self._backend.set_volume(self._settings.volume)
                if self._settings.muted:
                    self._backend.set_muted(True)
            except Exception as exc:  # noqa: BLE001
                logger.warning("No se pudo aplicar volumen inicial: %s", exc)

        # El fin de pista llega del hilo de VLC: aquí solo emitimos y, desde
        # el hilo de UI, avanzamos con una espera mínima (nunca VLC en vivo).
        self._backend_finished.connect(self._schedule_auto_advance)
        self._backend_error.connect(self._handle_backend_error)

        # Reenvío al bus global (señal obligatoria del proyecto).
        self.track_changed.connect(app_signals.track_changed)

        self._timer = QTimer(self)
        self._timer.setInterval(POLL_INTERVAL_MS)
        self._timer.timeout.connect(self._poll)

    # ------------------------------------------------------------- propiedades
    @property
    def playlist(self) -> PlaylistModel:
        return self._playlist

    @property
    def state(self) -> str:
        return self._state

    @property
    def current_track(self) -> Track | None:
        return self._playlist.current()

    @property
    def is_available(self) -> bool:
        return self._backend is not None

    @property
    def backend_error(self) -> str | None:
        return self._audio_error_msg

    # ------------------------------------------------------- aleatorio/repetir
    @property
    def shuffle(self) -> bool:
        return self._shuffle

    @shuffle.setter
    def shuffle(self, value: bool) -> None:
        self._shuffle = bool(value)
        self._settings.shuffle = self._shuffle

    @property
    def repeat(self) -> bool:
        return self._repeat

    @repeat.setter
    def repeat(self, value: bool) -> None:
        self._repeat = bool(value)
        self._settings.repeat = self._repeat

    # ------------------------------------------------------------ de reproducción
    def add_paths(self, paths: list[str]) -> list[Track]:
        tracks = [Track(path=str(Path(p))) for p in paths if p]
        if tracks:
            self._playlist.add_many(tracks)
        return tracks

    def replace_playlist(self, tracks: list[Track], start_index: int = 0) -> bool:
        if not tracks:
            self.error_occurred.emit("replace_playlist: la lista está vacía")
            return False
        index = max(0, min(start_index, len(tracks) - 1))
        self._playlist.clear()
        self._playlist.add_many(tracks)
        return self.play_index(index)

    def play_stream(self, url: str, title: str = "", artist: str = "") -> bool:
        backend = self._backend
        if backend is None:
            self._emit_unavailable()
            return False
        track = Track(path=str(url), title=title or str(url), artist=artist or None)
        try:
            backend.load(str(url))
            backend.play()
        except BackendError as exc:
            logger.error("No se pudo reproducir el flujo %s: %s", url, exc)
            self.error_occurred.emit(str(exc))
            return False
        self._duration = 0
        self._set_state(STATE_PLAYING)
        self._timer.start()
        self.duration_changed.emit(0)
        self.track_changed.emit(track)
        self.playback_state_changed.emit(STATE_PLAYING)
        return True

    def load_playlist(self, path: str | Path) -> int:
        count = self._playlist.load_m3u(path)
        if count:
            self._select_without_playing(0)
        return count

    def save_playlist(self, path: str | Path) -> None:
        self._playlist.save_m3u(path)

    def play(self) -> None:
        if self._backend is None:
            self._emit_unavailable()
            return
        if self._state == STATE_PAUSED:
            self._backend.resume()
            self._set_state(STATE_PLAYING)
            self._timer.start()
            return
        if self._state == STATE_PLAYING:
            return
        # stopped
        index = self._playlist.current_index
        if index < 0 and len(self._playlist) > 0:
            index = 0
        if index < 0:
            self.error_occurred.emit("Playlist vacía: abre archivos o una carpeta")
            return
        self.play_index(index)

    def pause(self) -> None:
        if self._backend is None or self._state != STATE_PLAYING:
            return
        self._backend.pause()
        self._timer.stop()
        self._set_state(STATE_PAUSED)

    def stop(self) -> None:
        if self._backend is not None:
            try:
                self._backend.stop()
            except Exception as exc:  # noqa: BLE001
                logger.warning("stop falló: %s", exc)
        self._timer.stop()
        self._duration = 0
        self._set_state(STATE_STOPPED)
        self.position_changed.emit(0)
        self.duration_changed.emit(0)

    def toggle_pause(self) -> None:
        if self._state == STATE_PLAYING:
            self.pause()
        else:
            self.play()

    def play_index(self, index: int) -> bool:
        track = self._playlist.set_current(index)
        if track is None:
            self.error_occurred.emit(f"Pista fuera de rango: {index}")
            return False
        return self._start_track(track)

    def next(self) -> bool:
        index = self._advance_index()
        if index is None:
            logger.debug("next: ya estás en la última pista")
            return False
        return self.play_index(index)

    def prev(self) -> None:
        if self._state == STATE_PLAYING and self.position_ms() > PREV_RESTART_THRESHOLD_MS:
            self.seek(0)
            return
        index = self._playlist.prev_index()
        if index is None:
            self.seek(0)
            return
        self.play_index(index)

    def seek(self, position_ms: int) -> None:
        if self._backend is None:
            self._emit_unavailable()
            return
        self._backend.seek(max(0, int(position_ms)))
        self.position_changed.emit(max(0, int(position_ms)))

    # ------------------------------------------------------------------ volumen
    def set_volume(self, volume: int) -> None:
        clamped = max(0, min(100, int(volume)))
        self._settings.volume = clamped
        if self._backend is not None:
            self._backend.set_volume(clamped)
        self.volume_changed.emit(clamped)

    def set_muted(self, muted: bool) -> None:
        self._settings.muted = bool(muted)
        if self._backend is not None:
            self._backend.set_muted(bool(muted))

    def toggle_mute(self) -> bool:
        target = not self.is_muted()
        self.set_muted(target)
        return target

    def is_muted(self) -> bool:
        if self._backend is None:
            return self._settings.muted
        return self._backend.is_muted()

    # ------------------------------------------------------------------ estado
    def position_ms(self) -> int:
        if self._backend is None:
            return 0
        return self._backend.position_ms()

    def duration_ms(self) -> int:
        if self._backend is None:
            return 0
        return self._backend.duration_ms()

    def shutdown(self) -> None:
        self._timer.stop()
        if self._backend is not None:
            self._backend.release()
            self._backend = None
        self._state = STATE_STOPPED
        logger.info("Player apagado")

    # ----------------------------------------------------------------- privadas
    def _start_track(self, track: Track) -> bool:
        backend = self._backend
        if backend is None:
            self._emit_unavailable()
            return False

        self._merge_metadata(track)
        try:
            backend.load(track.path)
            backend.play()
        except BackendError as exc:
            logger.error("No se pudo reproducir %s: %s", track.path, exc)
            self.error_occurred.emit(str(exc))
            return False

        self._duration = 0
        self._set_state(STATE_PLAYING)
        self._timer.start()
        # Orden: primero track_changed (el Notifier reacciona), luego estado.
        self.track_changed.emit(track)
        self.playback_state_changed.emit(STATE_PLAYING)
        return True

    def _merge_metadata(self, track: Track) -> None:
        try:
            info = read_metadata(track.path)
        except MetadataError as exc:
            logger.warning("Metadatos: %s", exc)
            info = None
        except Exception as exc:  # noqa: BLE001 - archivo corrupto u otro fallo
            logger.warning("Metadatos ilegibles para %s: %s", track.path, exc)
            info = None

        if info is not None:
            for field in _MERGED_FIELDS:
                value = getattr(info, field)
                if value is not None:
                    setattr(track, field, value)
            if info.duration_ms > 0:
                track.duration_ms = info.duration_ms

        if track.cover_path is None:
            try:
                track.cover_path = extract_cover(track.path)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Sin carátula para %s: %s", track.path, exc)

    def _set_state(self, state: str) -> None:
        if state != self._state:
            self._state = state
            self.playback_state_changed.emit(state)

    def _poll(self) -> None:
        backend = self._backend
        if backend is None or self._state != STATE_PLAYING:
            self._timer.stop()
            return
        self.position_changed.emit(backend.position_ms())
        duration = backend.duration_ms()
        if duration != self._duration:
            self._duration = duration
            self.duration_changed.emit(duration)

    def _on_backend_finished(self) -> None:
        self._backend_finished.emit()

    def _on_backend_error(self, message: str) -> None:
        self._backend_error.emit(message)

    def _schedule_auto_advance(self) -> None:
        QTimer.singleShot(AUTO_ADVANCE_DELAY_MS, self._auto_advance)

    def _auto_advance(self) -> None:
        index = self._advance_index()
        if index is None:
            logger.info("Fin de la playlist")
            self.stop()
            return
        self.play_index(index)

    def _advance_index(self) -> int | None:
        size = len(self._playlist)
        if size == 0:
            return None
        current = self._playlist.current_index
        if self._shuffle and size > 1:
            # Cualquier índice salvo el actual (sin repetir la misma).
            choice = random.randrange(size - 1)
            return choice if choice < current else choice + 1
        candidate = self._playlist.next_index()
        if candidate is not None:
            return candidate
        return 0 if self._repeat else None

    def _handle_backend_error(self, message: str) -> None:
        logger.error("Backend: %s", message)
        self.error_occurred.emit(message)

    def _select_without_playing(self, index: int) -> None:
        self._playlist.set_current(index)

    def _emit_unavailable(self) -> None:
        message = self._audio_error_msg or "Backend de audio no disponible"
        logger.error(message)
        self.error_occurred.emit(message)
