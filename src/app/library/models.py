"""Modelos de datos de PyAmp.

Viven los DTOs de la biblioteca: :class:`Track` (la pista, usada por la
playlist, el player, las notificaciones y la BD), y desde la Fase 2
también :class:`Artist`, :class:`Album` y :class:`Playlist`.

Regla del proyecto: son dataclasses puras — sin Qt, sin VLC, sin SQLite.
La UI y el player los consumen; la capa de persistencia (``database.py``)
los serializa. ``RadioStation`` llega en la Fase 6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Literales de presentación. Notifier mantiene su propia copia (formato de
# notificación autocontenido en Fase 0); si cambian, cambiarlos en ambos.
UNKNOWN_ARTIST_TEXT = "Artista desconocido"
UNKNOWN_TITLE_TEXT = "Sin título"


@dataclass
class Track:
    """Pista de audio (archivo local o entrada de playlist).

    Todos los campos son opcionales salvo ``path``: los metadatos se leen
    con mutagen (en el player al sonar, o en el escáner de la biblioteca).
    Los campos de gestión (``file_size``/``file_mtime``/``added_at``/...)
    los rellena la biblioteca de la Fase 2.
    """

    path: str = ""
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    albumartist: str | None = None
    genre: str | None = None
    year: str | None = None
    duration_ms: int = 0
    track_no: int | None = None
    disc_no: int | None = None
    bitrate: int | None = None
    samplerate: int | None = None
    channels: int | None = None
    #: Códec detectado por mutagen en la cabecera real («MPEG-1 layer 3»,
    #: «FLAC», «WAV»…); None mientras no se haya leído el archivo.
    codec: str | None = None
    cover_path: str | None = None
    # Gestión de archivo/BD (Fase 2).
    file_size: int | None = None
    file_mtime: int | None = None
    added_at: str | None = None
    last_played_at: str | None = None
    id: int | None = None
    play_count: int = 0
    #: Favorito marcado por el usuario (Fase 4; columna BD `is_favorite`).
    is_favorite: bool = False
    # Campos extra que pueda aportar un .m3u (no persisten en BD).
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def filename_stem(self) -> str:
        """Nombre del archivo sin extensión (o cadena vacía si no hay path)."""
        if not self.path:
            return ""
        return Path(self.path).stem

    @property
    def display_title(self) -> str:
        """Título para mostrar: etiqueta real o, en su defecto, el archivo."""
        if self.title:
            return str(self.title)
        return self.filename_stem or UNKNOWN_TITLE_TEXT

    @property
    def display_artist(self) -> str:
        """Artista para mostrar o 'Artista desconocido'."""
        if self.artist and str(self.artist).strip():
            return str(self.artist)
        return UNKNOWN_ARTIST_TEXT

    @property
    def display_name(self) -> str:
        """Texto de fila de playlist: 'Título — Artista'."""
        return f"{self.display_title} — {self.display_artist}"


@dataclass
class Artist:
    """Artista de la biblioteca (tabla ``artists``)."""

    id: int | None = None
    name: str = ""
    track_count: int = 0

    @property
    def display_name(self) -> str:
        """Nombre o 'Artista desconocido'."""
        if self.name and self.name.strip():
            return self.name
        return UNKNOWN_ARTIST_TEXT


@dataclass
class Album:
    """Álbum de la biblioteca (tabla ``albums``)."""

    id: int | None = None
    title: str = ""
    artist_id: int | None = None
    artist_name: str | None = None
    year: str | None = None
    cover_path: str | None = None
    track_count: int = 0


@dataclass
class Playlist:
    """Playlist persistida en la biblioteca (tablas ``playlists``).

    La Fase 1 ya guarda/carga ``.m3u``; este modelo corresponde a las
    playlists con nombre guardadas en SQLite (complementarias).
    """

    id: int | None = None
    name: str = ""
    created_at: str | None = None
    track_count: int = 0
    tracks: list[Track] = field(default_factory=list)
