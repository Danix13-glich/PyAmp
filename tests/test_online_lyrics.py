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

    assert result == tmp_path / "music" / "song.lrc"
    assert result is not None
    assert "[00:01.00]Hola" in result.read_text(encoding="utf-8")


def test_fetch_lyrics_usa_la_letra_antigua_de_la_carpeta_de_datos(
    tmp_path: Path, monkeypatch
) -> None:
    lyrics_dir = tmp_path / "datos"
    monkeypatch.setattr(online, "LYRICS_DIR", lyrics_dir)
    shared = lyrics_dir / "song.lrc"
    shared.parent.mkdir(parents=True)
    shared.write_text("[00:01.00]Vieja", encoding="utf-8")

    def _falla(*_args, **_kwargs):
        raise AssertionError("no debe buscar si ya hay una letra guardada")

    monkeypatch.setattr(online, "_search_candidates", _falla)
    track = Track(
        path=str(tmp_path / "music" / "song.mp3"),
        title="Song",
        artist="Artist",
        duration_ms=200_000,
    )
    assert online.fetch_lyrics(track) == shared


def test_fetch_lyrics_cae_en_la_carpeta_de_datos_si_no_puede_escribir(
    tmp_path: Path, monkeypatch
) -> None:
    lyrics_dir = tmp_path / "datos"
    monkeypatch.setattr(online, "LYRICS_DIR", lyrics_dir)
    candidate = _candidate(synced="[00:01.00]Hola")
    monkeypatch.setattr(
        online, "_search_candidates", lambda title, artist, timeout_s=0: [candidate]
    )
    original_save = online.save_lyrics

    def _save_sin_permiso(track, lyrics, *, destination=None):
        if destination is not None and destination.parent == tmp_path / "music":
            raise OSError("sin permiso")
        return original_save(track, lyrics, destination=destination)

    monkeypatch.setattr(online, "save_lyrics", _save_sin_permiso)
    track = Track(
        path=str(tmp_path / "music" / "song.mp3"),
        title="Song",
        artist="Artist",
        duration_ms=200_000,
    )

    result = online.fetch_lyrics(track)

    assert result == lyrics_dir / "song.lrc"
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


def test_fetch_lyrics_force_rellena_un_lrc_vacio(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(online, "LYRICS_DIR", tmp_path)
    sidecar = tmp_path / "music" / "song.lrc"
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text("\n", encoding="utf-8")
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

    result = online.fetch_lyrics(track, force=True)

    assert result == sidecar
    assert "[00:01.00]Hola" in sidecar.read_text(encoding="utf-8")


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
