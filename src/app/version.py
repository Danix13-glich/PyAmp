"""Metadatos de versión de PyAmp.

Fuente única de verdad de la versión (SemVer). Se usa en el título de la
ventana, en "Acerca de", en los metadatos de paquetes y en la CI.

El número debe coincidir con `project.version` en pyproject.toml y con la
tag de release (vX.Y.Z).
"""

from __future__ import annotations

__version__ = "0.1.0"
__app_name__ = "PyAmp"
__app_id__ = "org.pyamp.PyAmp"  # id de escritorio y notificaciones (freedesktop)
