"""Emisoras de radio y persistencia de las que añade o cambia el usuario."""

from __future__ import annotations

import json

from app.core.settings import Settings
from app.library.models import RadioStation

#: Emisoras incluidas de serie. Ahora vacío a propósito: la lista arranca
#: sin emisoras y el usuario las busca por su zona (o las añade a mano).
BUILTIN_STATIONS: tuple[RadioStation, ...] = ()


def _load(raw: str, default: object) -> object:
    if not raw:
        return default
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return default
    return data


class RadioLibrary:
    """Emisoras incluidas (editables) + las que añade el usuario."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    # ------------------------------------------------------------- lectura
    def custom_stations(self) -> list[RadioStation]:
        """Emisoras añadidas por el usuario (tolerante a datos corruptos)."""
        data = _load(self._settings.radio_stations, [])
        if not isinstance(data, list):
            return []
        stations: list[RadioStation] = []
        for item in data:
            station = _station_from_dict(item)
            if station is not None:
                stations.append(station)
        return stations

    def is_builtin(self, url: str) -> bool:
        """True si la URL pertenece a una emisora incluida de serie."""
        return any(station.url == url for station in BUILTIN_STATIONS)

    def found_stations(self) -> list[RadioStation]:
        """Emisoras encontradas por ubicación (guardadas en local)."""
        data = _load(self._settings.radio_found, [])
        if not isinstance(data, list):
            return []
        stations: list[RadioStation] = []
        for item in data:
            station = _station_from_dict(item)
            if station is not None:
                stations.append(station)
        return stations

    def set_found_stations(self, stations: list[RadioStation]) -> None:
        self._settings.radio_found = json.dumps([_as_dict(s) for s in stations], ensure_ascii=False)

    def stations(self) -> list[RadioStation]:
        """Todas las emisoras visibles: incluidas (con cambios) + propias + buscadas."""
        overrides = self._overrides()
        hidden = self._hidden()
        result: list[RadioStation] = []
        for base in BUILTIN_STATIONS:
            if base.url in hidden:
                continue
            change = overrides.get(base.url)
            if change:
                result.append(
                    RadioStation(
                        name=str(change.get("name", base.name)),
                        url=base.url,
                        genre=str(change.get("genre", base.genre)),
                        country=str(change.get("country", base.country)),
                        builtin=True,
                    )
                )
            else:
                result.append(base)
        result.extend(self.custom_stations())
        result.extend(self.found_stations())
        return result

    def search(self, term: str) -> list[RadioStation]:
        """Emisoras que coinciden con el texto de búsqueda."""
        return [station for station in self.stations() if station.matches(term)]

    # ------------------------------------------------------------ escritura
    def add(self, station: RadioStation) -> bool:
        """Añade una emisora propia; False si la URL ya existía."""
        if any(item.url == station.url for item in self.stations()):
            return False
        current = self.custom_stations()
        current.append(_clean(station))
        self._save_custom(current)
        return True

    def update(self, old_url: str, station: RadioStation) -> bool:
        """Edita una emisora (incluidas las de serie); False si no existe."""
        if not any(item.url == old_url for item in self.stations()):
            return False
        if station.url != old_url:
            # Cambiar la URL equivale a borrar la antigua y añadir la nueva.
            self.remove(old_url)
            return self.add(station)
        change = {"name": station.name, "genre": station.genre, "country": station.country}
        if self.is_builtin(old_url):
            overrides = self._overrides()
            overrides[old_url] = change
            self._save_overrides(overrides)
            return True
        found = self.found_stations()
        if any(item.url == old_url for item in found):
            for index, item in enumerate(found):
                if item.url == old_url:
                    found[index] = _clean(station)
                    break
            self.set_found_stations(found)
            return True
        current = self.custom_stations()
        for index, item in enumerate(current):
            if item.url == old_url:
                current[index] = _clean(station)
                break
        self._save_custom(current)
        return True

    def remove(self, url: str) -> None:
        """Elimina una emisora (también las de serie)."""
        if self.is_builtin(url):
            hidden = self._hidden()
            hidden.add(url)
            self._save_hidden(hidden)
            overrides = self._overrides()
            if overrides.pop(url, None) is not None:
                self._save_overrides(overrides)
            return
        found = self.found_stations()
        if any(item.url == url for item in found):
            self.set_found_stations([item for item in found if item.url != url])
            return
        self._save_custom([item for item in self.custom_stations() if item.url != url])

    # ------------------------------------------------------------- interno
    def _overrides(self) -> dict[str, dict[str, str]]:
        data = _load(self._settings.radio_overrides, {})
        if not isinstance(data, dict):
            return {}
        return {str(key): value for key, value in data.items() if isinstance(value, dict)}

    def _hidden(self) -> set[str]:
        data = _load(self._settings.radio_hidden, [])
        if not isinstance(data, list):
            return set()
        return {str(item) for item in data}

    def _save_custom(self, stations: list[RadioStation]) -> None:
        self._settings.radio_stations = json.dumps(
            [_as_dict(s) for s in stations], ensure_ascii=False
        )

    def _save_overrides(self, overrides: dict[str, dict[str, str]]) -> None:
        self._settings.radio_overrides = json.dumps(overrides, ensure_ascii=False)

    def _save_hidden(self, hidden: set[str]) -> None:
        self._settings.radio_hidden = json.dumps(sorted(hidden), ensure_ascii=False)


def _station_from_dict(item: object) -> RadioStation | None:
    if not isinstance(item, dict):
        return None
    name = str(item.get("name", "")).strip()
    url = str(item.get("url", "")).strip()
    if not name or not url:
        return None
    return RadioStation(
        name=name,
        url=url,
        genre=str(item.get("genre", "")).strip(),
        country=str(item.get("country", "")).strip(),
    )


def _clean(station: RadioStation) -> RadioStation:
    return RadioStation(station.name, station.url, station.genre, station.country)


def _as_dict(station: RadioStation) -> dict[str, str]:
    return {
        "name": station.name,
        "url": station.url,
        "genre": station.genre,
        "country": station.country,
    }
