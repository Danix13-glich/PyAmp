"""Tests de la biblioteca (Fase 2): SQLite, repos de playlists y escáner.

El escáner se ejecuta con ``run()`` de forma síncrona (mismo hilo): las
señales con conexiones directas se entregan al instante, sin necesidad de
un event loop.
"""

from __future__ import annotations

import os
import wave
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from app.library.database import (
    SCHEMA_VERSION,
    LibraryDatabase,
    cleanup_orphan_albums_artists,
    open_connection,
    record_play_by_path,
)
from app.library.models import Track
from app.library.playlist_repository import PlaylistRepository
from app.library.scanner import ScannerThread


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    """QApplication única offscreen para las señales de QThread y widgets."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def db(tmp_path: Path) -> LibraryDatabase:
    database = LibraryDatabase(tmp_path / "library.db")
    yield database
    database.close()


def make_wav(path: Path, *, title: str | None = None, artist: str | None = None) -> Path:
    """WAV mono PCM válido; opcionalmente etiquetado con ID3."""
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"\x00\x00" * 2000)
    if title is not None:
        from mutagen.id3 import TIT2, TPE1
        from mutagen.wave import WAVE

        audio = WAVE(str(path))
        audio.add_tags()
        assert audio.tags is not None
        audio.tags.add(TIT2(encoding=3, text=[title]))
        if artist is not None:
            audio.tags.add(TPE1(encoding=3, text=[artist]))
        audio.save()
    return path


# ------------------------------------------------------------------ esquema
def test_schema_initialized(db: LibraryDatabase) -> None:
    row = db.connection.execute("PRAGMA user_version").fetchone()
    assert row is not None and row[0] == SCHEMA_VERSION
    tables = {
        r["name"]
        for r in db.connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert {"tracks", "artists", "albums", "playlists", "playlist_tracks"} <= tables


def test_open_connection_enables_wal_and_fk(tmp_path: Path) -> None:
    conn = open_connection(tmp_path / "x.db")
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()


# -------------------------------------------------------------------- CRUD
def test_upsert_creates_track_and_resolves_artist_album(db: LibraryDatabase) -> None:
    track_id = db.upsert_track(
        Track(path="/m/a.mp3", title="Canción", artist="Artista", album="Álbum", year="2024")
    )
    track = db.get_track(track_id)
    assert track is not None
    assert track.title == "Canción"
    assert track.play_count == 0
    assert track.added_at is not None

    artists = db.list_artists()
    albums = db.list_albums()
    assert [a.name for a in artists] == ["Artista"]
    assert artists[0].track_count == 1
    assert albums[0].title == "Álbum"
    assert albums[0].artist_name == "Artista"
    assert albums[0].year == "2024"
    assert albums[0].track_count == 1


def test_upsert_updates_in_place_and_keeps_stats(db: LibraryDatabase) -> None:
    track_id = db.upsert_track(Track(path="/m/a.mp3", title="Viejo"))
    added_at = db.get_track(track_id).added_at  # type: ignore[union-attr]
    db.record_play_by_path("/m/a.mp3")

    again = db.upsert_track(Track(path="/m/a.mp3", title="Nuevo"))

    assert again == track_id
    track = db.get_track(track_id)
    assert track is not None and track.title == "Nuevo"
    assert track.play_count == 1  # el re-escaneo no borra estadísticas
    assert track.added_at == added_at
    assert db.stats()["tracks"] == 1


def test_remove_missing_tracks(db: LibraryDatabase) -> None:
    db.upsert_track(Track(path="/m/a.mp3", title="A"))
    db.upsert_track(Track(path="/m/b.mp3", title="B"))

    removed = db.remove_missing_tracks({"/m/a.mp3"})

    assert removed == 1
    assert db.get_track_by_path("/m/a.mp3") is not None
    assert db.get_track_by_path("/m/b.mp3") is None


def test_cleanup_orphans_after_removal(db: LibraryDatabase) -> None:
    db.upsert_track(Track(path="/m/a.mp3", artist="Único", album="Solo"))
    db.upsert_track(Track(path="/m/b.mp3", artist="Único", album="Solo"))

    db.remove_missing_tracks({"/m/b.mp3"})
    albums_removed, artists_removed = cleanup_orphan_albums_artists(db.connection)
    assert (albums_removed, artists_removed) == (0, 0)  # aún queda b.mp3

    db.remove_missing_tracks(set())
    albums_removed, artists_removed = cleanup_orphan_albums_artists(db.connection)
    assert (albums_removed, artists_removed) == (1, 1)
    assert db.list_artists() == []


def test_record_play_by_path(db: LibraryDatabase) -> None:
    db.upsert_track(Track(path="/m/a.mp3", title="A"))

    assert record_play_by_path(db.connection, "/m/a.mp3") is True
    assert db.record_play_by_path("/m/desconocida.mp3") is False

    track = db.get_track_by_path("/m/a.mp3")
    assert track is not None and track.play_count == 1
    assert track.last_played_at is not None


def test_search_tracks(db: LibraryDatabase) -> None:
    db.upsert_track(Track(path="/m/1.mp3", title="100% Love", artist="Alfa"))
    db.upsert_track(Track(path="/m/2.mp3", title="100A Love", artist="Beta"))
    db.upsert_track(Track(path="/m/3.mp3", title="Otra", album="Álbum Buscado"))

    assert [t.path for t in db.search_tracks("100%")] == ["/m/1.mp3"]  # literal
    assert [t.path for t in db.search_tracks("beta")] == ["/m/2.mp3"]  # insensible
    assert [t.path for t in db.search_tracks("Buscado")] == ["/m/3.mp3"]
    assert db.search_tracks("   ") == []


def test_all_tracks_sorted(db: LibraryDatabase) -> None:
    db.upsert_track(Track(path="/m/2.mp3", title="B", artist="Zeta"))
    db.upsert_track(Track(path="/m/1.mp3", title="A", artist="Alfa"))

    assert [t.title for t in db.all_tracks()] == ["A", "B"]


def test_stats(db: LibraryDatabase) -> None:
    db.upsert_track(Track(path="/m/a.mp3", artist="X", album="Y"))
    stats = db.stats()
    assert stats == {"tracks": 1, "artists": 1, "albums": 1, "playlists": 0}


# ------------------------------------------------- favoritos (Fase 4 / v2)
def test_schema_has_favorite_column(db: LibraryDatabase) -> None:
    columns = {row["name"] for row in db.connection.execute("PRAGMA table_info(tracks)").fetchall()}
    assert "is_favorite" in columns


def test_migration_v1_to_v2_adds_favorite_column(tmp_path: Path) -> None:
    """Una BD en v1 (Fase 3) se migra a v2 al abrirla con la fachada."""
    from app.library.database import _SCHEMA_V1

    path = tmp_path / "old.db"
    conn = open_connection(path)
    try:
        conn.executescript(_SCHEMA_V1)
        conn.execute("PRAGMA user_version = 1")
        conn.commit()
    finally:
        conn.close()

    database = LibraryDatabase(path)
    try:
        row = database.connection.execute("PRAGMA user_version").fetchone()
        assert row is not None and row[0] == SCHEMA_VERSION == 2
        columns = {r["name"] for r in database.connection.execute("PRAGMA table_info(tracks)")}
        assert "is_favorite" in columns
    finally:
        database.close()


def test_toggle_favorite_lifecycle(db: LibraryDatabase) -> None:
    path = "/m/fav.mp3"

    # Pista no indexada: el primer toggle crea la fila y la marca.
    assert db.toggle_favorite(path) is True
    assert db.is_favorite(path) is True

    # Segundo toggle la desmarca; persiste tras reabrir conexión lógica.
    assert db.toggle_favorite(path) is False
    assert db.is_favorite(path) is False

    # Path desconocido y sin marcar → False sin crear nada.
    assert db.is_favorite("/m/nunca.mp3") is False


def test_upsert_preserves_favorite(db: LibraryDatabase) -> None:
    """Re-escanear la misma pista no borra el favorito del usuario."""
    db.upsert_track(Track(path="/m/fav.mp3", title="Fav", artist="Alfa"))
    assert db.toggle_favorite("/m/fav.mp3") is True

    db.upsert_track(Track(path="/m/fav.mp3", title="Fav v2", artist="Alfa"))

    assert db.is_favorite("/m/fav.mp3") is True
    track = next(t for t in db.all_tracks() if t.path == "/m/fav.mp3")
    assert track.is_favorite is True
    assert track.title == "Fav v2"


# ------------------------------------------------------- playlists (repo)
def test_playlist_repository_lifecycle(db: LibraryDatabase) -> None:
    repo = PlaylistRepository(db)
    first = db.upsert_track(Track(path="/m/1.mp3", title="Uno"))
    second = db.upsert_track(Track(path="/m/2.mp3", title="Dos"))

    playlist_id = repo.create("Favoritas")
    assert repo.add_track(playlist_id, second) == 0
    assert repo.add_track(playlist_id, first) == 1

    playlist = repo.get(playlist_id)
    assert playlist is not None
    assert playlist.name == "Favoritas"
    assert playlist.track_count == 2
    # add_track conserva el orden de inserción (posición 0, 1).
    assert [t.title for t in playlist.tracks] == ["Dos", "Uno"]

    assert repo.set_tracks(playlist_id, [first]) is True
    assert repo.get(playlist_id).tracks[0].title == "Uno"  # type: ignore[union-attr]

    assert repo.rename(playlist_id, "Viaje") is True
    assert [p.name for p in repo.list_all()] == ["Viaje"]
    assert repo.list_all()[0].track_count == 1

    assert repo.delete(playlist_id) is True
    assert repo.get(playlist_id) is None
    # Las pistas de la biblioteca NO se borran con la playlist.
    assert db.stats()["tracks"] == 2


def test_playlist_delete_cascades_entries(db: LibraryDatabase) -> None:
    repo = PlaylistRepository(db)
    track_id = db.upsert_track(Track(path="/m/1.mp3", title="Uno"))
    playlist_id = repo.create("Borrar")
    repo.set_tracks(playlist_id, [track_id])

    repo.delete(playlist_id)

    rows = db.connection.execute("SELECT COUNT(*) AS n FROM playlist_tracks").fetchone()
    assert rows is not None and rows["n"] == 0


def test_playlist_errors(db: LibraryDatabase) -> None:
    repo = PlaylistRepository(db)
    with pytest.raises(ValueError):
        repo.create("   ")
    track_id = db.upsert_track(Track(path="/m/1.mp3"))
    playlist_id = repo.create("X")
    # Playlist inexistente -> False (no excepción).
    assert repo.set_tracks(999, [track_id]) is False
    # Pista inexistente -> ValueError (playlist existente).
    with pytest.raises(ValueError):
        repo.set_tracks(playlist_id, [999])
    # add_track: tanto playlist como pista inexistente -> ValueError.
    with pytest.raises(ValueError):
        repo.add_track(999, track_id)
    with pytest.raises(ValueError):
        repo.add_track(playlist_id, 12345)


# ----------------------------------------------------------------- escáner
def test_scanner_full_lifecycle(qapp: QApplication, tmp_path: Path) -> None:
    folder = tmp_path / "musica"
    folder.mkdir()
    make_wav(folder / "a.wav", title="Alfa", artist="Uno")
    make_wav(folder / "b.wav", title="Beta", artist="Dos")
    (folder / "sub").mkdir()
    make_wav(folder / "sub" / "c.wav")
    (folder / "no-audio.txt").write_text("hola")

    db_path = tmp_path / "library.db"
    summaries: list[dict] = []

    # 1) Escaneo inicial: 3 añadidas.
    scanner = ScannerThread(str(db_path), str(folder))
    scanner.scan_finished.connect(summaries.append)
    scanner.run()
    assert summaries[-1]["added"] == 3
    assert summaries[-1]["found"] == 3
    assert summaries[-1]["cancelled"] is False

    database = LibraryDatabase(db_path)
    assert database.stats()["tracks"] == 3
    assert database.get_track_by_path(str((folder / "a.wav").resolve())).title == "Alfa"  # type: ignore[union-attr]

    # 2) Reescaneo sin cambios: todo skipped.
    scanner2 = ScannerThread(str(db_path), str(folder))
    scanner2.scan_finished.connect(summaries.append)
    scanner2.run()
    assert summaries[-1]["skipped"] == 3
    assert summaries[-1]["added"] == 0

    # 3) Touch (mtime distinto) → 1 actualizada.
    target = folder / "b.wav"
    stat = target.stat()
    os.utime(target, (stat.st_mtime + 10, stat.st_mtime + 10))
    scanner3 = ScannerThread(str(db_path), str(folder))
    scanner3.scan_finished.connect(summaries.append)
    scanner3.run()
    assert summaries[-1]["updated"] == 1
    assert summaries[-1]["skipped"] == 2

    # 4) Borrado en disco → eliminada de la BD.
    (folder / "sub" / "c.wav").unlink()
    scanner4 = ScannerThread(str(db_path), str(folder))
    scanner4.scan_finished.connect(summaries.append)
    scanner4.run()
    assert summaries[-1]["removed"] == 1
    assert database.stats()["tracks"] == 2
    database.close()


def test_scanner_cancel_before_run_keeps_db(qapp: QApplication, tmp_path: Path) -> None:
    folder = tmp_path / "musica"
    folder.mkdir()
    make_wav(folder / "a.wav")

    db_path = tmp_path / "library.db"
    database = LibraryDatabase(db_path)
    database.upsert_track(Track(path="/m/existente.mp3", title="Previa"))
    database.close()

    scanner = ScannerThread(str(db_path), str(folder))
    scanner.cancel()  # cancelado antes de arrancar
    summaries: list[dict] = []
    scanner.scan_finished.connect(summaries.append)
    scanner.run()

    assert summaries[-1]["cancelled"] is True
    assert summaries[-1]["found"] == 0
    database = LibraryDatabase(db_path)
    # Cancelado: no se toca lo que había.
    assert database.get_track_by_path("/m/existente.mp3") is not None
    database.close()


def test_scanner_reports_invalid_folder(qapp: QApplication, tmp_path: Path) -> None:
    scanner = ScannerThread(str(tmp_path / "x.db"), str(tmp_path / "no-existe"))
    errors: list[str] = []
    summaries: list[dict] = []
    scanner.scan_error.connect(errors.append)
    scanner.scan_finished.connect(summaries.append)
    scanner.run()

    assert errors and "no válida" in errors[0]
    assert summaries  # finished se emite siempre (limpieza de la UI)
