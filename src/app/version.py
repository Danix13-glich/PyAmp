"""Metadatos de versión de PyAmp.

Fuente única de verdad de la versión. Se usa en el título de la ventana,
en "Acerca de", en los metadatos de paquetes y en la CI.

Política de versionado del proyecto (regla del proyecto, no SemVer):
cada componente MAYOR.MENOR.PARCHE es **un solo dígito** (0–9). Cada
cambio del programa sube el parche; al desbordarse un componente se
reinicia a 0 y sube el siguiente: 0.1.9 → 0.2.0, 0.9.9 → 1.0.0.

El número debe coincidir con `project.version` en pyproject.toml y con
la tag de release (vX.Y.Z).
"""

from __future__ import annotations

__version__ = "0.1.8"
__app_name__ = "PyAmp"
__app_id__ = "org.pyamp.PyAmp"  # id de escritorio y notificaciones (freedesktop)
