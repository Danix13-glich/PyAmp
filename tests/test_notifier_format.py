from __future__ import annotations

from types import SimpleNamespace

from app.notifications.notifier import (
    UNKNOWN_ARTIST_TEXT,
    format_track_notification,
)


def _track(**kwargs: object) -> SimpleNamespace:
    base = {"title": "Song Title", "artist": "The Artist", "path": "/music/song.mp3"}
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_format_returns_app_name_pyamp() -> None:
    app_name, _title, _body = format_track_notification(_track())
    assert app_name == "PyAmp"


def test_format_returns_title_and_artist() -> None:
    _app, title, body = format_track_notification(_track())
    assert title == "Song Title"
    assert body == "The Artist"


def test_format_unknown_artist_shows_desconocido() -> None:
    _app, _title, body = format_track_notification(_track(artist=None))
    assert body == UNKNOWN_ARTIST_TEXT
    assert body == "Artista desconocido"


def test_format_blank_artist_shows_desconocido() -> None:
    _app, _title, body = format_track_notification(_track(artist="   "))
    assert body == "Artista desconocido"


def test_format_generic_unknown_marker_shows_desconocido() -> None:
    _app, _title, body = format_track_notification(_track(artist="Unknown Artist"))
    assert body == "Artista desconocido"


def test_format_missing_title_falls_back_to_filename() -> None:
    _app, title, _body = format_track_notification(
        _track(title=None, path="/music/Mi Cancion Bonita.mp3")
    )
    assert title == "Mi Cancion Bonita"


def test_format_missing_title_and_path_shows_sin_titulo() -> None:
    _app, title, _body = format_track_notification(_track(title=None, path=None))
    assert title == "Sin título"


def test_format_accepts_dict_track() -> None:
    app_name, title, body = format_track_notification(
        {"title": "Dict Song", "artist": "Dict Artist", "path": "/a/b.mp3"}
    )
    assert app_name == "PyAmp"
    assert title == "Dict Song"
    assert body == "Dict Artist"


def test_format_is_stable_three_tuple() -> None:
    result = format_track_notification(_track())
    assert isinstance(result, tuple)
    assert len(result) == 3
    assert all(isinstance(part, str) and part for part in result)
