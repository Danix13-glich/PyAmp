from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Literales de presentación. Notifier mantiene su propia copia (formato de
# notificación autocontenido); si cambian, cambiarlos en ambos.
from app.i18n import tr

UNKNOWN_ARTIST_TEXT = "Artista desconocido"
UNKNOWN_TITLE_TEXT = "Sin título"


@dataclass
class Track:

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
    # Gestión de archivo/BD.
    file_size: int | None = None
    file_mtime: int | None = None
    added_at: str | None = None
    last_played_at: str | None = None
    id: int | None = None
    play_count: int = 0
    #: Favorito marcado por el usuario (columna BD `is_favorite`).
    is_favorite: bool = False
    #: Oculto por el usuario (columna BD `is_hidden`).
    is_hidden: bool = False
    # Campos extra que pueda aportar un .m3u (no persisten en BD).
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def filename_stem(self) -> str:
        if not self.path:
            return ""
        return Path(self.path).stem

    @property
    def display_title(self) -> str:
        if self.title:
            return str(self.title)
        return self.filename_stem or tr(UNKNOWN_TITLE_TEXT)

    @property
    def display_artist(self) -> str:
        if self.artist and str(self.artist).strip():
            return str(self.artist)
        return tr(UNKNOWN_ARTIST_TEXT)

    @property
    def display_name(self) -> str:
        return f"{self.display_title} — {self.display_artist}"


@dataclass
class Artist:

    id: int | None = None
    name: str = ""
    track_count: int = 0

    @property
    def display_name(self) -> str:
        if self.name and self.name.strip():
            return self.name
        return tr(UNKNOWN_ARTIST_TEXT)


@dataclass
class Album:

    id: int | None = None
    title: str = ""
    artist_id: int | None = None
    artist_name: str | None = None
    year: str | None = None
    cover_path: str | None = None
    track_count: int = 0


@dataclass
class Playlist:

    id: int | None = None
    name: str = ""
    created_at: str | None = None
    track_count: int = 0
    tracks: list[Track] = field(default_factory=list)


@dataclass(frozen=True)
class RadioStation:

    name: str
    url: str
    genre: str = ""
    country: str = ""
    builtin: bool = False

    def matches(self, term: str) -> bool:
        text = term.strip().casefold()
        if not text:
            return True
        return (
            text in self.name.casefold()
            or text in self.genre.casefold()
            or text in self.country.casefold()
        )
