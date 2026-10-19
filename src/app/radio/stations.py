from __future__ import annotations

import json

from app.core.settings import Settings
from app.library.models import RadioStation

#: Emisoras incluidas de serie. Las URLs son públicas y pueden cambiar.
BUILTIN_STATIONS: tuple[RadioStation, ...] = (
    RadioStation(
        "Radio Paradise", "https://stream.radioparadise.com/aac-320", "Eclectic", "EE. UU.", True
    ),
    RadioStation(
        "SomaFM Groove Salad",
        "https://ice1.somafm.com/groovesalad-128-mp3",
        "Chillout",
        "EE. UU.",
        True,
    ),
    RadioStation("SomaFM Lush", "https://ice1.somafm.com/lush-128-mp3", "Ambient", "EE. UU.", True),
    RadioStation(
        "Radio Swiss Jazz",
        "https://stream.srg-ssr.ch/m/rsj/mp3_128",
        "Jazz",
        "Suiza",
        True,
    ),
    RadioStation(
        "Radio Swiss Classic",
        "https://stream.srg-ssr.ch/m/rsc_de/mp3_128",
        "Clásica",
        "Suiza",
        True,
    ),
    RadioStation(
        "France Inter",
        "https://icecast.radiofrance.fr/franceinter-midfi.mp3",
        "Actualidad",
        "Francia",
        True,
    ),
    RadioStation(
        "Cadena SER",
        "https://flucast-m06-03.flumotion.com/copesedes/ser.mp3",
        "Actualidad",
        "España",
        True,
    ),
    RadioStation(
        "LOS40", "https://flucast-m06-02.flumotion.com/copesedes/los40.mp3", "Pop", "España", True
    ),
    RadioStation(
        "RNE Radio 3",
        "https://rtvelivestream.akamaized.net/rtvesec/rne/rne_r3_main.m3u8",
        "Cultura",
        "España",
        True,
    ),
)


class RadioLibrary:

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def custom_stations(self) -> list[RadioStation]:
        raw = self._settings.radio_stations
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            return []
        if not isinstance(data, list):
            return []
        stations: list[RadioStation] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            url = str(item.get("url", "")).strip()
            if not name or not url:
                continue
            stations.append(
                RadioStation(
                    name=name,
                    url=url,
                    genre=str(item.get("genre", "")).strip(),
                    country=str(item.get("country", "")).strip(),
                )
            )
        return stations

    def stations(self) -> list[RadioStation]:
        return [*BUILTIN_STATIONS, *self.custom_stations()]

    def search(self, term: str) -> list[RadioStation]:
        return [station for station in self.stations() if station.matches(term)]

    def add(self, station: RadioStation) -> bool:
        current = self.custom_stations()
        if any(item.url == station.url for item in current):
            return False
        current.append(RadioStation(station.name, station.url, station.genre, station.country))
        self._save(current)
        return True

    def update(self, old_url: str, station: RadioStation) -> bool:
        current = self.custom_stations()
        for index, item in enumerate(current):
            if item.url == old_url:
                current[index] = RadioStation(
                    station.name, station.url, station.genre, station.country
                )
                self._save(current)
                return True
        return False

    def remove(self, url: str) -> None:
        current = [item for item in self.custom_stations() if item.url != url]
        self._save(current)

    def _save(self, stations: list[RadioStation]) -> None:
        payload = [
            {
                "name": station.name,
                "url": station.url,
                "genre": station.genre,
                "country": station.country,
            }
            for station in stations
        ]
        self._settings.radio_stations = json.dumps(payload, ensure_ascii=False)
