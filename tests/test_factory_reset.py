from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.settings import Settings


def test_settings_reset_borra_idioma_radio_y_notificaciones(tmp_path) -> None:
    settings = Settings(tmp_path / "reset.conf")
    settings.language = "en"
    settings.radio_stations = '[{"name":"Radio","url":"http://radio"}]'
    settings.radio_found = '[{"name":"Buscada","url":"http://buscada"}]'
    settings.notifications_enabled = False

    settings.reset()

    assert settings.language == "es"
    assert settings.radio_stations == ""
    assert settings.radio_found == ""
    assert settings.notifications_enabled is True


def test_factory_reset_limpia_todo_y_avisa(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ui import main_window as main_window_module
    from app.ui.main_window import FACTORY_RESET_CLOSE_DELAY_MS, MainWindow

    calls: list[object] = []
    window = SimpleNamespace(
        _factory_reset_pending=False,
        _on_clear_playlist=lambda: calls.append("playlist"),
        _library=SimpleNamespace(reset=lambda: calls.append("library")),
        _delete_saved_playlists=lambda: calls.append("playlist-files"),
        _songs_table=SimpleNamespace(refresh=lambda: calls.append("songs")),
        _favorites_table=SimpleNamespace(refresh=lambda: calls.append("favorites")),
        _radio_panel=SimpleNamespace(refresh=lambda: calls.append("radio")),
        _settings=SimpleNamespace(reset=lambda: calls.append("settings")),
        _notifier=SimpleNamespace(
            enabled=False,
            notify_reset=lambda: calls.append("notification"),
        ),
        statusBar=lambda: SimpleNamespace(showMessage=lambda _text: calls.append("status")),
        _quit_after_factory_reset=lambda: None,
    )

    monkeypatch.setattr(
        main_window_module, "delete_all_custom_themes", lambda: calls.append("themes")
    )
    monkeypatch.setattr(
        main_window_module,
        "QTimer",
        SimpleNamespace(singleShot=lambda delay, _callback: calls.append(("quit", delay))),
    )

    MainWindow._on_factory_reset(window)  # type: ignore[arg-type]

    assert window._factory_reset_pending is True
    assert window._notifier.enabled is True
    assert calls == [
        "playlist",
        "library",
        "playlist-files",
        "themes",
        "settings",
        "songs",
        "favorites",
        "radio",
        "notification",
        "status",
        ("quit", FACTORY_RESET_CLOSE_DELAY_MS),
    ]


def test_factory_reset_borra_listas_guardadas_sin_tocar_otros_archivos(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.ui import main_window as main_window_module

    (tmp_path / "una.m3u").write_text("#EXTM3U", encoding="utf-8")
    (tmp_path / "dos.m3u8").write_text("#EXTM3U", encoding="utf-8")
    keep = tmp_path / "notas.txt"
    keep.write_text("no borrar", encoding="utf-8")
    monkeypatch.setattr(main_window_module, "PLAYLISTS_DIR", tmp_path)

    main_window_module.MainWindow._delete_saved_playlists(SimpleNamespace())

    assert list(tmp_path.glob("*.m3u")) == []
    assert list(tmp_path.glob("*.m3u8")) == []
    assert keep.read_text(encoding="utf-8") == "no borrar"
