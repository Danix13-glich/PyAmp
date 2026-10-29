from __future__ import annotations

from pathlib import Path

from app.core.playlist import PlaylistModel, read_m3u_paths
from app.library.database import LibraryDatabase
from app.library.models import Track


def export_favorites(tracks: list[Track], path: str | Path) -> None:
    PlaylistModel(tracks).save_m3u(path)


def import_favorites(database: LibraryDatabase, path: str | Path) -> tuple[int, list[str]]:
    return database.set_favorites(read_m3u_paths(path))
