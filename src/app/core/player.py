"""Fachada del reproductor de PyAmp.

Único punto del programa que orquesta la reproducción. La UI jamás habla
con VLC: llama a estos métodos y escucha estas señales.

Señales (nombradas en pasado):

* ``track_changed(track)`` — **SEÑAL GLOBAL OBLIGATORIA**: se emite SOLO
  cuando cambia la pista actual (next, prev, salto en playlist, arranque
  desde cero tras stop). NUNCA en pausa/reanudación de la misma pista.
  El Notifier se suscribe a ella: es la única fuente de notificaciones.
* ``playback_state_changed(state)`` — "playing" | "paused" | "stopped".
* ``position_changed(ms)`` / ``duration_changed(ms)`` / ``volume_changed(v)``.
* ``error_occurred(message)`` — errores no fatales (archivo corrupto,
  libVLC ausente...); la app nunca crashea.

Además reenvía ``track_changed`` al bus global :data:`app_signals` para
componentes sin referencia directa al player (biblioteca, MPRIS, ...).
"""

from __future__ import annotations

import logging
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
)


class Player(QObject):
    """Fachada de reproducción con señales Qt.

    Args:
        backend: Backend inyectable (para tests); si es None crea VlcBackend.
        playlist: Playlist inyectable; si es None crea una vacía.
        settings: Ajustes inyectables; si es None usa el singleton.
    """

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
        """Playlist en memoria compartida con la UI."""
        return self._playlist

    @property
    def state(self) -> str:
        """Estado actual: "playing" | "paused" | "stopped"."""
        return self._state

    @property
    def current_track(self) -> Track | None:
        """Pista actual (None si la playlist está vacía)."""
        return self._playlist.current()

    @property
    def is_available(self) -> bool:
        """True si hay backend de audio operativo."""
        return self._backend is not None

    @property
    def backend_error(self) -> str | None:
        """Mensaje del fallo de backend (None si está operativo)."""
        return self._audio_error_msg

    # ------------------------------------------------------------ de reproducción
    def add_paths(self, paths: list[str]) -> list[Track]:
        """Añade archivos a la playlist (sin reproducir aún).

        Args:
            paths: Rutas de archivo.

        Returns:
            Los Track creados (con metadatos perezosos: solo path).
        """
        tracks = [Track(path=str(Path(p))) for p in paths if p]
        if tracks:
            self._playlist.add_many(tracks)
        return tracks

    def replace_playlist(self, tracks: list[Track], start_index: int = 0) -> bool:
        """Reemplaza la playlist y reproduce ``tracks[start_index]``.

        Lo usa la biblioteca (Fase 3): doble clic → el contexto visible
        (álbum completo o resultados de búsqueda) pasa a ser la playlist y
        suena la pista elegida; el auto-avance continúa en ese contexto.

        Args:
            tracks: Nuevas pistas (pueden venir de la BD, metadatos ya
                leídos).
            start_index: Índice a reproducir (recortado al rango válido).

        Returns:
            True si empezó a reproducir.
        """
        if not tracks:
            self.error_occurred.emit("replace_playlist: la lista está vacía")
            return False
        index = max(0, min(start_index, len(tracks) - 1))
        self._playlist.clear()
        self._playlist.add_many(tracks)
        return self.play_index(index)

    def load_playlist(self, path: str | Path) -> int:
        """Reemplaza la playlist con un ``.m3u`` y selecciona la primera pista.

        Returns:
            Número de pistas cargadas.

        Raises:
            OSError: Si el archivo no se puede leer.
        """
        count = self._playlist.load_m3u(path)
        if count:
            self._select_without_playing(0)
        return count

    def save_playlist(self, path: str | Path) -> None:
        """Guarda la playlist como ``.m3u``.

        Raises:
            OSError: Si no se puede escribir.
        """
        self._playlist.save_m3u(path)

    def play(self) -> None:
        """Reproduce: reanuda si está en pausa, arranca desde cero si parado.

        El arranque desde cero de la misma pista SÍ emite ``track_changed``
        (regla del proyecto: "inicio desde cero" notifica); pausar y
        reanudar NO.
        """
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
        """Pausa la reproducción (NO emite ``track_changed``)."""
        if self._backend is None or self._state != STATE_PLAYING:
            return
        self._backend.pause()
        self._timer.stop()
        self._set_state(STATE_PAUSED)

    def stop(self) -> None:
        """Detiene la reproducción y deja el cursor al inicio."""
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
        """Conmuta entre pausar y reanudar (para el botón ▶/⏸)."""
        if self._state == STATE_PLAYING:
            self.pause()
        else:
            self.play()

    def play_index(self, index: int) -> bool:
        """Carga y reproduce la pista en ``index`` (emite ``track_changed``).

        Returns:
            True si empezó a reproducir.
        """
        track = self._playlist.set_current(index)
        if track is None:
            self.error_occurred.emit(f"Pista fuera de rango: {index}")
            return False
        return self._start_track(track)

    def next(self) -> bool:
        """Salta a la siguiente pista. En la última, no hace nada."""
        index = self._playlist.next_index()
        if index is None:
            logger.debug("next: ya estás en la última pista")
            return False
        return self.play_index(index)

    def prev(self) -> None:
        """Pista anterior; si lleva >3 s sonando, reinicia la actual (Winamp)."""
        if self._state == STATE_PLAYING and self.position_ms() > PREV_RESTART_THRESHOLD_MS:
            self.seek(0)
            return
        index = self._playlist.prev_index()
        if index is None:
            self.seek(0)
            return
        self.play_index(index)

    def seek(self, position_ms: int) -> None:
        """Mueve el cursor de reproducción.

        Args:
            position_ms: Posición en milisegundos.
        """
        if self._backend is None:
            self._emit_unavailable()
            return
        self._backend.seek(max(0, int(position_ms)))
        self.position_changed.emit(max(0, int(position_ms)))

    # ------------------------------------------------------------------ volumen
    def set_volume(self, volume: int) -> None:
        """Fija el volumen 0..100, lo persiste y emite ``volume_changed``."""
        clamped = max(0, min(100, int(volume)))
        self._settings.volume = clamped
        if self._backend is not None:
            self._backend.set_volume(clamped)
        self.volume_changed.emit(clamped)

    def set_muted(self, muted: bool) -> None:
        """Silencia o restablece el audio y lo persiste."""
        self._settings.muted = bool(muted)
        if self._backend is not None:
            self._backend.set_muted(bool(muted))

    def toggle_mute(self) -> bool:
        """Conmuta el silencio.

        Returns:
            True si quedó silenciado.
        """
        target = not self.is_muted()
        self.set_muted(target)
        return target

    def is_muted(self) -> bool:
        """True si el audio está silenciado."""
        if self._backend is None:
            return self._settings.muted
        return self._backend.is_muted()

    # ------------------------------------------------------------------ estado
    def position_ms(self) -> int:
        """Posición actual en milisegundos."""
        if self._backend is None:
            return 0
        return self._backend.position_ms()

    def duration_ms(self) -> int:
        """Duración conocida en milisegundos."""
        if self._backend is None:
            return 0
        return self._backend.duration_ms()

    def shutdown(self) -> None:
        """Para todo y libera el backend (llamar al cerrar la ventana)."""
        self._timer.stop()
        if self._backend is not None:
            self._backend.release()
            self._backend = None
        self._state = STATE_STOPPED
        logger.info("Player apagado")

    # ----------------------------------------------------------------- privadas
    def _start_track(self, track: Track) -> bool:
        """Carga metadatos, arranca la pista y emite las señales de cambio.

        Returns:
            True si la reproducción empezó.
        """
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
        """Completa la pista con metadatos (mutagen) y carátula, sin fallar.

        Los valores del archivo mandan sobre los del .m3u; lo que no esté en
        el archivo se conserva. Cualquier error se registra y la pista sigue
        reproducible con el nombre de archivo (RNF: sin crashes).
        """
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
        """Refresa posición/duración mientras suena (timer de UI)."""
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
        """Fin de pista detectado (HILO DE VLC): solo emitimos la señal."""
        self._backend_finished.emit()

    def _on_backend_error(self, message: str) -> None:
        """Error de VLC detectado (HILO DE VLC): solo emitimos la señal."""
        self._backend_error.emit(message)

    def _schedule_auto_advance(self) -> None:
        """Avanza a la siguiente pista desde el hilo de UI, con pequeña espera."""
        QTimer.singleShot(AUTO_ADVANCE_DELAY_MS, self._auto_advance)

    def _auto_advance(self) -> None:
        index = self._playlist.next_index()
        if index is None:
            logger.info("Fin de la playlist")
            self.stop()
            return
        self.play_index(index)

    def _handle_backend_error(self, message: str) -> None:
        logger.error("Backend: %s", message)
        self.error_occurred.emit(message)

    def _select_without_playing(self, index: int) -> None:
        """Selecciona una pista sin reproducirla (al cargar una playlist)."""
        self._playlist.set_current(index)

    def _emit_unavailable(self) -> None:
        message = self._audio_error_msg or "Backend de audio no disponible"
        logger.error(message)
        self.error_occurred.emit(message)
