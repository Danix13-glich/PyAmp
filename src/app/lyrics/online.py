from __future__ import annotations

import contextlib
import json
import logging
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.library.models import Track
from app.utils.paths import LYRICS_DIR

logger = logging.getLogger(__name__)

#: API pública de LRCLIB (sin clave ni registro). Devuelve letras sincronizadas
#: y planas junto a la duración real de cada resultado.
LRCLIB_SEARCH_URL = "https://lrclib.net/api/search"
USER_AGENT = "PyAmp/0.2.5 (+https://github.com/Danix13-glich/PyAmp)"
REQUEST_TIMEOUT_S = 8
REQUEST_RETRIES = 4
RETRY_DELAY_S = 1.0
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

#: Cómo máximo se prueban estas combinaciones de título/artista por búsqueda.
MAX_SEARCH_ATTEMPTS = 4
#: Resultados con estas palabras suelen ser versiones no deseadas.
_BAD_VERSION_WORDS = (
    "karaoke version",
    "instrumental version",
    "tribute band",
    "cover version",
    "nightcore",
    "sped up",
    "slowed",
    "8d audio",
)
#: Palabras que suelen acompañar a un sufijo de versión en el título.
_VERSION_WORDS = (
    "official",
    "lyric",
    "letra",
    "hd",
    "hq",
    "remaster",
    "remastered",
    "remasterizado",
    "explicit",
    "clean",
    "radio edit",
    "album version",
    "single version",
    "bonus",
    "deluxe",
    "from the",
)
_ARTIST_STOPWORDS = {"the", "el", "la", "los", "las", "de", "del", "and", "y"}


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
    # Se conservan letras y números de cualquier alfabeto (cirílico, griego,
    # árabe, CJK...), no solo ASCII.
    cleaned = "".join(ch if ch.isalnum() else " " for ch in without_marks.casefold())
    return " ".join(cleaned.split())


def _artist_parts(artist: str) -> list[str]:
    parts = [normalize_text(part) for part in _ARTIST_SEPARATORS.split(artist)]
    result = [part for part in parts if len(part) >= 2 and part not in _ARTIST_STOPWORDS]
    full = normalize_text(artist)
    if len(full) >= 2 and full not in result:
        result.append(full)
    return result


def artist_score(track_artist: str | None, candidate_artist: str) -> float:
    # Se exige coincidencia de artista: sin este dato no se acepta la letra.
    if not track_artist or not str(track_artist).strip():
        return 0.0
    candidate = normalize_text(candidate_artist)
    if not candidate:
        return 0.0
    best = 0.0
    for part in _artist_parts(str(track_artist)):
        if part == candidate:
            return 1.0
        if len(part) >= 4 and (part in candidate or candidate in part):
            shorter = min(len(part), len(candidate))
            best = max(best, 0.9 if shorter >= 5 else 0.75)
            continue
        # Erratas leves en el nombre del artista: "Månzskin" -> "Måneskin",
        # "OneRepublc" -> "OneRepublic", etc.
        if len(part) >= 5 and len(candidate) >= 5:
            ratio = SequenceMatcher(None, part, candidate).ratio()
            if ratio >= 0.82:
                best = max(best, 0.8)
        part_tokens = set(part.split())
        candidate_tokens = set(candidate.split())
        common = part_tokens & candidate_tokens
        if part_tokens and len(common) / len(part_tokens) >= 0.8:
            best = max(best, 0.7)
    return best


def artist_matches(track_artist: str | None, candidate_artist: str) -> bool:
    return artist_score(track_artist, candidate_artist) >= 0.7


def title_score(track_title: str | None, candidate_name: str) -> float:
    title = normalize_text(track_title or "")
    name = normalize_text(candidate_name)
    if not title or not name:
        return 0.0
    if title == name:
        return 1.0
    title_tokens = title.split()
    name_tokens = name.split()
    # Títulos muy cortos ("Go", "Up"...) solo valen si coinciden como palabra
    # completa; así no se confunden con el interior de otra palabra.
    if len(title) <= 3:
        return 0.9 if title in name_tokens else 0.0
    if title in name or name in title:
        shorter = min(len(title), len(name))
        return 0.92 if shorter >= 5 else 0.78
    title_set = set(title_tokens)
    name_set = set(name_tokens)
    common = title_set & name_set
    if not common:
        return 0.0
    track_coverage = len(common) / len(title_set)
    candidate_coverage = len(common) / len(name_set)
    if track_coverage >= 0.8 and candidate_coverage >= 0.5:
        return 0.75
    return 0.0


