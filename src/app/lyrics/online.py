from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
import urllib.error
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
USER_AGENT = "PyAmp/0.2.4 (+https://github.com/Danix13-glich/PyAmp)"
REQUEST_TIMEOUT_S = 8
REQUEST_RETRIES = 2
RETRY_DELAY_S = 0.6
#: Margen máximo entre la duración del archivo y la del resultado online.
DURATION_TOLERANCE_MS = 3000
#: Segundo intento más flexible para grabaciones con intro/silencio distinto.
RELAXED_DURATION_TOLERANCE_MS = 15000

_ARTIST_SEPARATORS = re.compile(
    r"\s*(?:,|;|/|&|\bfeat\.?\b|\bft\.?\b|\bx\b)\s*",
    re.IGNORECASE,
)
#: Marcas de tiempo LRC: ``[mm:ss]``, ``[mm:ss.xx]`` o ``[mm:ss.xxx]``.
LRC_TIMESTAMP_RE = re.compile(r"\[\d{1,2}:\d{1,2}(?:[.:]\d{1,3})?\]")


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


def clean_track_title(text: str) -> str:
    original = str(text).strip()
    cleaned = re.sub(r"\s*[\(\[].*?[\)\]]", " ", original)
    cleaned = re.sub(r"\s+(?:feat\.?|ft\.?|featuring)\s+.*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -_")
    return cleaned or original


def _infer_title_artist(stem: str) -> tuple[str, str]:
    text = re.sub(r"^\s*\d{1,3}[\s._-]+", "", stem).strip()
    for separator in (" - ", " – ", " — "):
        if separator in text:
            artist, title = text.split(separator, 1)
            return title.strip(), artist.strip()
    return text, ""


def duration_matches(
    duration_ms: int,
    candidate_s: float,
    tolerance_ms: int = DURATION_TOLERANCE_MS,
) -> bool:
    if duration_ms <= 0 or candidate_s <= 0:
        return False
    return abs(int(candidate_s * 1000) - int(duration_ms)) <= tolerance_ms


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
    *,
    duration_tolerance_ms: int = DURATION_TOLERANCE_MS,
) -> OnlineLyrics | None:
    best: OnlineLyrics | None = None
    best_difference: int | None = None
    for candidate in candidates:
        # Solo se aceptan letras con marcas de tiempo. Las letras planas no
        # permiten seguir la canción y antes podían guardarse por error.
        if not candidate.synced.strip():
            continue
        if duration_ms > 0 and not duration_matches(
            duration_ms, candidate.duration_s, duration_tolerance_ms
        ):
            continue
        if not artist_matches(track_artist, candidate.artist_name):
            continue
        if not title_matches(track_title, candidate.track_name):
            continue
        difference = (
            0 if duration_ms <= 0 else abs(int(candidate.duration_s * 1000) - int(duration_ms))
        )
        # La duración más cercana gana entre varias letras sincronizadas.
        if best_difference is None or difference < best_difference:
            best = candidate
            best_difference = difference
    return best


