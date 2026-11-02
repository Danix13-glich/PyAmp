from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.radio import song_search


def test_find_youtube_url_uses_yt_dlp(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        calls.append(command)
        return SimpleNamespace(
            returncode=0,
            stdout="https://www.youtube.com/watch?v=abc123XYZ98\n",
            stderr="",
        )

    monkeypatch.setattr(song_search.shutil, "which", lambda name: "/usr/bin/yt-dlp")
    monkeypatch.setattr(song_search.subprocess, "run", fake_run)

    assert (
        song_search.find_youtube_url("Artista Canción")
        == "https://www.youtube.com/watch?v=abc123XYZ98"
    )
    assert calls and calls[0][-1] == "ytsearch1:Artista Canción"


def test_find_youtube_url_falls_back_to_youtube_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(song_search.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        song_search.urllib.request,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("sin red")),
    )

    url = song_search.find_youtube_url("Artista Canción")

    assert url.startswith("https://www.youtube.com/results?")
    assert "search_query=Artista" in url


def test_search_online_song_devuelve_enlace_de_youtube(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        song_search,
        "_get_json",
        lambda url: {
            "results": [
                {
                    "trackName": "Canción",
                    "artistName": "Artista",
                    "trackTimeMillis": 180000,
                    "trackViewUrl": "https://music.apple.com/apple",
                    "previewUrl": "https://preview",
                }
            ]
        },
    )
    monkeypatch.setattr(
        song_search,
        "find_youtube_url",
        lambda query: "https://www.youtube.com/watch?v=youtube123",
    )

    result = song_search.search_online_song("Artista Canción")

    assert result is not None
    assert result.link == "https://www.youtube.com/watch?v=youtube123"
    assert "apple" not in result.link
