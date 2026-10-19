from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Any

from PySide6.QtCore import QThread, Signal

from app.library.models import RadioStation

logger = logging.getLogger(__name__)

#: Identificador que se envía a las APIs (buena práctica en radio-browser).
USER_AGENT = "PyAmp/0.2.1 (+https://github.com/Danix13-glich/PyAmp)"

#: Servicios de geolocalización por IP, en orden de preferencia.
GEO_URLS = (
    "https://ipapi.co/json/",
    "https://ipwho.is/",
)

#: Espejos de la API de radio-browser, en orden de preferencia.
RADIO_BROWSER_HOSTS = (
    "https://de1.api.radio-browser.info",
    "https://nl1.api.radio-browser.info",
    "https://at1.api.radio-browser.info",
)

NETWORK_TIMEOUT_S = 10


def _get_json(url: str) -> Any:
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT_S) as response:
        payload = response.read().decode("utf-8", errors="replace")
    return json.loads(payload)


def _country_code_from(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    code = payload.get("country_code") or payload.get("countryCode")
    if not code:
        return None
    return str(code).strip().upper() or None


def detect_country_code() -> str | None:
    """Código ISO de país según la IP pública (requiere internet)."""
    for url in GEO_URLS:
        try:
            code = _country_code_from(_get_json(url))
        except Exception as exc:  # noqa: BLE001 - la red es opcional/best-effort
            logger.info("Geolocalización falló con %s: %s", url, exc)
            continue
        if code:
            return code
    return None


def parse_stations(payload: Any, *, limit: int = 60) -> list[RadioStation]:
    """Convierte la respuesta de radio-browser en emisoras de PyAmp."""
    if not isinstance(payload, list):
        return []
    stations: list[RadioStation] = []
    seen: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        url = str(item.get("url_resolved") or item.get("url") or "").strip()
        if not name or not url or url in seen:
            continue
        seen.add(url)
        genre = ""
        tags = item.get("tags")
        if isinstance(tags, str) and tags.strip():
            genre = tags.split(",")[0].strip()
        country = str(item.get("country") or "").strip()
        stations.append(RadioStation(name=name, url=url, genre=genre, country=country))
        if len(stations) >= limit:
            break
    return stations


def search_stations(country_code: str, *, limit: int = 60) -> list[RadioStation]:
    """Emisoras online del país indicado, ordenadas por popularidad."""
    params = urllib.parse.urlencode(
        {
            "countrycode": country_code.upper(),
            "order": "clickcount",
            "reverse": "true",
            "hidebroken": "true",
            "limit": str(limit),
        }
    )
    last_error: Exception | None = None
    for host in RADIO_BROWSER_HOSTS:
        url = f"{host}/json/stations/search?{params}"
        try:
            return parse_stations(_get_json(url), limit=limit)
        except Exception as exc:  # noqa: BLE001 - probamos el siguiente espejo
            logger.info("radio-browser falló con %s: %s", host, exc)
            last_error = exc
    if last_error is not None:
        raise last_error
    return []


class RadioSearchWorker(QThread):
    """Busca emisoras por ubicación sin bloquear la interfaz."""

    finished_ok = Signal(list)  # list[RadioStation]
    failed = Signal(str)

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self._country: str | None = None

    @property
    def country_code(self) -> str | None:
        return self._country

    def run(self) -> None:
        try:
            country = detect_country_code()
            if not country:
                self.failed.emit("No se pudo determinar tu ubicación")
                return
            self._country = country
            stations = search_stations(country)
            if not stations:
                self.failed.emit("No se encontraron emisoras")
                return
            self.finished_ok.emit(stations)
        except Exception as exc:  # noqa: BLE001 - nunca debe tumbar la app
            logger.warning("Búsqueda de emisoras falló: %s", exc)
            self.failed.emit(str(exc))
