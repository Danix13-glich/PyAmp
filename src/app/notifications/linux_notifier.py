from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import html
import logging
import threading
from collections.abc import Callable
from typing import Any

from dbus_next import BusType, Message, MessageType, Variant

logger = logging.getLogger(__name__)

DESTINATION = "org.freedesktop.Notifications"
OBJECT_PATH = "/org/freedesktop/Notifications"
INTERFACE = "org.freedesktop.Notifications"

#: Firma de Notify: s app_name, u replaces_id, s app_icon, s summary,
#: s body, as actions, a{sv} hints, i expire_timeout.
NOTIFY_SIGNATURE = "susssasa{sv}i"


def _image_data(image_path: str) -> list[Any] | None:
    try:
        from PySide6.QtGui import QImage

        image = QImage(image_path)
        if image.isNull():
            return None
        image = image.convertToFormat(QImage.Format.Format_RGBA8888)
        # dbus-next exige una lista (no una tupla) para los STRUCT.
        return [
            image.width(),
            image.height(),
            image.bytesPerLine(),
            True,
            8,
            4,
            bytes(image.constBits()),
        ]
    except Exception as exc:  # noqa: BLE001 - la carátula es opcional
        logger.debug("No se pudo convertir la carátula %s: %s", image_path, exc)
        return None


class LinuxNotifier:

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._bus: Any = None
        self._ids: list[int] = []  # solo se toca desde el hilo del loop
        self._action_installed = False
        self._pending_actions: dict[int, Callable[[], None]] = {}

    # ------------------------------------------------------------------ API
    def notify(
        self,
        app_name: str,
        title: str,
        body: str,
        timeout_ms: int = 5000,
        image_path: str | None = None,
    ) -> None:
        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(
            self._notify_async(app_name, title, body, timeout_ms, image_path), loop
        )
        future.add_done_callback(self._log_result)

    def notify_action(
        self,
        app_name: str,
        title: str,
        body: str,
        action_label: str,
        on_action: Callable[[], None] | None = None,
        timeout_ms: int = 0,
        image_path: str | None = None,
    ) -> None:
        # Notificación con acción: al pulsarla llega ActionInvoked → se ejecuta
        # `on_action` (marshaling fuera del hilo de UI: el receptor usa señales).
        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(
            self._notify_async(
                app_name,
                title,
                body,
                timeout_ms,
                image_path,
                actions=["default", action_label],
                on_action=on_action,
            ),
            loop,
        )
        future.add_done_callback(self._log_result)

    def close_all(self) -> None:
        if self._loop is None:
            return
        # Si el loop ya se cerró al salir de la app, RuntimeError: se ignora.
        with contextlib.suppress(RuntimeError):
            asyncio.run_coroutine_threadsafe(self._close_all_async(), self._loop)

    # ------------------------------------------------------------ internas
    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(
                target=self._loop.run_forever, name="pyamp-notifier", daemon=True
            )
            self._thread.start()
        return self._loop

    async def _get_bus(self) -> Any:
        if self._bus is None:
            from dbus_next.aio import MessageBus

            self._bus = await MessageBus(bus_type=BusType.SESSION).connect()
            logger.debug("Notifier: conectado al bus de sesión D-Bus")
        return self._bus

    async def _notify_async(
        self,
        app_name: str,
        title: str,
        body: str,
        timeout_ms: int,
        image_path: str | None,
        actions: list[str] | None = None,
        on_action: Callable[[], None] | None = None,
    ) -> None:
        hints: dict[str, Variant] = {
            # Silenciosa: nunca reproduce sonido propio.
            "suppress-sound": Variant("b", True),
        }
        if image_path:
            data = _image_data(image_path)
            if data is not None:
                hints["image-data"] = Variant("(iiibiiay)", data)

        message = Message(
            destination=DESTINATION,
            path=OBJECT_PATH,
            interface=INTERFACE,
            member="Notify",
            signature=NOTIFY_SIGNATURE,
            body=[
                app_name,
                0,  # replaces_id: 0 = notificación nueva
                "",  # app_icon: usamos image-data, no icono del sistema
                html.escape(title),
                html.escape(body),
                actions or [],  # acciones (p. ej. clic para abrir algo)
                hints,
                int(timeout_ms),
            ],
        )
        bus = await self._get_bus()
        if actions:
            self._install_action_handler(bus)
        reply = await bus.call(message)
        if reply is None:
            raise RuntimeError("sin respuesta del servidor de notificaciones")
        if reply.message_type == MessageType.ERROR:
            self._bus = None  # reconectar en el próximo envío
            raise RuntimeError(reply.error_name or "error D-Bus desconocido")
        if reply.body:
            notification_id = int(reply.body[0])
            self._ids.append(notification_id)
            if actions and on_action is not None:
                self._pending_actions[notification_id] = on_action

    def _install_action_handler(self, bus: Any) -> None:
        if self._action_installed:
            return
        bus.add_message_handler(self._on_message)
        self._action_installed = True

    def _on_message(self, message: Any) -> bool:
        # Escucha ActionInvoked y dispara el callback de la notificación.
        if message.message_type != MessageType.SIGNAL:
            return False
        if message.interface != INTERFACE or message.member != "ActionInvoked":
            return False
        try:
            notification_id = int(message.body[0])
        except (IndexError, TypeError, ValueError):
            return False
        callback = self._pending_actions.pop(notification_id, None)
        if callback is not None:
            try:
                callback()
            except Exception as exc:  # noqa: BLE001 - una acción no debe romper nada
                logger.warning("Acción de notificación falló: %s", exc)
        return False

    async def _close_all_async(self) -> None:
        try:
            bus = await self._get_bus()
            while self._ids:
                notification_id = self._ids.pop()
                await bus.call(
                    Message(
                        destination=DESTINATION,
                        path=OBJECT_PATH,
                        interface=INTERFACE,
                        member="CloseNotification",
                        signature="u",
                        body=[notification_id],
                    )
                )
        except Exception as exc:  # noqa: BLE001 - cierre best-effort
            logger.debug("close_all: %s", exc)

    @staticmethod
    def _log_result(future: concurrent.futures.Future[None]) -> None:
        try:
            future.result()
        except Exception as exc:  # noqa: BLE001
            logger.error("Notificación D-Bus falló: %s", exc)
