from __future__ import annotations

import wave
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

import app.themes.manager as theme_manager
from app.core.settings import Settings
from app.library.metadata import MetadataError, read_metadata, write_metadata
from app.library.models import Track
from app.themes import create_custom_theme, derive_theme_colors, load_themes
from app.ui.cover_widget import station_initials
from app.ui.songs_table import SongsTableModel


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# --------------------------------------------------------------- ajustes
def test_window_size_defaults_and_clamp(tmp_path: Path) -> None:
    settings = Settings(tmp_path / "win.conf")
    assert settings.window_width > 0
    assert settings.window_height > 0
    settings.window_width = 5  # por debajo del mínimo
    settings.window_height = 999999  # por encima del máximo
    assert settings.window_width >= 480
    assert settings.window_height <= 2160


def test_show_hidden_setting_roundtrip(tmp_path: Path) -> None:
    settings = Settings(tmp_path / "hidden.conf")
    assert settings.show_hidden is False
    settings.show_hidden = True
    assert Settings(tmp_path / "hidden.conf").show_hidden is True


# ------------------------------------------------------------------ temas
def test_derive_theme_colors_produces_hex() -> None:
    colors = derive_theme_colors("#101018", "#f0f0f0", "#3d7bd9")
    for key in ("window_bg", "window_text", "accent", "accent_text", "surface_bg"):
        assert colors[key].startswith("#")
        assert len(colors[key]) == 7
    assert colors["window_bg"] == "#101018"
    assert colors["accent"] == "#3d7bd9"


def test_accent_text_is_readable() -> None:
    light = derive_theme_colors("#ffffff", "#000000", "#fff3b0")
    dark = derive_theme_colors("#000000", "#ffffff", "#1a1a2e")
    assert light["accent_text"] == "#101014"
    assert dark["accent_text"] == "#ffffff"


def test_create_custom_theme_is_loadable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(theme_manager, "USER_THEMES_DIR", tmp_path / "themes")
    monkeypatch.setattr(theme_manager, "_cache", None)

    theme = create_custom_theme("#101820", "#f2f2f2", "#ff8800", name="Atardecer")

    assert theme.id.startswith("custom-")
    assert theme.name == "Atardecer"
    assert theme.native is False
    assert (tmp_path / "themes" / f"{theme.id}.json").is_file()
    assert theme.id in load_themes()


# ------------------------------------------------------------- metadata
def _make_wav(path: Path) -> Path:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"\x00\x00" * 2000)
    return path


def test_write_and_read_metadata(tmp_path: Path) -> None:
    path = _make_wav(tmp_path / "track.wav")
    write_metadata(str(path), {"title": "Título", "artist": "Artista", "genre": "Rock"})
    info = read_metadata(str(path))
    assert info.title == "Título"
    assert info.artist == "Artista"
    assert info.genre == "Rock"


def test_write_metadata_missing_file(tmp_path: Path) -> None:
    with pytest.raises(MetadataError):
        write_metadata(tmp_path / "no-existe.wav", {"title": "X"})


# ------------------------------------------------- tabla (ocultos)
def test_model_hides_and_prefixes_hidden(qapp: QApplication) -> None:
    model = SongsTableModel()
    normal = Track(path="/m/a.mp3", title="Visible")
    hidden = Track(path="/m/b.mp3", title="Oculta", is_hidden=True)

    model.set_tracks([normal, hidden], show_hidden=False)
    assert model.rowCount() == 1

    model.set_tracks([normal, hidden], show_hidden=True)
    assert model.rowCount() == 2
    names = [
        model.data(model.index(row, 0), Qt.ItemDataRole.DisplayRole)
        for row in range(model.rowCount())
    ]
    assert "Visible" in names
    assert "-Oculta" in names


def test_station_initials() -> None:
    assert station_initials("Radio Paradise") == "RP"
    assert station_initials("LOS40") == "LO"
    assert station_initials("") == "R"
