"""Configuración común de la batería de tests.

Aísla la configuración: **ningún test debe leer ni escribir la QSettings
real del usuario** (``~/.config/PyAmp/PyAmp.conf``).

``QSettings`` cachea la ruta de configuración del sistema por proceso, así
que cambiar ``XDG_CONFIG_HOME`` después de crear el primer ``QSettings``
NO aísla nada. La forma fiable es inyectar un archivo ``.conf`` temporal:

* los tests que crean su propio ``Settings`` pasan ``path=`` explícito;
* los que usan el singleton :func:`app.core.settings.get_settings` quedan
  redirigidos aquí a un archivo temporal por test.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

import app.core.settings as settings_module
from app.i18n import DEFAULT_LANGUAGE, set_language


@pytest.fixture(autouse=True)
def isolated_qsettings(tmp_path: Path) -> Iterator[settings_module.Settings]:
    """Redirige el singleton de Settings a un ``.conf`` temporal por test."""
    isolated = settings_module.Settings(tmp_path / "PyAmp-test.conf")
    previous = settings_module._instance
    settings_module._instance = isolated
    try:
        yield isolated
    finally:
        settings_module._instance = previous


@pytest.fixture(autouse=True)
def isolated_language() -> Iterator[None]:
    """El idioma activo vuelve al español después de cada test.

    El idioma es estado global del módulo ``app.i18n``; sin esto, un test
    que pase a inglés dejaría en inglés los textos del siguiente.
    """
    set_language(DEFAULT_LANGUAGE)
    try:
        yield
    finally:
        set_language(DEFAULT_LANGUAGE)
