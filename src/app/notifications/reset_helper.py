from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

HELPER_FLAG = "--notify-reset-helper"


def _app_command() -> list[str]:
    appimage = os.environ.get("APPIMAGE", "").strip()
    if appimage:
        return [appimage]
    if getattr(sys, "frozen", False):
        return [sys.executable]
    root = Path(__file__).resolve().parents[3]
    return [sys.executable, str(root / "main.py")]


def _app_cwd() -> str:
    if os.environ.get("APPIMAGE", "").strip():
        return str(Path.home())
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).resolve().parent)
    return str(Path(__file__).resolve().parents[3])


def _argument(argv: list[str], name: str, default: str) -> str:
    try:
        index = argv.index(name)
    except ValueError:
        return default
    if index + 1 >= len(argv):
        return default
    return argv[index + 1]


def spawn_reset_notification(title: str, body: str, action_label: str) -> bool:
    if not sys.platform.startswith("linux"):
        return False
    command = [
        *_app_command(),
        HELPER_FLAG,
        "--reset-title",
        title,
        "--reset-body",
        body,
        "--reset-action",
        action_label,
    ]
    try:
        subprocess.Popen(
            command,
            cwd=_app_cwd(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except OSError as exc:
        logger.warning("No se pudo iniciar el aviso de reinicio: %s", exc)
        return False
    logger.info("Aviso de reinicio delegado a un proceso auxiliar")
    return True


def _launch_app() -> None:
    try:
        subprocess.Popen(
            _app_command(),
            cwd=_app_cwd(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
            env=os.environ.copy(),
        )
    except OSError as exc:
        logger.warning("No se pudo abrir PyAmp desde la notificación: %s", exc)


def run_reset_notification_helper(argv: list[str]) -> int:
    from app.notifications.linux_notifier import LinuxNotifier

    title = _argument(argv, "--reset-title", "PyAmp se ha restablecido")
    body = _argument(argv, "--reset-body", "Abre de nuevo PyAmp para continuar.")
    action_label = _argument(argv, "--reset-action", "Abrir PyAmp")
    finished = threading.Event()

    def on_action() -> None:
        _launch_app()
        finished.set()

    def on_closed() -> None:
        finished.set()

    notifier = LinuxNotifier()
    notifier.notify_action(
        app_name="PyAmp",
        title=title,
        body=body,
        action_label=action_label,
        on_action=on_action,
        on_closed=on_closed,
        timeout_ms=0,
    )
    finished.wait(timeout=3600)
    return 0
