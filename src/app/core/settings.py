"""Persistencia de estado con QSettings.

Ubicación nativa por SO (RNF): Linux ``~/.config/PyAmp/PyAmp.conf``,
Windows registro/AppData, macOS ``~/Library/Preferences``. Usa el formato
nativo del SO por comodidad con el gestor de configuración del escritorio.

En la Fase 1 se guardan: volumen, silencio, playlist, pista actual,
geometría de ventana y las claves de notificaciones (el diálogo de Ajustes
llega en la Fase 3; aquí las claves ya existen y se respetan).
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QByteArray, QSettings

from app.utils.paths import APP_NAME

# ------------------------------------------------------------------ claves
KEY_VOLUME = "playback/volume"
KEY_MUTED = "playback/muted"
KEY_PLAYLIST_PATHS = "playlist/paths"
KEY_PLAYLIST_INDEX = "playlist/current_index"
KEY_NOTIFICATIONS_ENABLED = "notifications/enabled"
KEY_NOTIFICATIONS_TIMEOUT_MS = "notifications/timeout_ms"
KEY_WINDOW_GEOMETRY = "window/geometry"

DEFAULT_VOLUME = 100
DEFAULT_TIMEOUT_MS = 5000
MIN_TIMEOUT_MS = 1000
MAX_TIMEOUT_MS = 60000


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
    """Fachada tipada sobre :class:`QSettings` de PyAmp."""

    def __init__(self) -> None:
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


_instance: Settings | None = None


def get_settings() -> Settings:
    """Singleton perezoso de :class:`Settings` (tras crear QApplication)."""
    global _instance
    if _instance is None:
        _instance = Settings()
    return _instance
