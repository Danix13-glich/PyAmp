#!/usr/bin/env python3
"""Punto de entrada de PyAmp.

Arranca logging, la aplicación Qt y la ventana principal (UI mínima de la
Fase 1). La UI definitiva Winamp llega en la Fase 3.

Uso:
    python main.py
"""

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

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.ui.main_window import MainWindow  # noqa: E402
from app.utils.logging import setup_logging  # noqa: E402
from app.version import __version__  # noqa: E402

logger = logging.getLogger(__name__)


def main() -> int:
    """Crea la aplicación Qt y muestra la ventana principal.

    Returns:
        Código de salida del proceso (0 = correcto).
    """
    app = QApplication(sys.argv)
    app.setApplicationName("PyAmp")
    app.setOrganizationName("PyAmp")
    app.setApplicationVersion(__version__)

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
