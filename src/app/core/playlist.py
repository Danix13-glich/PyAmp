from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from pathlib import Path

from app.library.metadata import AUDIO_EXTENSIONS
from app.library.models import Track

logger = logging.getLogger(__name__)

# AUDIO_EXTENSIONS vive ahora en app.library.metadata (fuente única);
# se reimporta aquí por compatibilidad con los llamantes antiguos.

M3U_HEADER = "#EXTM3U"


def read_m3u_paths(path: str | Path) -> list[str]:
    """Rutas de un M3U, sin exigir que los archivos existan."""
    source = Path(path).expanduser()
    base_dir = source.parent
    result: list[str] = []
    seen: set[str] = set()
    for line in source.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        candidate = Path(text)
        if not candidate.is_absolute():
            candidate = base_dir / candidate
        try:
            resolved = str(candidate.resolve())
        except OSError:
            resolved = str(candidate)
        if resolved not in seen:
            seen.add(resolved)
            result.append(resolved)
    return result


def audio_filter_string() -> str:
    return " ".join(f"*{ext}" for ext in sorted(AUDIO_EXTENSIONS))


def collect_audio_files(folder: str | Path, recursive: bool = True) -> list[str]:
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
        self.tracks.append(track)
        if len(self.tracks) == 1:
            self.current_index = 0
        return len(self.tracks) - 1

    def add_many(self, tracks: Iterable[Track]) -> int:
        first = len(self.tracks)
        self.tracks.extend(tracks)
        if first == 0 and self.tracks:
            self.current_index = 0
        return first

    def remove_at(self, index: int) -> bool:
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
        self.tracks.clear()
        self.current_index = -1

    # -------------------------------------------------------------- índice
    def current(self) -> Track | None:
        if 0 <= self.current_index < len(self.tracks):
            return self.tracks[self.current_index]
        return None

    def set_current(self, index: int) -> Track | None:
        if 0 <= index < len(self.tracks):
            self.current_index = index
            return self.tracks[self.current_index]
        return None

    def next_index(self) -> int | None:
        candidate = self.current_index + 1
        if 0 <= candidate < len(self.tracks):
            return candidate
        return None

    def prev_index(self) -> int | None:
        candidate = self.current_index - 1
        if 0 <= candidate < len(self.tracks):
            return candidate
        return None

    def index_of_path(self, path: str) -> int:
        for index, track in enumerate(self.tracks):
            if track.path == path:
                return index
        return -1

    def rename_path(self, old_path: str, new_path: str) -> int:
        changed = 0
        for track in self.tracks:
            if track.path == old_path:
                track.path = new_path
                changed += 1
        return changed

    # ---------------------------------------------------------------- .m3u
    def save_m3u(self, path: str | Path) -> None:
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
