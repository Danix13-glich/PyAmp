"""Notificaciones de escritorio de PyAmp.

Este módulo es el ÚNICO punto del programa que lanza notificaciones de
escritorio. Tanto el player como los widgets deben emitir la señal global
`track_changed(track)` y dejar que el `Notifier` reaccione; está prohibido
lanzar notificaciones desde widgets o desde el player de forma directa.

Reglas del proyecto:
    * Se notifica SOLO cuando cambia la pista actual (nunca en pause/play
      de la misma pista): la detección la hace quien emita `track_changed`.
    * El formato vive EXCLUSIVAMENTE en `format_track_notification`. Si
      mañana hay que cambiar el orden o añadir el álbum, se toca ahí.
    * Las notificaciones no deben bloquear el hilo de UI: cualquier backend
      que espere debe hacerlo fuera del hilo principal (hilo propio o
      fire-and-forget).
    * Si un backend falla, se registra en el log y la reproducción sigue.
    * Respetan "No molestar" cuando el backend lo permite y son silenciosas.

Uso típico (conectado en Fase 1 a `core.player`):

    notifier = Notifier()
    player.track_changed.connect(notifier.notify_track)
"""

from __future__ import annotations

import logging
import platform
from pathlib import Path
from typing import Any

from app.i18n import tr

logger = logging.getLogger(__name__)

# Duración por defecto en segundos (configurable en Ajustes -> Notificaciones).
DEFAULT_TIMEOUT_MS = 5000

UNKNOWN_ARTIST_TEXT = "Artista desconocido"


def _fallback_title(track: Any) -> str:
    """Deriva un título usable cuando los metadatos no existen.

    Reglas:
        * Si hay `title`, se usa tal cual.
        * Si no, se usa el nombre del archivo sin extensión (`path`).
        * Si no hay nada, "Sin título".

    Args:
        track: Objeto con atributos `title` y/o `path` (puede ser un dataclass,
            un dict o un SimpleNamespace).

    Returns:
        Texto de título nunca vacío.
    """
    title = track.get("title") if isinstance(track, dict) else getattr(track, "title", None)
    if title:
        return str(title)

    path = track.get("path") if isinstance(track, dict) else getattr(track, "path", None)
    if path:
        return Path(str(path)).stem or tr("Sin título")

    return tr("Sin título")


def format_track_notification(track: Any) -> tuple[str, str, str]:
    """Formatea la notificación de cambio de pista.

    FUNCIÓN ÚNICA DE FORMATO. Devuelve la terna exacta que se muestra al
    usuario en todas las plataformas:

        ┌──────────────────────────────┐
        │  PyAmp                       │  <- app_name
        │  Título de la canción        │  <- title
        │  Nombre del autor            │  <- body
        └──────────────────────────────┘

    Args:
        track: Pista actual. Debe exponer `title`, `artist` y `path` (por
            ejemplo `app.library.models.Track`). También acepta un dict.

    Returns:
        Tupla `(app_name, title, body)`:
            * app_name: "PyAmp".
            * title: título de la pista o nombre del archivo sin extensión.
            * body: artista o "Artista desconocido".
    """
    if isinstance(track, dict):
        artist = track.get("artist")
        path = track.get("path")
    else:
        artist = getattr(track, "artist", None)
        path = getattr(track, "path", None)

    title = _fallback_title(track)
    body = str(artist).strip() if artist else tr(UNKNOWN_ARTIST_TEXT)

    # Detección de "desconocido": strings vacíos o marcadores habituales.
    if not body or body.lower() in {"unknown artist", "(unknown)", "-", "none"}:
        body = tr(UNKNOWN_ARTIST_TEXT)

    logger.debug("format_track_notification: path=%r title=%r body=%r", path, title, body)
    return ("PyAmp", title, body)


