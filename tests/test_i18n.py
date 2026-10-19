"""Tests de idioma (0.1.8): app/i18n.py, Ajustes → General y reinicio.

El idioma es estado global del proceso, así que ``conftest.py`` lo devuelve
al español después de cada test (fixture ``isolated_language``).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.core.settings import Settings, get_settings
from app.i18n import (
    DEFAULT_LANGUAGE,
    LANGUAGES,
    current_language,
    language_name,
    set_language,
    tr,
)
from app.library.database import LibraryDatabase
from app.library.models import Track
from app.ui.library_panel import LibraryPanel
from app.ui.main_window import MainWindow
from app.ui.settings_dialog import SettingsDialog
from app.ui.songs_table import SongsTable


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    """QApplication única offscreen para los widgets."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# --------------------------------------------------------------- app/i18n.py
def test_tr_returns_spanish_by_default() -> None:
    """En español ``tr`` devuelve el texto original (el código es la fuente)."""
    set_language(DEFAULT_LANGUAGE)
    assert tr("&Archivo") == "&Archivo"
    assert tr("texto sin traducir") == "texto sin traducir"


def test_tr_translates_known_texts_to_english() -> None:
    """En inglés los textos conocidos se traducen y el resto queda igual."""
    set_language("en")
    assert tr("&Archivo") == "&File"
    assert tr("Ajustes de PyAmp") == "PyAmp Settings"
    assert tr("texto sin traducir") == "texto sin traducir"


def test_set_language_rejects_unknown_codes() -> None:
    """Un código desconocido vuelve al idioma por defecto (español)."""
    assert set_language("fr") == "es"
    assert current_language() == "es"
    assert language_name("fr") == "Español"
    assert language_name("en") == "English"
    assert set(LANGUAGES) == {"es", "en"}


# ---------------------------------------------------------- Settings.language
def test_settings_language_roundtrip(tmp_path: Path) -> None:
    """El idioma persiste y un valor inválido cae al por defecto."""
    settings = Settings(tmp_path / "lang.conf")

    assert settings.language == "es"
    settings.language = "en"
    assert settings.language == "en"
    settings.language = "klingon"
    assert settings.language == "es"


# --------------------------------------------------- Ajustes → pestaña General
def test_settings_dialog_emits_language(qapp: QApplication) -> None:
    """La pestaña General lista los idiomas y emite apply_language al aceptar."""
    dialog = SettingsDialog(get_settings(), notifier_backend="test", version="0.1.8")
    received: list[str] = []
    dialog.apply_language.connect(received.append)

    assert dialog._combo_language.count() == 2  # noqa: SLF001 - tests
    dialog._combo_language.setCurrentIndex(  # noqa: SLF001 - tests
        dialog._combo_language.findData("en")  # noqa: SLF001 - tests
    )
    dialog._on_accepted()  # noqa: SLF001 - tests

    assert received == ["en"]


def test_language_change_schedules_restart(
    qapp: QApplication, isolated_qsettings: Settings
) -> None:
    """Un cambio real de idioma persiste y lanza ``_restart_app`` (aplazado)."""
    restarts: list[int] = []
    fake = SimpleNamespace(
        _settings=isolated_qsettings,
        _restart_app=lambda: restarts.append(1),
    )

    MainWindow._on_apply_language(fake, "en")  # type: ignore[arg-type]
    QTest.qWait(20)

    assert isolated_qsettings.language == "en"
    assert restarts == [1]

    # Repetir el mismo idioma no reinicia otra vez.
    MainWindow._on_apply_language(fake, "en")  # type: ignore[arg-type]
    QTest.qWait(20)
    assert restarts == [1]


# ------------------------------------------------------ textos con interfaz
def test_english_translates_panel_bucket(qapp: QApplication, tmp_path: Path) -> None:
    """En inglés el nodo «(Sin artista)» pasa a «(No artist)»."""
    set_language("en")
    database = LibraryDatabase(tmp_path / "en.db")
    try:
        database.upsert_track(
            Track(path=str(tmp_path / "suelta.wav"), title="Suelta", duration_ms=1000)
        )
        panel = LibraryPanel(database)
        panel.refresh()
        texts = [
            panel.tree.topLevelItem(index).text(0)
            for index in range(panel.tree.topLevelItemCount())
        ]
        assert texts == ["(No artist)"]
    finally:
        database.close()


def test_english_translates_table_headers(qapp: QApplication, tmp_path: Path) -> None:
    """En inglés las columnas de la tabla usan sus nombres ingleses."""
    set_language("en")
    database = LibraryDatabase(tmp_path / "en.db")
    try:
        table = SongsTable(database)
        headers = [
            table.model.headerData(section, Qt.Orientation.Horizontal) for section in range(4)
        ]
        assert headers == ["Name", "Duration", "Artist", "★"]
    finally:
        database.close()