def title_matches(track_title: str | None, candidate_name: str) -> bool:
    return title_score(track_title, candidate_name) > 0.0


def clean_track_title(text: str) -> str:
    original = str(text).strip()
    # Paréntesis y corchetes suelen contener "Official Video", "Remastered",
    # "feat. ...", etc. Se eliminan para consultar el título base.
    cleaned = re.sub(r"\s*[\(\[].*?[\)\]]", " ", original)
    cleaned = re.sub(r"\s+(?:feat\.?|ft\.?|featuring)\s+.*$", "", cleaned, flags=re.I)
    # Sufijos separados por guion: "Song - Remastered 2011".
    version_words = "|".join(re.escape(word) for word in _VERSION_WORDS)
    cleaned = re.sub(
        rf"\s+[-–—]\s+(?:(?:\d{{4}}\s+)?(?:{version_words})\b.*)$",
        "",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"^\s*\d{1,3}\s*[.)_-]\s*", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -_")
    return cleaned or original


def _looks_like_version_text(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return True
    if normalized.isdigit():
        return True
    version_words = (*_VERSION_WORDS, "live", "version")
    return any(word in normalized for word in version_words)


def _infer_title_artist(stem: str) -> tuple[str, str]:
    text = re.sub(r"^\s*\d{1,3}[\s._-]+", "", stem).strip()
    for separator in (" - ", " – ", " — "):
        if separator in text:
            artist, title = text.split(separator, 1)
            return title.strip(), artist.strip()
    return text, ""


def _title_variants(title: str, artist: str) -> list[str]:
    variants = [title, clean_track_title(title)]
    # Títulos guardados como "Artista - Canción": si la parte izquierda
    # coincide con el artista, se prueba también solo con la canción.
    for separator in (" - ", " – ", " — "):
        if separator not in title:
            continue
        left, right = title.split(separator, 1)
        left_norm = normalize_text(left)
        artist_norm = normalize_text(artist)
        if left_norm and (left_norm in artist_norm or artist_norm in left_norm):
            variants.append(right)
        break
    return _unique_texts(variants)


def _artist_variants(artist: str) -> list[str]:
    variants = [artist]
    variants.extend(part.strip() for part in _ARTIST_SEPARATORS.split(artist) if part.strip())
    # "The Beatles" también se busca como "Beatles"; algunos catálogos
    # almacenan el nombre sin el artículo.
    expanded: list[str] = []
    for variant in variants:
        expanded.append(variant)
        lowered = variant.casefold()
        for prefix in ("the ", "los ", "las "):
            if lowered.startswith(prefix) and len(variant) > len(prefix) + 1:
                expanded.append(variant[len(prefix) :])
    return _unique_texts(expanded)[:4]


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
    track_name = str(item.get("trackName") or "").strip("\ufeff \t\r\n")
    artist_name = str(item.get("artistName") or "").strip("\ufeff \t\r\n")
    try:
        duration_s = float(item.get("duration") or 0)
    except (TypeError, ValueError):
        return None
    synced = str(item.get("syncedLyrics") or "").strip("\ufeff \t\r\n")
    plain = str(item.get("plainLyrics") or "").strip("\ufeff \t\r\n")
    if not track_name or not artist_name or not (synced or plain):
        return None
    return OnlineLyrics(track_name, artist_name, duration_s, synced, plain)


def _version_penalty(track_title: str, candidate: OnlineLyrics) -> float:
    track_text = normalize_text(track_title)
    candidate_text = normalize_text(f"{candidate.track_name} {candidate.artist_name}")
    penalty = 0.0
    for word in _BAD_VERSION_WORDS:
        if word in candidate_text and word not in track_text:
            penalty += 30.0
    # Las versiones en directo suelen tener otra duración, pero si la duración
    # no se conoce este pequeño castigo evita elegirlas por error.
    candidate_tokens = set(candidate_text.split())
    track_tokens = set(track_text.split())
    if "live" in candidate_tokens and "live" not in track_tokens:
        penalty += 8.0
    return penalty


def _candidate_pairs(candidate: OnlineLyrics) -> list[tuple[str, str]]:
    pairs = [(candidate.track_name, candidate.artist_name)]
    # Muchos resultados de LRCLIB vienen subidos por canales de YouTube:
    # trackName = "Måneskin - Beggin'" y artistName = "7clouds". En ese caso
    # el artista real está en el título.
    for separator in (" - ", " – ", " — "):
        if separator in candidate.track_name:
            left, right = candidate.track_name.split(separator, 1)
            if left.strip() and right.strip():
                pairs.append((right.strip(), left.strip()))
            break
    for separator in (" - ", " – ", " — "):
        if separator in candidate.artist_name:
            left, right = candidate.artist_name.split(separator, 1)
            if left.strip() and right.strip():
                pairs.append((candidate.track_name, left.strip()))
            break
    return pairs


def _candidate_score(
    track_title: str,
    track_artist: str | None,
    duration_ms: int,
    candidate: OnlineLyrics,
    *,
    duration_tolerance_ms: int,
) -> tuple[float, int] | None:
    if not candidate.synced.strip():
        return None
    difference = 0 if duration_ms <= 0 else abs(int(candidate.duration_s * 1000) - int(duration_ms))
    if duration_ms > 0 and difference > duration_tolerance_ms:
        return None
    title_points, artist_points = max(
        (
            (title_score(track_title, title), artist_score(track_artist, artist))
            for title, artist in _candidate_pairs(candidate)
        ),
        key=lambda pair: pair[0] * 0.6 + pair[1] * 0.4,
    )
    if title_points <= 0.0 or artist_points < 0.7:
        return None
    score = title_points * 50.0 + artist_points * 35.0
    if title_points >= 0.99:
        score += 5.0
    if artist_points >= 0.99:
        score += 5.0
    if duration_ms > 0:
        score += max(0.0, 1.0 - difference / duration_tolerance_ms) * 25.0
    penalty = _version_penalty(track_title, candidate)
    if penalty >= 30.0:
        return None
    score -= penalty
    return score, difference


def _is_excellent(
    candidate: OnlineLyrics,
    track_title: str,
    artist: str,
    duration_ms: int,
) -> bool:
    difference = 0 if duration_ms <= 0 else abs(int(candidate.duration_s * 1000) - int(duration_ms))
    return (
        title_score(track_title, candidate.track_name) >= 0.99
        and artist_score(artist, candidate.artist_name) >= 0.99
        and (duration_ms <= 0 or difference <= 2000)
        and _version_penalty(track_title, candidate) == 0.0
    )


def select_lyrics(
    track_title: str,
    track_artist: str | None,
    duration_ms: int,
    candidates: list[OnlineLyrics],
    *,
    duration_tolerance_ms: int = DURATION_TOLERANCE_MS,
) -> OnlineLyrics | None:
    best: OnlineLyrics | None = None
    best_key: tuple[float, int] | None = None
    for candidate in candidates:
        result = _candidate_score(
            track_title,
            track_artist,
            duration_ms,
            candidate,
            duration_tolerance_ms=duration_tolerance_ms,
        )
        if result is None:
            continue
        score, difference = result
        key = (score, -difference)
        if best_key is None or key > best_key:
            best = candidate
            best_key = key
    return best


def _request_json(url: str, timeout_s: int = REQUEST_TIMEOUT_S) -> object:
    last_error: Exception | None = None
    for attempt in range(REQUEST_RETRIES):
        request = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
        )
        delay = min(RETRY_DELAY_S * (attempt + 1), 3.0)
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                return json.loads(response.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            # 429 = demasiadas peticiones; 5xx = servidor ocupado.
            if exc.code < 500 and exc.code != 429:
                raise
            last_error = exc
            retry_after = exc.headers.get("Retry-After")
            if retry_after:
                with contextlib.suppress(ValueError):
                    delay = max(delay, min(float(retry_after), 5.0))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
        if attempt + 1 < REQUEST_RETRIES:
            time.sleep(delay)
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
    # La búsqueda estructurada (track_name + artist_name) de LRCLIB devuelve
    # 503 con frecuencia; la búsqueda libre es más estable y ya devuelve
    # suficientes resultados para puntuarlos después.
    query = f"{artist} {track_title}".strip()
    params = urllib.parse.urlencode({"q": query})
    return _parse_candidates(_request_json(f"{LRCLIB_SEARCH_URL}?{params}", timeout_s))


def _search_candidates_query(query: str, timeout_s: int = REQUEST_TIMEOUT_S) -> list[OnlineLyrics]:
    params = urllib.parse.urlencode({"q": query})
    return _parse_candidates(_request_json(f"{LRCLIB_SEARCH_URL}?{params}", timeout_s))


def _search_candidates_by_title(
    title: str, timeout_s: int = REQUEST_TIMEOUT_S
) -> list[OnlineLyrics]:
    # La búsqueda por título suele funcionar cuando el artista tiene una
    # errata, aunque la búsqueda conjunta de título + artista devuelva 503.
    params = urllib.parse.urlencode({"track_name": title})
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


def _merge_candidates(target: list[OnlineLyrics], found: list[OnlineLyrics]) -> None:
    for candidate in found:
        if candidate not in target:
            target.append(candidate)


def _bad_artist(artist: str) -> bool:
    return normalize_text(artist) in {
        "various artists",
        "unknown artist",
        "artista desconocido",
        "unknown",
    }


def search_lyrics(track: Track, timeout_s: int = REQUEST_TIMEOUT_S) -> OnlineLyrics | None:
    if not track.path or "://" in track.path:
        return None
    stem = Path(track.path).stem
    tag_title = (track.title or "").strip()
    artist = (track.artist or track.albumartist or "").strip()
    if _bad_artist(artist):
        artist = ""

    inferred_title, inferred_artist = _infer_title_artist(stem)
    title = tag_title or inferred_title or stem
    if not artist:
        if inferred_artist:
            artist = inferred_artist
            if not tag_title:
                title = inferred_title
        elif " - " in title:
            # Algunos archivos guardan "Artista - Canción" en la etiqueta de
            # título y no rellenan la etiqueta de artista.
            inferred_from_title, inferred_artist = _infer_title_artist(title)
            inferred_from_title = clean_track_title(inferred_from_title)
            if inferred_artist and not _looks_like_version_text(inferred_from_title):
                title = inferred_from_title
                artist = inferred_artist
    if not title or not artist:
        return None

    title_variants = _title_variants(title, artist)
    artist_variants = _artist_variants(artist)
    if not title_variants or not artist_variants:
        return None

    primary_title = title_variants[0]
    primary_artist = artist_variants[0]
    best_title = title_variants[-1]
    first_artist = artist_variants[1] if len(artist_variants) > 1 else primary_artist

    attempts: list[tuple[str, str]] = []
    for query_title in _unique_texts([primary_title, best_title]):
        for query_artist in _unique_texts([primary_artist, first_artist]):
            key = (normalize_text(query_title), normalize_text(query_artist))
            if key not in {
                (normalize_text(item_title), normalize_text(item_artist))
                for item_title, item_artist in attempts
            }:
                attempts.append((query_title, query_artist))

    candidates: list[OnlineLyrics] = []
    last_error: Exception | None = None

    # Primero se prueba la combinación más probable. En cuanto aparece una
    # candidata válida se devuelve: así no se satura la API con variantes.
    for query_title, query_artist in attempts[:MAX_SEARCH_ATTEMPTS]:
        try:
            found = _search_candidates(query_title, query_artist, timeout_s)
        except Exception as exc:  # noqa: BLE001 - se prueba la siguiente variante
            last_error = exc
            logger.info(
                "Búsqueda de letras falló para %r / %r: %s",
                query_title,
                query_artist,
                exc,
            )
            continue
        _merge_candidates(candidates, found)
        selected = select_lyrics(query_title, artist, track.duration_ms, found)
        if selected is not None:
            logger.debug(
                "Letra encontrada: %s / %s (%s)",
                selected.track_name,
                selected.artist_name,
                selected.duration_s,
            )
            return selected

    # Si el artista tiene una errata o un nombre alternativo, una búsqueda
    # solo por título permite encontrar la canción; luego se valida el artista
    # con coincidencia difusa.
    for fallback_title in _unique_texts([best_title, primary_title]):
        for search_by_title in (
            _search_candidates_by_title,
            _search_candidates_query,
        ):
            try:
                found = search_by_title(fallback_title, timeout_s)
            except Exception as exc:  # noqa: BLE001 - la búsqueda por título es opcional
                last_error = exc
                logger.info(
                    "Búsqueda de letras por título falló para %r: %s",
                    fallback_title,
                    exc,
                )
                continue
            _merge_candidates(candidates, found)
            selected = select_lyrics(fallback_title, artist, track.duration_ms, found)
            if selected is not None:
                logger.debug(
                    "Letra encontrada por título: %s / %s (%s)",
                    selected.track_name,
                    selected.artist_name,
                    selected.duration_s,
                )
                return selected

    # Erratas en el apellido del artista: "Pedro Kapo" -> "Pedro".
    # Buscar solo con la primera palabra del artista suele encontrar la canción
    # y luego la puntuación valida el nombre completo con coincidencia difusa.
    artist_tokens: list[str] = []
    for artist_variant in _unique_texts([primary_artist, first_artist]):
        for token in artist_variant.split():
            if len(normalize_text(token)) >= 3 and token not in artist_tokens:
                artist_tokens.append(token)
    for token in artist_tokens[:3]:
        for fallback_title in _unique_texts([best_title, primary_title]):
            query = f"{fallback_title} {token}".strip()
            try:
                found = _search_candidates_query(query, timeout_s)
            except Exception as exc:  # noqa: BLE001 - la búsqueda parcial es opcional
                last_error = exc
                logger.info("Búsqueda parcial de letras falló para %r: %s", query, exc)
                continue
            _merge_candidates(candidates, found)
            selected = select_lyrics(best_title, artist, track.duration_ms, found)
            if selected is not None:
                logger.debug(
                    "Letra encontrada con artista parcial: %s / %s (%s)",
                    selected.track_name,
                    selected.artist_name,
                    selected.duration_s,
                )
                return selected

    # Si el título es muy común, buscar por el artista devuelve su catálogo y
    # permite encontrar la canción aunque el título no aparezca en los primeros
    # resultados de la búsqueda por título.
    for fallback_artist in _unique_texts([primary_artist, first_artist]):
        try:
            found = _search_candidates_query(fallback_artist, timeout_s)
        except Exception as exc:  # noqa: BLE001 - la búsqueda por artista es opcional
            last_error = exc
            logger.info("Búsqueda de letras por artista falló para %r: %s", fallback_artist, exc)
            continue
        _merge_candidates(candidates, found)
        selected = select_lyrics(best_title, artist, track.duration_ms, found)
        if selected is not None:
            logger.debug(
                "Letra encontrada por artista: %s / %s (%s)",
                selected.track_name,
                selected.artist_name,
                selected.duration_s,
            )
            return selected

    # Se comparan todos los resultados y gana el que mejor encaje.
    selected = select_lyrics(best_title, artist, track.duration_ms, candidates)
    if selected is not None:
        return selected

    if not candidates and last_error is not None:
        raise last_error

    # Último intento: misma canción/artista pero con una diferencia de duración
    # algo mayor (intros, silencios o versiones de distinta duración).
    return select_lyrics(
        best_title,
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
    #: Ruta de la pista para la que la búsqueda no pudo completarse.
    failed = Signal(str)

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
            self.failed.emit(self._track.path)
            return
        if path is None:
            self.missing.emit(self._track.path)
        else:
            logger.info("Letra online encontrada para %s: %s", self._track.path, path)
            self.found.emit(self._track.path, str(path))
