#!/usr/bin/env python3

from __future__ import annotations

import logging
import platform
import sys
from pathlib import Path

# Garantiza que `src/` esté en sys.path aunque se ejecute desde cualquier
# directorio (imports tipo `from app...`).
_SRC_DIR = Path(__file__).resolve().parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.core.settings import get_settings  # noqa: E402
from app.i18n import set_language  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402
from app.utils.logging import setup_logging  # noqa: E402
from app.version import __version__  # noqa: E402

logger = logging.getLogger(__name__)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("PyAmp")
    app.setOrganizationName("PyAmp")
    app.setApplicationVersion(__version__)
    app.setDesktopFileName("pyamp")

    icon_path = Path(__file__).resolve().parent / "assets" / "logo.svg"
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Idioma guardado (Ajustes → General) ANTES de construir la interfaz:
    # las dos versiones de los textos viven en app/i18n.py.
    set_language(get_settings().language)

    log_file = setup_logging()
    logger.info(
        "PyAmp %s iniciando (Python %s, %s, log=%s)",
        __version__,
        platform.python_version(),
        platform.platform(),
        log_file,
    )

    window = MainWindow()
    window.show()

    exit_code = app.exec()
    logger.info("PyAmp termina con código %d", exit_code)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
