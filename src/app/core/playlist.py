"""Modelo de playlist en memoria + lectura/escritura de ``.m3u``.

Lista simple de :class:`app.library.models.Track` con índice actual.
No es un QObject: los cambios los refluye la UI (o el player) — aquí no hay
lógica de presentación. La persistencia en SQLite llega en la Fase 2.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from pathlib import Path

from app.library.models import Track

logger = logging.getLogger(__name__)

#: Extensiones que PyAmp reconoce como audio.
AUDIO_EXTENSIONS = frozenset(
    {".mp3", ".flac", ".ogg", ".oga", ".opus", ".m4a", ".aac", ".wav", ".aiff", ".aif", ".wma"}
)

M3U_HEADER = "#EXTM3U"


def audio_filter_string() -> str:
    """Filtro de diálogos de archivo, p. ej. ``*.mp3 *.flac ...``."""
    return " ".join(f"*{ext}" for ext in sorted(AUDIO_EXTENSIONS))


def collect_audio_files(folder: str | Path, recursive: bool = True) -> list[str]:
    """Devuelve las rutas de audio de una carpeta, ordenadas.

    Función pura (sin Qt): el hilo que la llame puede ser un QThread para
    no bloquear la UI (RNF: la interfaz nunca se bloquea).

    Args:
        folder: Carpeta a recorrer.
        recursive: Si es True recorre subcarpetas (por defecto).

    Returns:
        Lista de rutas absolutas ordenadas alfabéticamente (ignorando mayúsculas).
    """
    root = Path(folder).expanduser()
    if not root.is_dir():
        logger.warning("Carpeta no válida: %s", folder)
        return []
    candidates = root.rglob("*") if recursive else root.iterdir()
    files = [
        str(path.resolve())
        for path in candidates
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    ]
    return sorted(files, key=str.casefold)


class PlaylistModel:
    """Playlist en memoria con índice de pista actual.

    Args:
        tracks: Pistas iniciales (opcional).
    """

    def __init__(self, tracks: Iterable[Track] | None = None) -> None:
        self.tracks: list[Track] = list(tracks) if tracks else []
        self.current_index: int = -1 if not self.tracks else 0

    # ------------------------------------------------------------- básicas
    def __len__(self) -> int:
        return len(self.tracks)

    def __iter__(self) -> Iterator[Track]:
        return iter(self.tracks)

    def __getitem__(self, index: int) -> Track:
        return self.tracks[index]

    def add(self, track: Track) -> int:
        """Añade una pista al final y devuelve su índice."""
        self.tracks.append(track)
        if len(self.tracks) == 1:
            self.current_index = 0
        return len(self.tracks) - 1

    def add_many(self, tracks: Iterable[Track]) -> int:
        """Añade varias pistas; devuelve el índice de la primera añadida."""
        first = len(self.tracks)
        self.tracks.extend(tracks)
        if first == 0 and self.tracks:
            self.current_index = 0
        return first

    def remove_at(self, index: int) -> bool:
        """Elimina la pista en ``index``; reajusta el índice actual.

        Returns:
            True si se eliminó.
        """
        if not 0 <= index < len(self.tracks):
            return False
        del self.tracks[index]
        if not self.tracks:
            self.current_index = -1
        elif self.current_index > index:
            self.current_index -= 1
        elif self.current_index == index:
            self.current_index = min(index, len(self.tracks) - 1)
        return True

    def clear(self) -> None:
        """Vacía la playlist."""
        self.tracks.clear()
        self.current_index = -1

    # -------------------------------------------------------------- índice
    def current(self) -> Track | None:
        """Pista actual o None si la lista está vacía."""
        if 0 <= self.current_index < len(self.tracks):
            return self.tracks[self.current_index]
        return None

    def set_current(self, index: int) -> Track | None:
        """Fija el índice actual sin reproducir (mejor esfuerzo).

        Returns:
            La pista resultante o None si el índice está fuera de rango.
        """
        if 0 <= index < len(self.tracks):
            self.current_index = index
            return self.tracks[self.current_index]
        return None

    def next_index(self) -> int | None:
        """Índice de la siguiente pista secuencial, o None si es la última."""
        candidate = self.current_index + 1
        if 0 <= candidate < len(self.tracks):
            return candidate
        return None

    def prev_index(self) -> int | None:
        """Índice de la pista anterior, o None si es la primera."""
        candidate = self.current_index - 1
        if 0 <= candidate < len(self.tracks):
            return candidate
        return None

    def index_of_path(self, path: str) -> int:
        """Índice de la primera pista con ese path (-1 si no está)."""
        for index, track in enumerate(self.tracks):
            if track.path == path:
                return index
        return -1

    # ---------------------------------------------------------------- .m3u
    def save_m3u(self, path: str | Path) -> None:
        """Guarda la playlist como M3U extendido (``#EXTM3U``).

        Args:
            path: Archivo destino (se sobrescribe).

        Raises:
            OSError: Si no se puede escribir el archivo.
        """
        target = Path(path).expanduser()
        lines = [M3U_HEADER]
        for track in self.tracks:
            seconds = max(0, track.duration_ms // 1000)
            label = track.display_name
            lines.append(f"#EXTINF:{seconds},{label}")
            lines.append(track.path)
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.info("Playlist guardada en %s (%d pistas)", target, len(self.tracks))

    def load_m3u(self, path: str | Path) -> int:
        """Carga un ``.m3u``/``.m3u8`` reemplazando el contenido actual.

        Soporta M3U extendido (``#EXTINF:duración,Título``) y M3U simple.
        Las rutas relativas se resuelven contra la carpeta del archivo.

        Returns:
            Número de pistas cargadas (las que no existen se omiten).

        Raises:
            OSError: Si no se puede leer el archivo.
        """
        source = Path(path).expanduser()
        base_dir = source.parent
        raw_lines = source.read_text(encoding="utf-8", errors="replace").splitlines()

        parsed: list[Track] = []
        pending_duration = 0
        pending_title: str | None = None
        for line in raw_lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#EXTINF:"):
                info = line[len("#EXTINF:") :]
                duration_text, _, label = info.partition(",")
                try:
                    pending_duration = max(0, int(float(duration_text))) * 1000
                except ValueError:
                    pending_duration = 0
                pending_title = label.strip() or None
                continue
            if line.startswith("#"):
                continue
            candidate = Path(line)
            if not candidate.is_absolute():
                candidate = base_dir / candidate
            if not candidate.is_file():
                logger.warning("M3U: pista no encontrada, omitida: %s", line)
                continue
            title = pending_title
            artist: str | None = None
            if title and " - " in title:
                artist, _, title = title.partition(" - ")
                artist = artist.strip() or None
                title = title.strip() or None
            parsed.append(
                Track(
                    path=str(candidate.resolve()),
                    title=title,
                    artist=artist,
                    duration_ms=pending_duration,
                )
            )
            pending_duration = 0
            pending_title = None

        self.tracks = parsed
        self.current_index = 0 if parsed else -1
        logger.info("Playlist cargada desde %s (%d pistas)", source, len(parsed))
        return len(parsed)
