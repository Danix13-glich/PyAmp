"""Persistencia de estado con QSettings.

Ubicación nativa por SO (RNF): Linux ``~/.config/PyAmp/PyAmp.conf``,
Windows registro/AppData, macOS ``~/Library/Preferences``. Usa el formato
nativo del SO por comodidad con el gestor de configuración del escritorio.

En la Fase 1 se guardan: volumen, silencio, playlist, pista actual,
geometría de ventana y las claves de notificaciones (el diálogo de Ajustes
llega en la Fase 3; aquí las claves ya existen y se respetan).
"""

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
KEY_VIEW_MODE = "ui/view_mode"
KEY_SHOW_SPECTRUM = "ui/show_spectrum"
KEY_SHOW_COVER = "ui/show_cover"
KEY_THEME = "ui/theme"
KEY_LANGUAGE = "ui/language"
KEY_SHORTCUTS = "shortcuts/custom"
KEY_LIBRARY_FOLDERS = "library/folders"

DEFAULT_VOLUME = 100
DEFAULT_TIMEOUT_MS = 5000
MIN_TIMEOUT_MS = 1000
MAX_TIMEOUT_MS = 60000

#: Vistas posibles del menú Ver (Fase 4; Favoritos añadido en 0.1.6).
VIEW_CANCIONES = "canciones"
VIEW_BIBLIOTECA = "biblioteca"
VIEW_FAVORITOS = "favoritos"
VIEW_MODES = {VIEW_CANCIONES, VIEW_BIBLIOTECA, VIEW_FAVORITOS}
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
    "view_biblioteca": "Ctrl+2",
    "view_favoritos": "Ctrl+3",
    "open_files": "Ctrl+O",
    "open_folder": "Ctrl+Shift+O",
    "load_playlist": "Ctrl+Shift+L",
    "save_playlist": "Ctrl+Shift+S",
    "settings": "Ctrl+,",
    "quit": "Ctrl+Q",
}