class Notifier:
    """Fachada de notificaciones de escritorio, multiplataforma.

    Elige el backend según `platform.system()` y, si el backend primario
    falla, intenta `plyer` como fallback universal. Cualquier error se
    registra en el log y NO interrumpe la reproducción.
    """

    def __init__(self, timeout_ms: int = DEFAULT_TIMEOUT_MS, enabled: bool = True) -> None:
        """Inicializa el notifier.

        Args:
            timeout_ms: Duración de la notación en milisegundos.
            enabled: Si es False, `notify_track` no hace nada (Ajustes →
                Notificaciones → desactivar).
        """
        self.timeout_ms = timeout_ms
        self.enabled = enabled
        self._backend_name = "none"
        self._init_backend()

    def _init_backend(self) -> None:
        """Selecciona el backend según SO, con fallback a plyer.

        No lanza excepciones: si todo falla, se queda en `none` y las
        notificaciones se convierten en no-op (la app sigue funcionando).
        """
        system = platform.system()
        try:
            if system == "Linux":
                from .linux_notifier import LinuxNotifier

                self._backend: Any = LinuxNotifier()
                self._backend_name = "linux-dbus"
            elif system == "Windows":
                from .windows_notifier import WindowsNotifier

                self._backend = WindowsNotifier()
                self._backend_name = "windows-toast"
            elif system == "Darwin":
                from .macos_notifier import MacOSNotifier

                self._backend = MacOSNotifier()
                self._backend_name = "macos-notification"
            else:
                raise RuntimeError(f"SO no soportado: {system}")
        except Exception as exc:  # noqa: BLE001 - queremos capturar TODO y seguir
            logger.warning(
                "Backend de notificaciones no disponible (%s); usando fallback/none", exc
            )
            self._backend = None
            self._backend_name = "none"
            self._try_plyer_fallback()

    def _try_plyer_fallback(self) -> None:
        """Intenta registrar plyer como backend de último recurso."""
        try:
            from plyer import notification  # noqa: F401

            self._backend = "plyer"
            self._backend_name = "plyer"
            logger.info("Notifier: usando fallback plyer")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Notifier: fallback plyer no disponible (%s)", exc)

    @property
    def backend_name(self) -> str:
        """Nombre del backend activo (útil para diagnóstico y tests)."""
        return self._backend_name

    def notify_track(self, track: Any) -> None:
        """Lanza la notificación de cambio de pista.

        Debe llamarse SOLO ante un cambio real de pista (señal
        `track_changed`), nunca en pause/play de la misma pista.

        Args:
            track: Pista actual; se formatea con `format_track_notification`.
        """
        if not self.enabled:
            logger.debug("Notifier desactivado en Ajustes; se omite notificación")
            return

        try:
            app_name, title, body = format_track_notification(track)
        except Exception as exc:  # noqa: BLE001
            logger.error("Error formateando notificación: %s", exc)
            return

        # Carátula (Fase 1: Linux la muestra vía hint image-data; los demás
        # backends la ignoran hasta que la implementen).
        if isinstance(track, dict):
            image_path = track.get("cover_path")
        else:
            image_path = getattr(track, "cover_path", None)
        if image_path and not Path(str(image_path)).is_file():
            image_path = None

        try:
            self._send(app_name, title, body, str(image_path) if image_path else None)
        except Exception as exc:  # noqa: BLE001
            # Regla de oro: la notificación jamás interrumpe la reproducción.
            logger.error("Error enviando notificación (backend=%s): %s", self._backend_name, exc)

    def _send(self, app_name: str, title: str, body: str, image_path: str | None = None) -> None:
        """Despacha la notificación al backend activo.

        Args:
            app_name: Nombre de la app ("PyAmp").
            title: Título de la notificación.
            body: Cuerpo de la notificación.
            image_path: Ruta de la carátula o None si no hay.
        """
        if self._backend is None:
            logger.debug("Sin backend de notificaciones; se omite: %r / %r", title, body)
            return

        if self._backend == "plyer":
            from plyer import notification

            notification.notify(
                title=f"{app_name} — {title}",
                message=body,
                app_name=app_name,
                timeout=self.timeout_ms // 1000,
            )
            return

        # Backends propios (Linux/Windows/macOS) implementan notify().
        self._backend.notify(
            app_name=app_name,
            title=title,
            body=body,
            timeout_ms=self.timeout_ms,
            image_path=image_path,
        )

    def notify(self, title: str, body: str) -> None:
        """Lanza una notificación genérica (no de pista).

        Útil para avisos puntuales (p. ej. "Playlist guardada"). No usar
        para cambios de pista: eso va por `notify_track`.

        Args:
            title: Título.
            body: Cuerpo.
        """
        if not self.enabled:
            return
        try:
            self._send("PyAmp", title, body, None)
        except Exception as exc:  # noqa: BLE001
            logger.error("Error en notificación genérica: %s", exc)

    def close_all(self) -> None:
        """Cierra las notificaciones pendientes si el backend lo soporta.

        Best-effort: si el backend no expone cierre, se registra en debug y
        no hace nada. Nunca lanza excepciones hacia el llamante.
        """
        if self._backend is None or self._backend == "plyer":
            return
        try:
            closer = getattr(self._backend, "close_all", None)
            if callable(closer):
                closer()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error cerrando notificaciones: %s", exc)
