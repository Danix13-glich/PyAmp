from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

import app.core.settings as settings_module
from app.i18n import DEFAULT_LANGUAGE, set_language


@pytest.fixture(autouse=True)
def isolated_qsettings(tmp_path: Path) -> Iterator[settings_module.Settings]:
    isolated = settings_module.Settings(tmp_path / "PyAmp-test.conf")
    previous = settings_module._instance
    settings_module._instance = isolated
    try:
        yield isolated
    finally:
        settings_module._instance = previous


@pytest.fixture(autouse=True)
def isolated_language() -> Iterator[None]:
    set_language(DEFAULT_LANGUAGE)
    try:
        yield
    finally:
        set_language(DEFAULT_LANGUAGE)
