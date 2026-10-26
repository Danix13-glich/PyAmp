from __future__ import annotations

import json
import logging
import re
import unicodedata
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.library.models import Track
from app.utils.paths import LYRICS_DIR

logger = logging.getLogger(__name__)

#: API pública de LRCLIB (sin clave ni registro). Devuelve letras sincronizadas
#: y planas junto a la duración real de cada resultado.
LRCLIB_SEARCH_URL = "https://lrclib.net/api/search"
USER_AGENT = "PyAmp/0.2.1 (+https://github.com/Danix13-glich/PyAmp)"
REQUEST_TIMEOUT_S = 7
#: Margen máximo entre la duración del archivo y la del resultado online.
DURATION_TOLERANCE_MS = 3000

_ARTIST_SEPARATORS = re.compile(
    r"\s*(?:,|;|/|&|\bfeat\.?\b|\bft\.?\b|\bx\b)\s*",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class OnlineLyrics:

    track_name: str
    artist_name: str
    duration_s: float
    synced: str
    plain: str

    @property
    def text(self) -> str:
        return self.synced.strip() or self.plain.strip()


def normalize_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(text))
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    cleaned = re.sub(r"[^0-9a-zA-Z]+", " ", without_marks.casefold())
    return " ".join(cleaned.split())


def _artist_parts(artist: str) -> list[str]:
    parts = [normalize_text(part) for part in _ARTIST_SEPARATORS.split(artist)]
    result = [part for part in parts if len(part) >= 2]
    full = normalize_text(artist)
    if len(full) >= 2 and full not in result:
        result.append(full)
    return result


def artist_matches(track_artist: str | None, candidate_artist: str) -> bool:
    # Se exige coincidencia de artista: sin este dato no se acepta la letra.
    if not track_artist or not str(track_artist).strip():
        return False
    candidate = normalize_text(candidate_artist)
    if not candidate:
        return False
    for part in _artist_parts(str(track_artist)):
        if part == candidate or part in candidate or candidate in part:
            return True
    return False


def title_matches(track_title: str | None, candidate_name: str) -> bool:
    title = normalize_text(track_title or "")
    name = normalize_text(candidate_name)
    if len(title) < 2 or len(name) < 2:
        return False
    return title in name or name in title


def duration_matches(duration_ms: int, candidate_s: float) -> bool:
    if duration_ms <= 0 or candidate_s <= 0:
        return False
    return abs(int(candidate_s * 1000) - int(duration_ms)) <= DURATION_TOLERANCE_MS


def _parse_candidate(item: object) -> OnlineLyrics | None:
    if not isinstance(item, dict):
        return None
    track_name = str(item.get("trackName") or "").strip()
    artist_name = str(item.get("artistName") or "").strip()
    try:
        duration_s = float(item.get("duration") or 0)
    except (TypeError, ValueError):
        return None
    synced = str(item.get("syncedLyrics") or "").strip()
    plain = str(item.get("plainLyrics") or "").strip()
    if not track_name or not artist_name or not (synced or plain):
        return None
    return OnlineLyrics(track_name, artist_name, duration_s, synced, plain)


def select_lyrics(
    track_title: str,
    track_artist: str | None,
    duration_ms: int,
    candidates: list[OnlineLyrics],
) -> OnlineLyrics | None:
    best: OnlineLyrics | None = None
    best_key: tuple[int, int] | None = None
    for candidate in candidates:
        if not duration_matches(duration_ms, candidate.duration_s):
            continue
        if not artist_matches(track_artist, candidate.artist_name):
            continue
        if not title_matches(track_title, candidate.track_name):
            continue
        difference = abs(int(candidate.duration_s * 1000) - int(duration_ms))
        # Preferir letra sincronizada; a igualdad, la duración más cercana.
        key = (0 if candidate.synced else 1, difference)
        if best_key is None or key < best_key:
            best = candidate
            best_key = key
    return best


def _search_candidates(
    track_title: str, artist: str, timeout_s: int = REQUEST_TIMEOUT_S
) -> list[OnlineLyrics]:
    params = urllib.parse.urlencode({"track_name": track_title, "artist_name": artist})
    request = urllib.request.Request(
        f"{LRCLIB_SEARCH_URL}?{params}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    if not isinstance(payload, list):
        return []
    results: list[OnlineLyrics] = []
    for item in payload:
        candidate = _parse_candidate(item)
        if candidate is not None:
            results.append(candidate)
    return results


def search_lyrics(track: Track, timeout_s: int = REQUEST_TIMEOUT_S) -> OnlineLyrics | None:
    if not track.path or "://" in track.path:
        return None
    title = (track.title or Path(track.path).stem).strip()
    artist = (track.artist or "").strip()
    if not title or not artist:
        return None

    candidates = _search_candidates(title, artist, timeout_s)
    selected = select_lyrics(title, artist, track.duration_ms, candidates)
    if selected is not None:
        return selected

    # Si el tag trae varios artistas, LRCLIB puede no encontrar nada con la
    # cadena completa; se reintenta con el primero.
    parts = [part.strip() for part in _ARTIST_SEPARATORS.split(artist) if part.strip()]
    if len(parts) > 1:
        candidates = _search_candidates(title, parts[0], timeout_s)
        return select_lyrics(title, artist, track.duration_ms, candidates)
    return None


def target_path(track: Track) -> Path:
    return LYRICS_DIR / f"{Path(track.path).stem}.lrc"


def save_lyrics(track: Track, lyrics: OnlineLyrics, *, destination: Path | None = None) -> Path:
    path = destination or target_path(track)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(lyrics.text + "\n", encoding="utf-8")
    return path


def fetch_lyrics(track: Track, *, force: bool = False) -> Path | None:
    if not track.path or "://" in track.path:
        return None
    sidecar = Path(track.path).with_suffix(".lrc")
    target = target_path(track)
    if not force:
        if sidecar.is_file():
            return sidecar
        if target.is_file():
            return target
    lyrics = search_lyrics(track)
    if lyrics is None:
        return None
    # Si el usuario pide buscar y ya había un .lrc vacío, se rellena ese mismo
    # archivo; si no, se guarda en la carpeta de letras de PyAmp.
    destination = target
    if force and sidecar.is_file():
        try:
            if not sidecar.read_text(encoding="utf-8", errors="replace").strip():
                destination = sidecar
        except OSError:
            pass
    return save_lyrics(track, lyrics, destination=destination)


class OnlineLyricsWorker(QThread):
    #: (ruta de la pista, ruta del .lrc guardado)
    found = Signal(str, str)
    #: Ruta de la pista para la que no se encontró una letra válida.
    missing = Signal(str)

    def __init__(self, track: Track, parent: object | None = None, *, force: bool = False) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self._track = track
        self._force = force

    @property
    def track_path(self) -> str:
        return self._track.path

    def run(self) -> None:
        try:
            path = fetch_lyrics(self._track, force=self._force)
        except Exception as exc:  # noqa: BLE001 - la red nunca debe romper nada
            logger.info("Búsqueda de letra online falló para %s: %s", self._track.path, exc)
            self.missing.emit(self._track.path)
            return
        if path is None:
            self.missing.emit(self._track.path)
        else:
            logger.info("Letra online encontrada para %s: %s", self._track.path, path)
            self.found.emit(self._track.path, str(path))
