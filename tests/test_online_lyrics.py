from __future__ import annotations

from pathlib import Path

from app.library.models import Track
from app.lyrics import online


def _candidate(
    name: str = "Song",
    artist: str = "Artist",
    duration: float = 200.0,
    synced: str = "[00:01.00]Letra sincronizada",
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
    plain = _candidate(synced="", plain="Letra plana")
    synced = _candidate(synced="[00:01.00]Letra sincronizada")
    selected = online.select_lyrics("Song", "Artist", 200_000, [plain, synced])
    assert selected is synced


def test_select_ignora_letra_plana() -> None:
    plain = _candidate(synced="", plain="Letra plana")
    assert online.select_lyrics("Song", "Artist", 200_000, [plain]) is None


def test_search_lyrics_no_guarda_letra_plana(tmp_path: Path, monkeypatch) -> None:
    plain = _candidate(synced="", plain="Letra plana")
    monkeypatch.setattr(online, "LYRICS_DIR", tmp_path)
    monkeypatch.setattr(online, "_search_candidates", lambda title, artist, timeout_s=0: [plain])
    monkeypatch.setattr(online, "_search_candidates_by_title", lambda title, timeout_s=0: [plain])
    monkeypatch.setattr(online, "_search_candidates_query", lambda query, timeout_s=0: [plain])
    track = Track(
        path=str(tmp_path / "music" / "song.mp3"),
        title="Song",
        artist="Artist",
        duration_ms=200_000,
    )

    assert online.fetch_lyrics(track) is None
    assert not (tmp_path / "music" / "song.lrc").exists()


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
    sidecar = tmp_path / "music" / "song.lrc"
    assert online.fetch_lyrics(track) == sidecar
    assert "[00:01.00]Vieja" in sidecar.read_text(encoding="utf-8")


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


def test_fetch_lyrics_no_toca_un_lrc_sincronizado(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(online, "LYRICS_DIR", tmp_path)
    sidecar = tmp_path / "music" / "song.lrc"
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text("[00:01.00]letra local", encoding="utf-8")

    def _falla(*_args, **_kwargs):
        raise AssertionError("no debe buscar si ya hay una letra sincronizada")

    monkeypatch.setattr(online, "_search_candidates", _falla)
    track = Track(
        path=str(tmp_path / "music" / "song.mp3"),
        title="Song",
        artist="Artist",
        duration_ms=200_000,
    )
    assert online.fetch_lyrics(track) == sidecar


def test_fetch_lyrics_reemplaza_letra_plana_por_sincronizada(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(online, "LYRICS_DIR", tmp_path)
    sidecar = tmp_path / "music" / "song.lrc"
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text("letra local sin tiempos", encoding="utf-8")
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

    assert online.fetch_lyrics(track) == sidecar
    assert "[00:01.00]Hola" in sidecar.read_text(encoding="utf-8")


def test_fetch_lyrics_conserva_letra_plana_si_no_hay_sincronizada(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(online, "LYRICS_DIR", tmp_path)
    sidecar = tmp_path / "music" / "song.lrc"
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text("letra local sin tiempos", encoding="utf-8")
    plain = _candidate(synced="", plain="Letra plana")
    monkeypatch.setattr(online, "_search_candidates", lambda title, artist, timeout_s=0: [plain])
    monkeypatch.setattr(online, "_search_candidates_by_title", lambda title, timeout_s=0: [plain])
    monkeypatch.setattr(online, "_search_candidates_query", lambda query, timeout_s=0: [plain])
    track = Track(
        path=str(tmp_path / "music" / "song.mp3"),
        title="Song",
        artist="Artist",
        duration_ms=200_000,
    )

    assert online.fetch_lyrics(track) is None
    assert sidecar.read_text(encoding="utf-8") == "letra local sin tiempos"


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


def test_search_lyrics_infiere_artista_del_nombre_de_archivo(tmp_path: Path, monkeypatch) -> None:
    candidate = _candidate(artist="Artist")
    calls: list[tuple[str, str]] = []

    def _fake(title: str, artist: str, timeout_s: int = 0):
        calls.append((title, artist))
        return [candidate]

    monkeypatch.setattr(online, "_search_candidates", _fake)
    track = Track(
        path=str(tmp_path / "Artist - Song.mp3"),
        title="Song",
        artist=None,
        duration_ms=200_000,
    )

    assert online.search_lyrics(track) == candidate
    assert calls[0] == ("Song", "Artist")


def test_search_lyrics_tolera_diferencia_de_duracion(tmp_path: Path, monkeypatch) -> None:
    candidate = _candidate(duration=212.0)
    monkeypatch.setattr(
        online, "_search_candidates", lambda title, artist, timeout_s=0: [candidate]
    )
    monkeypatch.setattr(online, "_search_candidates_by_title", lambda title, timeout_s=0: [])
    monkeypatch.setattr(online, "_search_candidates_query", lambda query, timeout_s=0: [])
    track = Track(
        path=str(tmp_path / "song.mp3"),
        title="Song",
        artist="Artist",
        duration_ms=200_000,
    )

    assert online.search_lyrics(track) == candidate


def test_search_lyrics_prueba_consulta_libre_si_no_hay_resultados(
    tmp_path: Path, monkeypatch
) -> None:
    candidate = _candidate()
    queries: list[str] = []
    monkeypatch.setattr(online, "_search_candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr(online, "_search_candidates_by_title", lambda title, timeout_s=0: [])
    monkeypatch.setattr(
        online,
        "_search_candidates_query",
        lambda query, timeout_s=0: queries.append(query) or [candidate],
    )
    track = Track(
        path=str(tmp_path / "song.mp3"),
        title="Song",
        artist="Artist",
        duration_ms=200_000,
    )

    assert online.search_lyrics(track) == candidate
    assert queries == ["Song"]


def test_clean_track_title_quita_feat_y_parentesis() -> None:
    assert online.clean_track_title("Song (feat. Other)") == "Song"
    assert online.clean_track_title("Song [Remastered]") == "Song"
    assert online.clean_track_title("Canción") == "Canción"


def test_lyrics_file_is_synced(tmp_path: Path) -> None:
    synced = tmp_path / "synced.lrc"
    synced.write_text("[00:01.00]Hola\n", encoding="utf-8")
    plain = tmp_path / "plain.lrc"
    plain.write_text("Hola\n", encoding="utf-8")

    assert online.lyrics_file_is_synced(synced)
    assert not online.lyrics_file_is_synced(plain)
    assert not online.lyrics_file_is_synced(tmp_path / "missing.lrc")


def test_fetch_lyrics_copia_la_sincronizada_compartida_junto_al_audio(
    tmp_path: Path, monkeypatch
) -> None:
    lyrics_dir = tmp_path / "datos"
    monkeypatch.setattr(online, "LYRICS_DIR", lyrics_dir)
    sidecar = tmp_path / "music" / "song.lrc"
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text("letra plana", encoding="utf-8")
    shared = lyrics_dir / "song.lrc"
    shared.parent.mkdir(parents=True)
    shared.write_text("[00:01.00]Hola", encoding="utf-8")

    def _falla(*_args, **_kwargs):
        raise AssertionError("no debe buscar si ya hay una letra sincronizada")

    monkeypatch.setattr(online, "_search_candidates", _falla)
    track = Track(
        path=str(tmp_path / "music" / "song.mp3"),
        title="Song",
        artist="Artist",
        duration_ms=200_000,
    )

    assert online.fetch_lyrics(track) == sidecar
    assert "[00:01.00]Hola" in sidecar.read_text(encoding="utf-8")


def test_clean_track_title_quita_sufijos_de_version() -> None:
    assert online.clean_track_title("Song - Remastered 2011") == "Song"
    assert online.clean_track_title("Song – Official Video") == "Song"
    assert online.clean_track_title("01. Song") == "Song"
    assert online.clean_track_title("Song - Part 2") == "Song - Part 2"
    assert online.clean_track_title("Song - From Me to You") == "Song - From Me to You"


def test_title_matches_no_confunde_titulos_muy_cortos() -> None:
    assert online.title_matches("Go", "Go (Live)")
    assert not online.title_matches("Go", "Goodbye")


def test_select_penaliza_versiones_karaoke() -> None:
    studio = _candidate(name="Song", duration=200.0)
    karaoke = _candidate(name="Song (Karaoke Version)", duration=200.0)
    assert online.select_lyrics("Song", "Artist", 200_000, [karaoke, studio]) is studio


def test_select_prefiere_la_duracion_mas_cercana() -> None:
    close = _candidate(name="Song", duration=200.2)
    far = _candidate(name="Song", duration=202.0)
    assert online.select_lyrics("Song", "Artist", 200_000, [far, close]) is close


def test_search_lyrics_usa_albumartist_si_falta_artista(tmp_path: Path, monkeypatch) -> None:
    candidate = _candidate(artist="Artist")
    calls: list[tuple[str, str]] = []

    def _fake(title: str, artist: str, timeout_s: int = 0):
        calls.append((title, artist))
        return [candidate]

    monkeypatch.setattr(online, "_search_candidates", _fake)
    track = Track(
        path=str(tmp_path / "song.mp3"),
        title="Song",
        artist=None,
        albumartist="Artist",
        duration_ms=200_000,
    )

    assert online.search_lyrics(track) == candidate
    assert calls[0] == ("Song", "Artist")


def test_search_lyrics_extrae_artista_del_titulo(tmp_path: Path, monkeypatch) -> None:
    candidate = _candidate(artist="Artist")
    calls: list[tuple[str, str]] = []

    def _fake(title: str, artist: str, timeout_s: int = 0):
        calls.append((title, artist))
        return [candidate]

    monkeypatch.setattr(online, "_search_candidates", _fake)
    track = Track(
        path=str(tmp_path / "song.mp3"),
        title="Artist - Song",
        artist=None,
        duration_ms=200_000,
    )

    assert online.search_lyrics(track) == candidate
    assert calls[0] == ("Song", "Artist")


def test_search_lyrics_prueba_el_titulo_sin_sufijo_de_version(tmp_path: Path, monkeypatch) -> None:
    candidate = _candidate(name="Song", artist="Artist")
    calls: list[tuple[str, str]] = []

    def _fake(title: str, artist: str, timeout_s: int = 0):
        calls.append((title, artist))
        return [] if title != "Song" else [candidate]

    monkeypatch.setattr(online, "_search_candidates", _fake)
    track = Track(
        path=str(tmp_path / "song.mp3"),
        title="Song - Remastered 2011",
        artist="Artist",
        duration_ms=200_000,
    )

    assert online.search_lyrics(track) == candidate
    assert ("Song", "Artist") in calls


def test_select_rechaza_karaoke_si_la_pista_no_lo_es() -> None:
    karaoke = _candidate(name="Song (Karaoke Version)", duration=200.0)
    assert online.select_lyrics("Song", "Artist", 200_000, [karaoke]) is None


def test_normalize_text_conserva_otros_alfabetos() -> None:
    assert online.normalize_text("Café 東京") == "cafe 東京"
    assert online.normalize_text("Привет, мир!") == "привет мир"


def test_search_lyrics_busca_por_titulo_si_el_artista_esta_mal_escrito(
    tmp_path: Path, monkeypatch
) -> None:
    candidate = _candidate(name="Beggin'", artist="Måneskin", duration=190.0)
    queries: list[str] = []
    monkeypatch.setattr(online, "_search_candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr(online, "_search_candidates_by_title", lambda title, timeout_s=0: [])
    monkeypatch.setattr(
        online,
        "_search_candidates_query",
        lambda query, timeout_s=0: queries.append(query) or [candidate],
    )
    track = Track(
        path=str(tmp_path / "beggin.mp3"),
        title="Beggin",
        artist="Månzskin",
        duration_ms=190_000,
    )

    assert online.search_lyrics(track) == candidate
    assert queries == ["Beggin"]


def test_artist_score_admite_erratas_leves() -> None:
    assert online.artist_score("Månzskin", "Måneskin") >= 0.7
    assert online.artist_score("OneRepublc", "OneRepublic") >= 0.7
    assert online.artist_score("Pedro Kapo", "Pedro Capó") >= 0.7


def test_select_usa_el_artista_del_titulo_si_el_canal_no_coincide() -> None:
    candidate = _candidate(name="Måneskin - Beggin'", artist="7clouds", duration=210.0)
    assert online.select_lyrics("Beggin", "Månzskin", 211_566, [candidate]) is candidate