def _request_json(url: str, timeout_s: int = REQUEST_TIMEOUT_S) -> object:
    last_error: Exception | None = None
    for attempt in range(REQUEST_RETRIES):
        request = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                return json.loads(response.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            if exc.code < 500:
                raise
            last_error = exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
        if attempt + 1 < REQUEST_RETRIES:
            time.sleep(RETRY_DELAY_S)
    if last_error is not None:
        raise last_error
    return []


def _parse_candidates(payload: object) -> list[OnlineLyrics]:
    if not isinstance(payload, list):
        return []
    results: list[OnlineLyrics] = []
    for item in payload:
        candidate = _parse_candidate(item)
        if candidate is not None:
            results.append(candidate)
    return results


def _search_candidates(
    track_title: str, artist: str, timeout_s: int = REQUEST_TIMEOUT_S
) -> list[OnlineLyrics]:
    params = urllib.parse.urlencode({"track_name": track_title, "artist_name": artist})
    return _parse_candidates(_request_json(f"{LRCLIB_SEARCH_URL}?{params}", timeout_s))


def _search_candidates_query(query: str, timeout_s: int = REQUEST_TIMEOUT_S) -> list[OnlineLyrics]:
    params = urllib.parse.urlencode({"q": query})
    return _parse_candidates(_request_json(f"{LRCLIB_SEARCH_URL}?{params}", timeout_s))


def _unique_texts(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).strip()
        key = normalize_text(text)
        if text and key and key not in seen:
            seen.add(key)
            result.append(text)
    return result


def search_lyrics(track: Track, timeout_s: int = REQUEST_TIMEOUT_S) -> OnlineLyrics | None:
    if not track.path or "://" in track.path:
        return None
    stem = Path(track.path).stem
    title = (track.title or "").strip() or stem
    artist = (track.artist or "").strip()
    if not artist:
        inferred_title, inferred_artist = _infer_title_artist(stem)
        artist = inferred_artist
        if not (track.title or "").strip() and inferred_title:
            title = inferred_title
    if not title or not artist:
        return None

    clean_title = clean_track_title(title)
    title_variants = _unique_texts([title, clean_title])
    artist_variants = _unique_texts(
        [artist, *[part for part in _ARTIST_SEPARATORS.split(artist) if part.strip()]]
    )
    candidates: list[OnlineLyrics] = []

    for title_variant in title_variants:
        for artist_variant in artist_variants:
            found = _search_candidates(title_variant, artist_variant, timeout_s)
            for candidate in found:
                if candidate not in candidates:
                    candidates.append(candidate)
            selected = select_lyrics(title_variant, artist, track.duration_ms, found)
            if selected is not None:
                return selected

    query = f"{artist_variants[-1]} {clean_title}".strip()
    found = _search_candidates_query(query, timeout_s)
    for candidate in found:
        if candidate not in candidates:
            candidates.append(candidate)
    selected = select_lyrics(clean_title, artist, track.duration_ms, found)
    if selected is not None:
        return selected

    # Último intento: misma canción/artista pero con una diferencia de duración
    # algo mayor (intros, silencios o versiones de distinta duración).
    return select_lyrics(
        clean_title,
        artist,
        track.duration_ms,
        candidates,
        duration_tolerance_ms=RELAXED_DURATION_TOLERANCE_MS,
    )


def target_path(track: Track) -> Path:
    # Junto al audio: «Cancion.mp3» → «Cancion.lrc».
    return Path(track.path).with_suffix(".lrc")


def shared_path(track: Track) -> Path:
    return LYRICS_DIR / f"{Path(track.path).stem}.lrc"


def lyrics_file_is_synced(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return LRC_TIMESTAMP_RE.search(text) is not None


def save_lyrics(track: Track, lyrics: OnlineLyrics, *, destination: Path | None = None) -> Path:
    path = destination or target_path(track)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(lyrics.synced.strip() + "\n", encoding="utf-8")
    return path


def fetch_lyrics(track: Track, *, force: bool = False) -> Path | None:
    if not track.path or "://" in track.path:
        return None
    sidecar = target_path(track)
    shared = shared_path(track)
    if not force:
        # Compatibilidad con letras descargadas antes en la carpeta de datos.
        for existing in (sidecar, shared):
            if not existing.is_file() or not lyrics_file_is_synced(existing):
                continue
            if existing == sidecar:
                return sidecar
            # Hay una letra sincronizada en la carpeta de datos, pero junto a
            # la canción solo había una plana: se copia para que la interfaz
            # muestre siempre la versión sincronizada.
            try:
                sidecar.parent.mkdir(parents=True, exist_ok=True)
                sidecar.write_text(
                    existing.read_text(encoding="utf-8", errors="replace"),
                    encoding="utf-8",
                )
                return sidecar
            except OSError:
                return existing
    # Si solo hay una letra plana (sin tiempos), se intenta sustituir por una
    # sincronizada. Si no aparece, no se borra el archivo existente.
    lyrics = search_lyrics(track)
    if lyrics is None:
        return None
    try:
        return save_lyrics(track, lyrics, destination=sidecar)
    except OSError as exc:
        # Carpeta de música sin permiso de escritura: se usa la carpeta de datos.
        logger.warning("No se pudo guardar la letra junto a %s: %s", track.path, exc)
        return save_lyrics(track, lyrics, destination=shared)


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
