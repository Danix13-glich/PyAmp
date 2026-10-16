"""Notificador para Windows — STUB (implementación real en la Fase 8).

La Fase 1 solo exige el backend de Linux; aquí se registra la intención y
la app continúa sin notificaciones en Windows (nunca crashea).

Fase 8: sustituir por ``windows-toasts`` (WinRT, Windows 10/11) con imagen
de carátula e ignorando "No molestar" del centro de notificaciones.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class WindowsNotifier:
    """Backend Windows (stub hasta la Fase 8)."""

    def notify(
        self,
        app_name: str,
        title: str,
        body: str,
        timeout_ms: int = 5000,
        image_path: str | None = None,
    ) -> None:
        """TODO(Fase 8): notificación toast nativa con windows-toasts.

        Args:
            app_name: Nombre de la app.
            title: Título.
            body: Cuerpo.
            timeout_ms: Duración en ms.
            image_path: Carátula o None.
        """
        logger.info(
            "[stub Windows — Fase 8] %s / %s / %s (timeout=%dms, imagen=%s)",
            app_name,
            title,
            body,
            timeout_ms,
            image_path or "no",
        )

    def close_all(self) -> None:
        """TODO(Fase 8): cerrar toasts pendientes si la librería lo permite."""
        logger.debug("[stub Windows] close_all")
