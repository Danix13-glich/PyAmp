from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)

USER_AGENT = "PyAmp/0.2.3 (+https://github.com/Danix13-glich/PyAmp)"
NETWORK_TIMEOUT_S = 12
ITUNES_URL = "https://itunes.apple.com/search"
DEEZER_URL = "https://api.deezer.com/search"


@dataclass(frozen=True)
class SongResult:

    title: str
    artist: str
    duration_ms: int
    link: str
    preview_url: str = ""


def _get_json(url: str) -> object:
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT_S) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def _read_exact(stream: object, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = stream.read(remaining)  # type: ignore[attr-defined]
        if not chunk:
            break
        chunks.append(bytes(chunk))
        remaining -= len(chunk)
    return b"".join(chunks)


def fetch_icy_title(url: str) -> str:
    stream_url = str(url).strip()
    if not stream_url:
        return ""
    request = urllib.request.Request(
        stream_url,
        headers={
            "User-Agent": USER_AGENT,
            "Icy-MetaData": "1",
            "Accept": "*/*",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT_S) as response:
            raw_interval = response.headers.get("icy-metaint")
            if not raw_interval:
                return ""
            interval = int(str(raw_interval).strip())
            if interval <= 0 or interval > 1_000_000:
                return ""
            for _ in range(6):
                _read_exact(response, interval)
                raw_length = _read_exact(response, 1)
                if not raw_length:
                    return ""
                length = raw_length[0] * 16
                if length <= 0:
                    continue
                payload = _read_exact(response, length)
                match = re.search(rb"StreamTitle='(.*?)';", payload, re.DOTALL)
                if match:
                    return match.group(1).decode("utf-8", errors="replace").strip()
    except Exception as exc:  # noqa: BLE001 - el directo puede no ser Icecast
        logger.info("No se pudieron leer metadatos ICY de %s: %s", stream_url, exc)
    return ""


def _first_itunes(payload: object) -> SongResult | None:
    if not isinstance(payload, dict):
        return None
    results = payload.get("results")
    if not isinstance(results, list):
        return None
    for item in results:
        if not isinstance(item, dict):
            continue
        title = str(item.get("trackName") or "").strip()
        artist = str(item.get("artistName") or "").strip()
        if not title or not artist:
            continue
        try:
            duration_ms = int(item.get("trackTimeMillis") or 0)
        except (TypeError, ValueError):
            duration_ms = 0
        link = str(item.get("trackViewUrl") or "").strip()
        preview = str(item.get("previewUrl") or "").strip()
        return SongResult(title, artist, duration_ms, link, preview)
    return None


def _first_deezer(payload: object) -> SongResult | None:
    if not isinstance(payload, dict):
        return None
    results = payload.get("data")
    if not isinstance(results, list):
        return None
    for item in results:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        artist_data = item.get("artist")
        artist = str(artist_data.get("name") or "").strip() if isinstance(artist_data, dict) else ""
        if not title or not artist:
            continue
        try:
            duration_ms = int(float(item.get("duration") or 0) * 1000)
        except (TypeError, ValueError):
            duration_ms = 0
        link = str(item.get("link") or "").strip()
        preview = str(item.get("preview") or "").strip()
        return SongResult(title, artist, duration_ms, link, preview)
    return None


def search_online_song(term: str) -> SongResult | None:
    query = str(term).strip()
    if not query:
        return None
    itunes_params = urllib.parse.urlencode(
        {"term": query, "media": "music", "entity": "song", "limit": "5"}
    )
    try:
        result = _first_itunes(_get_json(f"{ITUNES_URL}?{itunes_params}"))
        if result is not None:
            return result
    except Exception as exc:  # noqa: BLE001 - se prueba el siguiente servicio
        logger.info("Búsqueda iTunes falló para %r: %s", query, exc)
    deezer_params = urllib.parse.urlencode({"q": query, "limit": "5"})
    try:
        return _first_deezer(_get_json(f"{DEEZER_URL}?{deezer_params}"))
    except Exception as exc:  # noqa: BLE001 - la red nunca debe tumbar la app
        logger.info("Búsqueda Deezer falló para %r: %s", query, exc)
    return None


class SongSearchWorker(QThread):

    found = Signal(object)  # SongResult
    failed = Signal(str)

    def __init__(self, term: str, parent: object | None = None, *, stream_url: str = "") -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self._term = term
        self._stream_url = stream_url

    def run(self) -> None:
        try:
            term = self._term.strip()
            if not term and self._stream_url:
                term = fetch_icy_title(self._stream_url)
            result = search_online_song(term) if term else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("Búsqueda de canción falló: %s", exc)
            self.failed.emit(str(exc))
            return
        if result is None:
            self.failed.emit("")
        else:
            logger.info("Canción encontrada: %s — %s", result.title, result.artist)
            self.found.emit(result)


class SongDownloadWorker(QThread):

    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, result: SongResult, folder: Path, parent: object | None = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self._result = result
        self._folder = Path(folder)

    def run(self) -> None:
        executable = shutil.which("yt-dlp")
        if not executable:
            self.failed.emit("yt-dlp")
            return
        query = f"{self._result.artist} {self._result.title}".strip()
        try:
            self._folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.failed.emit(str(exc))
            return
        command = [
            executable,
            "--no-playlist",
            "--quiet",
            "--no-warnings",
            "--print",
            "after_move:filepath",
            "--extract-audio",
            "--audio-format",
            "mp3",
            "--audio-quality",
            "0",
            "--output",
            str(self._folder / "%(title)s.%(ext)s"),
            f"ytsearch1:{query}",
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=600,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            logger.warning("Descarga de %r falló: %s", query, exc)
            self.failed.emit(str(exc))
            return
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip().splitlines()
            self.failed.emit(detail[-1] if detail else "yt-dlp")
            return
        lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        target = Path(lines[-1]) if lines else None
        if target is None or not target.is_file():
            self.failed.emit("no-file")
            return
        logger.info("Canción descargada: %s", target)
        self.finished_ok.emit(str(target))
