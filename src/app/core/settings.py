from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtCore import QByteArray, QSettings

from app.i18n import DEFAULT_LANGUAGE, LANGUAGES
from app.utils.paths import APP_NAME

# ------------------------------------------------------------------ claves
KEY_VOLUME = "playback/volume"
KEY_MUTED = "playback/muted"
KEY_SHUFFLE = "playback/shuffle"
KEY_REPEAT = "playback/repeat"
KEY_PLAYLIST_PATHS = "playlist/paths"
KEY_PLAYLIST_INDEX = "playlist/current_index"
KEY_NOTIFICATIONS_ENABLED = "notifications/enabled"
KEY_NOTIFICATIONS_TIMEOUT_MS = "notifications/timeout_ms"
KEY_WINDOW_GEOMETRY = "window/geometry"
KEY_WINDOW_WIDTH = "window/default_width"
KEY_WINDOW_HEIGHT = "window/default_height"
KEY_VIEW_MODE = "ui/view_mode"
KEY_SHOW_SPECTRUM = "ui/show_spectrum"
KEY_SHOW_COVER = "ui/show_cover"
KEY_SHOW_HIDDEN = "ui/show_hidden"
KEY_THEME = "ui/theme"
KEY_LANGUAGE = "ui/language"
KEY_SHORTCUTS = "shortcuts/custom"
KEY_LIBRARY_FOLDERS = "library/folders"
KEY_RADIO_STATIONS = "radio/stations"
KEY_RADIO_OVERRIDES = "radio/overrides"
KEY_RADIO_HIDDEN = "radio/hidden"
KEY_RADIO_FOUND = "radio/found"
KEY_HISTORY_NOTIFIED = "history/notified_month"

DEFAULT_VOLUME = 100
DEFAULT_TIMEOUT_MS = 5000
MIN_TIMEOUT_MS = 1000
MAX_TIMEOUT_MS = 60000

#: Tamaño por defecto de la ventana principal (Ajustes → Apariencia).
DEFAULT_WINDOW_WIDTH = 630
DEFAULT_WINDOW_HEIGHT = 485
MIN_WINDOW_WIDTH = 480
MAX_WINDOW_WIDTH = 3840
MIN_WINDOW_HEIGHT = 360
MAX_WINDOW_HEIGHT = 2160

#: Vistas posibles del menú Ver.
VIEW_CANCIONES = "canciones"
VIEW_FAVORITOS = "favoritos"
VIEW_RADIO = "radio"
VIEW_MODES = {VIEW_CANCIONES, VIEW_FAVORITOS, VIEW_RADIO}
DEFAULT_VIEW_MODE = VIEW_CANCIONES

#: Atajos personalizables (Ajustes → Atajos): id → secuencia por defecto.
#: Solo los IDs de esta tabla se pueden reasignar; las teclas multimedia
#: del hardware quedan fijas (no tienen representación portable).
SHORTCUT_DEFAULTS: dict[str, str] = {
    "prev": "F9",
    "play_pause": "F10",
    "next": "F11",
    "lyrics": "Ctrl+L",
    "view_canciones": "Ctrl+1",
    "view_favoritos": "Ctrl+2",
    "view_radio": "Ctrl+3",
    "open_files": "Ctrl+O",
    "open_folder": "Ctrl+Shift+O",
    "load_playlist": "Ctrl+Shift+L",
    "save_playlist": "Ctrl+Shift+S",
    "settings": "Ctrl+,",
    "quit": "Ctrl+Q",
}


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off", ""}:
            return False
    return default


