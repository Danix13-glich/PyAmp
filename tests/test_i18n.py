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
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# --------------------------------------------------------------- app/i18n.py
def test_tr_returns_spanish_by_default() -> None:
    set_language(DEFAULT_LANGUAGE)
    assert tr("&Archivo") == "&Archivo"
    assert tr("texto sin traducir") == "texto sin traducir"


def test_tr_translates_known_texts_to_english() -> None:
    set_language("en")
    assert tr("&Archivo") == "&File"
    assert tr("Ajustes de PyAmp") == "PyAmp Settings"
    assert tr("texto sin traducir") == "texto sin traducir"


def test_set_language_rejects_unknown_codes() -> None:
    assert set_language("fr") == "es"
    assert current_language() == "es"
    assert language_name("fr") == "Español"
    assert language_name("en") == "English"
    assert language_name("it") == "Italiano"
    assert language_name("ar") == "العربية"
    assert set(LANGUAGES) == {"es", "en", "it", "ar"}


def test_tr_translates_known_texts_to_italian() -> None:
    set_language("it")
    assert tr("&Archivo") == "&File"
    assert tr("Ajustes de PyAmp") == "Impostazioni di PyAmp"
    assert tr("texto sin traducir") == "texto sin traducir"


def test_tr_translates_known_texts_to_arabic() -> None:
    set_language("ar")
    assert tr("&Archivo") == "&ملف"
    assert tr("Ajustes de PyAmp") == "إعدادات PyAmp"
    assert tr("texto sin traducir") == "texto sin traducir"


def test_arabic_is_right_to_left() -> None:
    from app.i18n import is_rtl

    assert is_rtl("ar") is True
    assert is_rtl("es") is False
    assert is_rtl("it") is False


def test_all_translations_cover_every_key() -> None:
    from app.i18n import _AR, _EN, _IT, _TRANSLATIONS

    assert set(_TRANSLATIONS) == {"en", "it", "ar"}
    for code, table in (("it", _IT), ("ar", _AR)):
        missing = set(_EN) - set(table)
        assert not missing, f"faltan claves en {code}: {sorted(missing)[:5]}"
        extra = set(table) - set(_EN)
        assert not extra, f"claves sobrantes en {code}: {sorted(extra)[:5]}"


# ---------------------------------------------------------- Settings.language
def test_settings_language_roundtrip(tmp_path: Path) -> None:
    settings = Settings(tmp_path / "lang.conf")

    assert settings.language == "es"
    settings.language = "en"
    assert settings.language == "en"
    settings.language = "klingon"
    assert settings.language == "es"


# --------------------------------------------------- Ajustes → pestaña General
def test_settings_dialog_emits_language(qapp: QApplication) -> None:
    dialog = SettingsDialog(get_settings(), notifier_backend="test", version="0.1.8")
    received: list[str] = []
    dialog.apply_language.connect(received.append)

    assert dialog._combo_language.count() == 4  # noqa: SLF001 - tests
    dialog._combo_language.setCurrentIndex(  # noqa: SLF001 - tests
        dialog._combo_language.findData("en")  # noqa: SLF001 - tests
    )
    dialog._on_accepted()  # noqa: SLF001 - tests

    assert received == ["en"]


def test_language_change_schedules_restart(
    qapp: QApplication, isolated_qsettings: Settings
) -> None:
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
