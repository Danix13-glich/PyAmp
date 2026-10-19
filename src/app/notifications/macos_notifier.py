from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class MacOSNotifier:

    def notify(
        self,
        app_name: str,
        title: str,
        body: str,
        timeout_ms: int = 5000,
        image_path: str | None = None,
    ) -> None:
        logger.info(
            "[stub macOS] %s / %s / %s (timeout=%dms, imagen=%s)",
            app_name,
            title,
            body,
            timeout_ms,
            image_path or "no",
        )

    def close_all(self) -> None:
        logger.debug("[stub macOS] close_all")
