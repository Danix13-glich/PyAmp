from __future__ import annotations

import logging

from .database import LibraryDatabase, now_iso, row_to_track
from .models import Playlist

logger = logging.getLogger(__name__)


class PlaylistNotFoundError(Exception):
    pass


class PlaylistRepository:

    def __init__(self, database: LibraryDatabase) -> None:
        self._database = database

    @property
    def database(self) -> LibraryDatabase:
        return self._database

    # ------------------------------------------------------------- básica
    def create(self, name: str) -> int:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("El nombre de la playlist no puede estar vacío")
        conn = self._database.connection
        cursor = conn.execute(
            "INSERT INTO playlists (name, created_at) VALUES (?, ?)",
            (cleaned, now_iso()),
        )
        conn.commit()
        logger.info("Playlist creada: %r (id=%s)", cleaned, cursor.lastrowid)
        return int(cursor.lastrowid or 0)

    def delete(self, playlist_id: int) -> bool:
        conn = self._database.connection
        cursor = conn.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
        conn.commit()
        return cursor.rowcount > 0

    def rename(self, playlist_id: int, name: str) -> bool:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("El nombre de la playlist no puede estar vacío")
        conn = self._database.connection
        cursor = conn.execute("UPDATE playlists SET name = ? WHERE id = ?", (cleaned, playlist_id))
        conn.commit()
        return cursor.rowcount > 0

    # ----------------------------------------------------------- lectura
    def list_all(self) -> list[Playlist]:
        rows = self._database.connection.execute(
            """SELECT p.id, p.name, p.created_at, COUNT(pt.track_id) AS track_count
               FROM playlists p
               LEFT JOIN playlist_tracks pt ON pt.playlist_id = p.id
               GROUP BY p.id
               ORDER BY p.name COLLATE NOCASE"""
        ).fetchall()
        return [
            Playlist(
                id=row["id"],
                name=row["name"],
                created_at=row["created_at"],
                track_count=row["track_count"],
                tracks=[],
            )
            for row in rows
        ]

    def get(self, playlist_id: int) -> Playlist | None:
        conn = self._database.connection
        header = conn.execute(
            "SELECT id, name, created_at FROM playlists WHERE id = ?", (playlist_id,)
        ).fetchone()
        if header is None:
            return None
        rows = conn.execute(
            """SELECT t.* FROM playlist_tracks pt
               JOIN tracks t ON t.id = pt.track_id
               WHERE pt.playlist_id = ?
               ORDER BY pt.position""",
            (playlist_id,),
        ).fetchall()
        tracks = [row_to_track(row) for row in rows]
        return Playlist(
            id=header["id"],
            name=header["name"],
            created_at=header["created_at"],
            track_count=len(tracks),
            tracks=tracks,
        )

    # ---------------------------------------------------------- contenido
    def set_tracks(self, playlist_id: int, track_ids: list[int]) -> bool:
        conn = self._database.connection
        exists = conn.execute("SELECT 1 FROM playlists WHERE id = ?", (playlist_id,)).fetchone()
        if exists is None:
            return False
        for track_id in track_ids:
            found = conn.execute("SELECT 1 FROM tracks WHERE id = ?", (track_id,)).fetchone()
            if found is None:
                raise ValueError(f"Pista no encontrada en la biblioteca: {track_id}")
        with conn:
            conn.execute("DELETE FROM playlist_tracks WHERE playlist_id = ?", (playlist_id,))
            conn.executemany(
                "INSERT INTO playlist_tracks (playlist_id, position, track_id) " "VALUES (?, ?, ?)",
                [(playlist_id, position, track_id) for position, track_id in enumerate(track_ids)],
            )
        return True

    def add_track(self, playlist_id: int, track_id: int) -> int:
        conn = self._database.connection
        exists = conn.execute("SELECT 1 FROM playlists WHERE id = ?", (playlist_id,)).fetchone()
        if exists is None:
            raise ValueError(f"Playlist no encontrada: {playlist_id}")
        found = conn.execute("SELECT 1 FROM tracks WHERE id = ?", (track_id,)).fetchone()
        if found is None:
            raise ValueError(f"Pista no encontrada en la biblioteca: {track_id}")
        row = conn.execute(
            "SELECT COALESCE(MAX(position) + 1, 0) AS pos FROM playlist_tracks "
            "WHERE playlist_id = ?",
            (playlist_id,),
        ).fetchone()
        position = int(row["pos"]) if row is not None else 0
        conn.execute(
            "INSERT INTO playlist_tracks (playlist_id, position, track_id) " "VALUES (?, ?, ?)",
            (playlist_id, position, track_id),
        )
        conn.commit()
        return position
