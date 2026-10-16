"""Modelos de datos de PyAmp.

En la Fase 1 solo vive :class:`Track`, el modelo de pista usado por la
playlist, el player y las notificaciones. La Fase 2 amplía este módulo con
``Album``, ``Artist``, ``Playlist`` y ``RadioStation`` para la biblioteca
(SQLite).

Regla del proyecto: este dataclass es un DTO puro — sin Qt, sin VLC, sin
SQLite. La UI y el player lo consumen; la capa de persistencia lo
serializa.
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
    con mutagen en el momento en que la pista empieza a sonar, nunca en
    masa al abrir la UI (RNF: la UI nunca se bloquea).
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
    cover_path: str | None = None
    # Gestión de BD (la rellena la Fase 2; aquí queda preparado).
    id: int | None = None
    play_count: int = 0
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
