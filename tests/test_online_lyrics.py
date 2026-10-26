from __future__ import annotations

from pathlib import Path

from app.library.models import Track
from app.lyrics import online


def _candidate(
    name: str = "Song",
    artist: str = "Artist",
    duration: float = 200.0,
    synced: str = "",
    plain: str = "Letra de prueba",
) -> online.OnlineLyrics:
    return online.OnlineLyrics(name, artist, duration, synced, plain)


def test_normalize_text_quita_acentos_y_puntuacion() -> None:
    assert online.normalize_text("Canción (Remastered)") == "cancion remastered"


def test_artist_matches_varios_artistas() -> None:
    assert online.artist_matches("Artist A, Artist B", "Artist A")
    assert online.artist_matches("Artist A feat. Artist B", "Artist B")
    assert not online.artist_matches("Otro", "Artist A")


def test_title_matches_por_containment() -> None:
    assert online.title_matches("Song", "Song (Remastered)")
    assert online.title_matches("Corazón", "Corazon")
    assert not online.title_matches("Otra", "Song")


def test_duration_matches_con_margen() -> None:
    assert online.duration_matches(200_000, 201.5)
    assert not online.duration_matches(200_000, 215.0)
    assert not online.duration_matches(0, 200.0)


def test_select_exige_duracion_artista_y_titulo() -> None:
    candidates = [
        _candidate(duration=215.0),  # duración no coincide
        _candidate(artist="Otro"),  # artista no coincide
        _candidate(name="Otra canción"),  # título no coincide
    ]
    assert online.select_lyrics("Song", "Artist", 200_000, candidates) is None


def test_select_prefiere_letra_sincronizada() -> None:
    plain = _candidate(plain="Letra plana")
    synced = _candidate(synced="[00:01.00]Letra sincronizada")
    selected = online.select_lyrics("Song", "Artist", 200_000, [plain, synced])
    assert selected is synced


def test_fetch_lyrics_guarda_lrc(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(online, "LYRICS_DIR", tmp_path)
    candidate = _candidate(synced="[00:01.00]Hola")
    monkeypatch.setattr(
        online, "_search_candidates", lambda title, artist, timeout_s=0: [candidate]
    )
    track = Track(
        path=str(tmp_path / "music" / "song.mp3"),
        title="Song",
        artist="Artist",
        duration_ms=200_000,
    )

    result = online.fetch_lyrics(track)

    assert result == tmp_path / "song.lrc"
    assert result is not None
    assert "[00:01.00]Hola" in result.read_text(encoding="utf-8")


def test_fetch_lyrics_no_toca_un_lrc_existente(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(online, "LYRICS_DIR", tmp_path)
    sidecar = tmp_path / "music" / "song.lrc"
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text("letra local", encoding="utf-8")

    def _falla(*_args, **_kwargs):
        raise AssertionError("no debe buscar si ya hay letra local")

    monkeypatch.setattr(online, "_search_candidates", _falla)
    track = Track(
        path=str(tmp_path / "music" / "song.mp3"),
        title="Song",
        artist="Artist",
        duration_ms=200_000,
    )
    assert online.fetch_lyrics(track) == sidecar


def test_search_reintenta_con_el_primer_artista(tmp_path: Path, monkeypatch) -> None:
    calls: list[str] = []
    candidate = _candidate(artist="Artist A")

    def _fake(title: str, artist: str, timeout_s: int = 0):
        calls.append(artist)
        return [] if artist == "Artist A, Artist B" else [candidate]

    monkeypatch.setattr(online, "_search_candidates", _fake)
    track = Track(
        path=str(tmp_path / "song.mp3"),
        title="Song",
        artist="Artist A, Artist B",
        duration_ms=200_000,
    )

    assert online.search_lyrics(track) == candidate
    assert calls == ["Artist A, Artist B", "Artist A"]
