"""Notificador para macOS — STUB (implementación real en la Fase 8).

La Fase 1 solo exige el backend de Linux; aquí se registra la intención y
la app continúa sin notificaciones en macOS (nunca crashea).

Fase 8: sustituir por ``pync`` (Notification Center) o ``osascript`` con
carátula e integración con "No molestar".
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class MacOSNotifier:
    """Backend macOS (stub hasta la Fase 8)."""

    def notify(
        self,
        app_name: str,
        title: str,
        body: str,
        timeout_ms: int = 5000,
        image_path: str | None = None,
    ) -> None:
        """TODO(Fase 8): notificación nativa de Notification Center.

        Args:
            app_name: Nombre de la app.
            title: Título.
            body: Cuerpo.
            timeout_ms: Duración en ms.
            image_path: Carátula o None.
        """
        logger.info(
            "[stub macOS — Fase 8] %s / %s / %s (timeout=%dms, imagen=%s)",
            app_name,
            title,
            body,
            timeout_ms,
            image_path or "no",
        )

    def close_all(self) -> None:
        """TODO(Fase 8): retirar notificaciones del centro de notificaciones."""
        logger.debug("[stub macOS] close_all")