def _as_bool(value: Any, default: bool) -> bool:
    """Convierte valores de QSettings (bool, int, str) a bool de forma segura."""
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
    """Fachada tipada sobre :class:`QSettings` de PyAmp.

    Args:
        path: Ruta explícita del archivo ``.conf`` (formato INI). Es la
            forma **fiable** de aislar en tests: ``QSettings`` cachea la
            ruta de configuración del sistema por proceso, así que
            cambiar ``XDG_CONFIG_HOME`` después de crear el primer
            ``QSettings`` NO aísla nada (ver NOTA_SIGUIENTE_MODELO.md).
            Si es ``None`` (uso normal), se usa la configuración nativa
            del SO (``~/.config/PyAmp/PyAmp.conf`` en Linux).
    """

    def __init__(self, path: str | Path | None = None) -> None:
        if path is not None:
            self._settings = QSettings(str(path), QSettings.Format.IniFormat)
        else:
            self._settings = QSettings(APP_NAME, APP_NAME)

    # ------------------------------------------------------------- genérico
    def value(self, key: str, default: Any = None) -> Any:
        """Lee un valor crudo."""
        return self._settings.value(key, default)

    def _raw(self, key: str, default: Any = None) -> Any:
        """Lectura interna tipada como Any (los stubs de QSettings devuelven object)."""
        return self._settings.value(key, default)

    def set_value(self, key: str, value: Any) -> None:
        """Escribe un valor y sincroniza el disco."""
        self._settings.setValue(key, value)
        self._settings.sync()

    def sync(self) -> None:
        """Fuerza la escritura a disco."""
        self._settings.sync()

    # ------------------------------------------------------------- playback
    @property
    def volume(self) -> int:
        """Volumen 0..100."""
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
        """True si el audio estaba silenciado al cerrar."""
        return _as_bool(self._raw(KEY_MUTED, False), False)

    @muted.setter
    def muted(self, value: bool) -> None:
        self.set_value(KEY_MUTED, bool(value))

    @property
    def shuffle(self) -> bool:
        """True si el modo aleatorio estaba activo (🔀)."""
        return _as_bool(self._raw(KEY_SHUFFLE, False), False)

    @shuffle.setter
    def shuffle(self, value: bool) -> None:
        self.set_value(KEY_SHUFFLE, bool(value))

    @property
    def repeat(self) -> bool:
        """True si la repetición de playlist estaba activa (🔁 = 1)."""
        return _as_bool(self._raw(KEY_REPEAT, False), False)

    @repeat.setter
    def repeat(self, value: bool) -> None:
        self.set_value(KEY_REPEAT, bool(value))

    # ---------------------------------------------------------- notificaciones
    @property
    def notifications_enabled(self) -> bool:
        """Ajuste → Notificaciones → activar/desactivar (diálogo en Fase 3)."""
        return _as_bool(self._raw(KEY_NOTIFICATIONS_ENABLED, True), True)

    @notifications_enabled.setter
    def notifications_enabled(self, value: bool) -> None:
        self.set_value(KEY_NOTIFICATIONS_ENABLED, bool(value))

    @property
    def notifications_timeout_ms(self) -> int:
        """Duración de la notificación en ms (5 s por defecto, 1–60 s)."""
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
        """Rutas de la playlist guardada al cerrar."""
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
        """Índice de la pista seleccionada al cerrar."""
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
        """Geometría de la ventana principal (None la primera vez)."""
        value = self._settings.value(KEY_WINDOW_GEOMETRY)
        if isinstance(value, QByteArray):
            return value
        return None

    @window_geometry.setter
    def window_geometry(self, geometry: QByteArray) -> None:
        self.set_value(KEY_WINDOW_GEOMETRY, geometry)

    @property
    def view_mode(self) -> str:
        """Vista activa del menú Ver: «canciones» (tabla) o «biblioteca»."""
        raw = self._raw(KEY_VIEW_MODE, DEFAULT_VIEW_MODE)
        value = str(raw).strip().lower() if raw is not None else ""
        return value if value in VIEW_MODES else DEFAULT_VIEW_MODE

    @view_mode.setter
    def view_mode(self, value: str) -> None:
        if value in VIEW_MODES:
            self.set_value(KEY_VIEW_MODE, value)

    @property
    def show_spectrum(self) -> bool:
        """True si el espectrograma se muestra (menú Ver)."""
        return _as_bool(self._raw(KEY_SHOW_SPECTRUM, True), True)

    @show_spectrum.setter
    def show_spectrum(self, value: bool) -> None:
        self.set_value(KEY_SHOW_SPECTRUM, bool(value))

    @property
    def show_cover(self) -> bool:
        """True si la carátula se muestra en la cabecera (menú Ver)."""
        return _as_bool(self._raw(KEY_SHOW_COVER, True), True)

    @show_cover.setter
    def show_cover(self, value: bool) -> None:
        self.set_value(KEY_SHOW_COVER, bool(value))

    @property
    def theme_id(self) -> str:
        """Id del tema visual (Ajustes → Apariencia / Ver → Temas)."""
        raw = self._raw(KEY_THEME, "")
        return str(raw).strip() if raw is not None else ""

    @theme_id.setter
    def theme_id(self, value: str) -> None:
        self.set_value(KEY_THEME, str(value).strip())

    @property
    def language(self) -> str:
        """Código de idioma de la interfaz («es» o «en»).

        Se elige en Ajustes → General y se aplica al reiniciar la app. Un
        valor desconocido o vacío cae al idioma por defecto (español).
        """
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
        """Carpetas escaneadas en la biblioteca (raíces recordadas).

        «Refrescar canciones» re-escanea TODAS estas carpetas en orden;
        se recordará cada carpeta que se escanee con éxito.
        """
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
        """Atajos personalizados (id de atajo → secuencia portable).

        Solo se guardan los que difieren de su valor por defecto: un id
        ausente significa «usa el valor por defecto». Se serializan como
        JSON en una única clave para que el ``.conf`` siga siendo legible.
        """
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


_instance: Settings | None = None


def get_settings() -> Settings:
    """Singleton perezoso de :class:`Settings` (tras crear QApplication)."""
    global _instance
    if _instance is None:
        _instance = Settings()
    return _instance
