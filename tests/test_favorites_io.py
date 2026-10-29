from __future__ import annotations

from pathlib import Path

from app.core.playlist import read_m3u_paths
from app.library.database import LibraryDatabase
from app.library.favorites_io import export_favorites, import_favorites
from app.library.models import Track


def _db(tmp_path: Path) -> LibraryDatabase:
    return LibraryDatabase(tmp_path / "library.db")


def test_read_m3u_paths_resuelve_relativas(tmp_path: Path) -> None:
    playlist = tmp_path / "lista.m3u"
    playlist.write_text(
        "#EXTM3U\n#EXTINF:1,Uno\nuno.mp3\nsub/dos.mp3\nuno.mp3\n",
        encoding="utf-8",
    )

    paths = read_m3u_paths(playlist)

    assert paths == [
        str((tmp_path / "uno.mp3").resolve()),
        str((tmp_path / "sub/dos.mp3").resolve()),
    ]


def test_export_favorites_escribe_solo_favoritas(tmp_path: Path) -> None:
    database = _db(tmp_path)
    favorite = Track(path=str(tmp_path / "favorita.mp3"), title="Favorita", duration_ms=1000)
    other = Track(path=str(tmp_path / "otra.mp3"), title="Otra", duration_ms=2000)
    database.upsert_track(favorite)
    database.upsert_track(other)
    database.toggle_favorite(favorite.path)

    target = tmp_path / "favoritos.m3u"
    export_favorites(database.favorite_tracks(), target)

    content = target.read_text(encoding="utf-8")
    assert "#EXTM3U" in content
    assert favorite.path in content
    assert other.path not in content
    database.close()


def test_import_favorites_marca_existentes_y_devuelve_ausentes(tmp_path: Path) -> None:
    database = _db(tmp_path)
    existing = Track(path=str(tmp_path / "existe.mp3"), title="Existe")
    already = Track(path=str(tmp_path / "ya-favorita.mp3"), title="Ya favorita")
    database.upsert_track(existing)
    database.upsert_track(already)
    database.toggle_favorite(already.path)
    missing = str(tmp_path / "no-esta.mp3")
    playlist = tmp_path / "importar.m3u"
    playlist.write_text(f"#EXTM3U\n{existing.path}\n{missing}\n", encoding="utf-8")

    marked, missing_paths = import_favorites(database, playlist)

    assert marked == 1
    assert missing_paths == [missing]
    assert database.is_favorite(existing.path) is True
    assert database.is_favorite(already.path) is True
    database.close()
