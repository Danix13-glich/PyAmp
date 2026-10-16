#!/usr/bin/env python3
"""Punto de entrada de PyAmp.

Arranca la aplicación Qt. En la Fase 0 abre una QMainWindow vacía con el
título "PyAmp". A partir de la Fase 1 cargará el reproductor completo.

Uso:
    python main.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Garantiza que `src/` esté en sys.path aunque se ejecute desde cualquier
# directorio (imports tipo `from app...`).
_SRC_DIR = Path(__file__).resolve().parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from PySide6.QtWidgets import QApplication, QMainWindow  # noqa: E402

from app.version import __version__  # noqa: E402


def main() -> int:
    """Crea la aplicación Qt y muestra la ventana principal.

    Returns:
        Código de salida del proceso (0 = correcto).
    """
    app = QApplication(sys.argv)
    app.setApplicationName("PyAmp")
    app.setOrganizationName("PyAmp")
    app.setApplicationVersion(__version__)

    window = QMainWindow()
    window.setWindowTitle("PyAmp")
    window.resize(800, 500)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