class Settings:

    def __init__(self, path: str | Path | None = None) -> None:
        if path is not None:
            self._settings = QSettings(str(path), QSettings.Format.IniFormat)
        else:
            self._settings = QSettings(APP_NAME, APP_NAME)

    # ------------------------------------------------------------- genérico
    def value(self, key: str, default: Any = None) -> Any:
        return self._settings.value(key, default)

    def _raw(self, key: str, default: Any = None) -> Any:
        return self._settings.value(key, default)

    def set_value(self, key: str, value: Any) -> None:
        self._settings.setValue(key, value)
        self._settings.sync()

    def sync(self) -> None:
        self._settings.sync()

    # ------------------------------------------------------------- playback
    @property
    def volume(self) -> int:
        try:
            value = int(self._raw(KEY_VOLUME, DEFAULT_VOLUME))
        except (TypeError, ValueError):
            value = DEFAULT_VOLUME
        return max(0, min(100, value))

    @volume.setter
    def volume(self, value: int) -> None:
        self.set_value(KEY_VOLUME, max(0, min(100, int(value))))

    @property
    def muted(self) -> bool:
        return _as_bool(self._raw(KEY_MUTED, False), False)

    @muted.setter
    def muted(self, value: bool) -> None:
        self.set_value(KEY_MUTED, bool(value))

    @property
    def shuffle(self) -> bool:
        return _as_bool(self._raw(KEY_SHUFFLE, False), False)

    @shuffle.setter
    def shuffle(self, value: bool) -> None:
        self.set_value(KEY_SHUFFLE, bool(value))

    @property
    def repeat(self) -> bool:
        return _as_bool(self._raw(KEY_REPEAT, False), False)

    @repeat.setter
    def repeat(self, value: bool) -> None:
        self.set_value(KEY_REPEAT, bool(value))

    # ---------------------------------------------------------- notificaciones
    @property
    def notifications_enabled(self) -> bool:
        return _as_bool(self._raw(KEY_NOTIFICATIONS_ENABLED, True), True)

    @notifications_enabled.setter
    def notifications_enabled(self, value: bool) -> None:
        self.set_value(KEY_NOTIFICATIONS_ENABLED, bool(value))

    @property
    def notifications_timeout_ms(self) -> int:
        try:
            value = int(self._raw(KEY_NOTIFICATIONS_TIMEOUT_MS, DEFAULT_TIMEOUT_MS))
        except (TypeError, ValueError):
            value = DEFAULT_TIMEOUT_MS
        return max(MIN_TIMEOUT_MS, min(MAX_TIMEOUT_MS, value))

    @notifications_timeout_ms.setter
    def notifications_timeout_ms(self, value: int) -> None:
        self.set_value(
            KEY_NOTIFICATIONS_TIMEOUT_MS, max(MIN_TIMEOUT_MS, min(MAX_TIMEOUT_MS, int(value)))
        )

    # ------------------------------------------------------------- playlist
    @property
    def playlist_paths(self) -> list[str]:
        raw = self._raw(KEY_PLAYLIST_PATHS, [])
        if raw is None:
            return []
        if isinstance(raw, str):
            return [raw] if raw else []
        return [str(item) for item in raw]

    @playlist_paths.setter
    def playlist_paths(self, paths: list[str]) -> None:
        self.set_value(KEY_PLAYLIST_PATHS, [str(p) for p in paths])

    @property
    def playlist_index(self) -> int:
        try:
            return max(-1, int(self._raw(KEY_PLAYLIST_INDEX, -1)))
        except (TypeError, ValueError):
            return -1

    @playlist_index.setter
    def playlist_index(self, index: int) -> None:
        self.set_value(KEY_PLAYLIST_INDEX, int(index))

    # --------------------------------------------------------------- ventana
    @property
    def window_geometry(self) -> QByteArray | None:
        value = self._settings.value(KEY_WINDOW_GEOMETRY)
        if isinstance(value, QByteArray):
            return value
        return None

    @window_geometry.setter
    def window_geometry(self, geometry: QByteArray) -> None:
        self.set_value(KEY_WINDOW_GEOMETRY, geometry)

    @property
    def window_width(self) -> int:
        return self._clamp_int(
            KEY_WINDOW_WIDTH, DEFAULT_WINDOW_WIDTH, MIN_WINDOW_WIDTH, MAX_WINDOW_WIDTH
        )

    @window_width.setter
    def window_width(self, value: int) -> None:
        self.set_value(KEY_WINDOW_WIDTH, max(MIN_WINDOW_WIDTH, min(MAX_WINDOW_WIDTH, int(value))))

    @property
    def window_height(self) -> int:
        return self._clamp_int(
            KEY_WINDOW_HEIGHT, DEFAULT_WINDOW_HEIGHT, MIN_WINDOW_HEIGHT, MAX_WINDOW_HEIGHT
        )

    @window_height.setter
    def window_height(self, value: int) -> None:
        self.set_value(
            KEY_WINDOW_HEIGHT, max(MIN_WINDOW_HEIGHT, min(MAX_WINDOW_HEIGHT, int(value)))
        )

    def _clamp_int(self, key: str, default: int, minimum: int, maximum: int) -> int:
        try:
            value = int(self._raw(key, default))
        except (TypeError, ValueError):
            value = default
        return max(minimum, min(maximum, value))

    @property
    def view_mode(self) -> str:
        raw = self._raw(KEY_VIEW_MODE, DEFAULT_VIEW_MODE)
        value = str(raw).strip().lower() if raw is not None else ""
        return value if value in VIEW_MODES else DEFAULT_VIEW_MODE

    @view_mode.setter
    def view_mode(self, value: str) -> None:
        if value in VIEW_MODES:
            self.set_value(KEY_VIEW_MODE, value)

    @property
    def show_spectrum(self) -> bool:
        return _as_bool(self._raw(KEY_SHOW_SPECTRUM, True), True)

    @show_spectrum.setter
    def show_spectrum(self, value: bool) -> None:
        self.set_value(KEY_SHOW_SPECTRUM, bool(value))

    @property
    def show_cover(self) -> bool:
        return _as_bool(self._raw(KEY_SHOW_COVER, True), True)

    @show_cover.setter
    def show_cover(self, value: bool) -> None:
        self.set_value(KEY_SHOW_COVER, bool(value))

    @property
    def show_hidden(self) -> bool:
        return _as_bool(self._raw(KEY_SHOW_HIDDEN, False), False)

    @show_hidden.setter
    def show_hidden(self, value: bool) -> None:
        self.set_value(KEY_SHOW_HIDDEN, bool(value))

    @property
    def theme_id(self) -> str:
        raw = self._raw(KEY_THEME, "")
        return str(raw).strip() if raw is not None else ""

    @theme_id.setter
    def theme_id(self, value: str) -> None:
        self.set_value(KEY_THEME, str(value).strip())

    @property
    def language(self) -> str:
        raw = self._raw(KEY_LANGUAGE, DEFAULT_LANGUAGE)
        value = str(raw).strip().lower() if raw is not None else ""
        return value if value in LANGUAGES else DEFAULT_LANGUAGE

    @language.setter
    def language(self, value: str) -> None:
        key = str(value).strip().lower()
        self.set_value(KEY_LANGUAGE, key if key in LANGUAGES else DEFAULT_LANGUAGE)

    # ------------------------------------------------------------ biblioteca
    @property
    def library_folders(self) -> list[str]:
        raw = self._raw(KEY_LIBRARY_FOLDERS, [])
        if raw is None:
            return []
        if isinstance(raw, str):
            return [raw] if raw else []
        return [str(item) for item in raw]

    @library_folders.setter
    def library_folders(self, folders: list[str]) -> None:
        clean: list[str] = []
        for folder in folders:
            text = str(folder).strip()
            if text and text not in clean:
                clean.append(text)
        self.set_value(KEY_LIBRARY_FOLDERS, clean)

    # --------------------------------------------------------------- atajos
    @property
    def shortcuts(self) -> dict[str, str]:
        raw = self._raw(KEY_SHORTCUTS, "")
        if not raw:
            return {}
        try:
            data = json.loads(str(raw))
        except (json.JSONDecodeError, TypeError, ValueError):
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(key): str(value) for key, value in data.items()}

    @shortcuts.setter
    def shortcuts(self, mapping: dict[str, str]) -> None:
        clean = {str(key): str(value) for key, value in mapping.items() if str(key)}
        self.set_value(KEY_SHORTCUTS, json.dumps(clean, ensure_ascii=False, sort_keys=True))

    # ------------------------------------------------------------------ radio
    @property
    def radio_stations(self) -> str:
        raw = self._raw(KEY_RADIO_STATIONS, "")
        return str(raw) if raw else ""

    @radio_stations.setter
    def radio_stations(self, value: str) -> None:
        self.set_value(KEY_RADIO_STATIONS, str(value))

    @property
    def radio_overrides(self) -> str:
        raw = self._raw(KEY_RADIO_OVERRIDES, "")
        return str(raw) if raw else ""

    @radio_overrides.setter
    def radio_overrides(self, value: str) -> None:
        self.set_value(KEY_RADIO_OVERRIDES, str(value))

    @property
    def radio_hidden(self) -> str:
        raw = self._raw(KEY_RADIO_HIDDEN, "")
        return str(raw) if raw else ""

    @radio_hidden.setter
    def radio_hidden(self, value: str) -> None:
        self.set_value(KEY_RADIO_HIDDEN, str(value))

    @property
    def radio_found(self) -> str:
        raw = self._raw(KEY_RADIO_FOUND, "")
        return str(raw) if raw else ""

    @radio_found.setter
    def radio_found(self, value: str) -> None:
        self.set_value(KEY_RADIO_FOUND, str(value))

    # --------------------------------------------------------------- historial
    @property
    def history_notified_month(self) -> str:
        raw = self._raw(KEY_HISTORY_NOTIFIED, "")
        return str(raw) if raw else ""

    @history_notified_month.setter
    def history_notified_month(self, value: str) -> None:
        self.set_value(KEY_HISTORY_NOTIFIED, str(value))


_instance: Settings | None = None


def get_settings() -> Settings:
    global _instance
    if _instance is None:
        _instance = Settings()
    return _instance
