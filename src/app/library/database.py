"""Biblioteca de PyAmp en SQLite (Fase 2).

Ubicación (RNF): ``<datos>/PyAmp/library.db`` — en Linux
``~/.local/share/PyAmp/library.db``. Modo WAL + foreign keys en cada
conexión; el escáner abre su **propia conexión** dentro de su QThread
(sqlite3 es por hilo) y la UI usa la suya.

Migraciones: ``PRAGMA user_version`` (v1 = esquema inicial). Añadir
tablas/columnas futuras = ``_migrate`` con ``version < 2``...

Las funciones a nivel de módulo operan sobre una conexión (útiles para el
escáner); :class:`LibraryDatabase` es la fachada que usa la app y envuelve
esas mismas funciones con su conexión.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from app.utils.paths import DATABASE_FILE

from .models import Album, Artist, Track

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 2

_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS artists (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE
);

CREATE TABLE IF NOT EXISTS albums (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL COLLATE NOCASE,
    artist_id INTEGER REFERENCES artists(id) ON DELETE SET NULL,
    year TEXT,
    cover_path TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_albums_title_artist
    ON albums (title, COALESCE(artist_id, 0));

CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    title TEXT,
    artist TEXT,
    album TEXT,
    albumartist TEXT,
    genre TEXT,
    year TEXT,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    track_no INTEGER,
    disc_no INTEGER,
    bitrate INTEGER,
    samplerate INTEGER,
    channels INTEGER,
    cover_path TEXT,
    artist_id INTEGER REFERENCES artists(id) ON DELETE SET NULL,
    album_id INTEGER REFERENCES albums(id) ON DELETE SET NULL,
    file_size INTEGER,
    file_mtime INTEGER,
    added_at TEXT NOT NULL,
    last_played_at TEXT,
    play_count INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_tracks_artist_id ON tracks (artist_id);
CREATE INDEX IF NOT EXISTS ix_tracks_album_id ON tracks (album_id);
CREATE INDEX IF NOT EXISTS ix_tracks_genre ON tracks (genre COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS ix_tracks_year ON tracks (year);

CREATE TABLE IF NOT EXISTS playlists (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS playlist_tracks (
    playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    PRIMARY KEY (playlist_id, position)
);
CREATE INDEX IF NOT EXISTS ix_playlist_tracks_track ON playlist_tracks (track_id);
"""


def now_iso() -> str:
    """Marca de tiempo local en ISO 8601 (segundos)."""
    return datetime.now().isoformat(timespec="seconds")


def open_connection(path: str | Path) -> sqlite3.Connection:
    """Abre una conexión lista para usar (WAL + foreign keys).

    Args:
        path: Ruta del archivo ``.db`` (se crea el padre si no existe).

    Returns:
        Conexión con ``row_factory = sqlite3.Row``.
    """
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Aplica los esquemas pendientes según ``PRAGMA user_version``."""
    row = conn.execute("PRAGMA user_version").fetchone()
    version = int(row[0]) if row is not None else 0

    if version < 1:
        conn.executescript(_SCHEMA_V1)
        conn.execute("PRAGMA user_version = 1")
        conn.commit()
        logger.info("Biblioteca inicializada (esquema v1)")
        version = 1

    if version < 2:
        # Fase 4: favoritos marcados por el usuario.
        conn.execute("ALTER TABLE tracks ADD COLUMN is_favorite INTEGER NOT NULL DEFAULT 0")
        conn.execute("PRAGMA user_version = 2")
        conn.commit()
        logger.info("Biblioteca migrada a esquema v2 (favoritos)")


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Garantiza el esquema vigente en ``conn`` (idempotente).

    Útil para conexiones propias de otros hilos (el escáner), que no
    pasan por :class:`LibraryDatabase`.
    """
    _migrate(conn)


# ------------------------------------------------------------------ mapping
def row_to_track(row: sqlite3.Row) -> Track:
    """Convierte una fila de ``tracks`` en :class:`Track`."""
    return Track(
        id=row["id"],
        path=row["path"],
        title=row["title"],
        artist=row["artist"],
        album=row["album"],
        albumartist=row["albumartist"],
        genre=row["genre"],
        year=row["year"],
        duration_ms=row["duration_ms"] or 0,
        track_no=row["track_no"],
        disc_no=row["disc_no"],
        bitrate=row["bitrate"],
        samplerate=row["samplerate"],
        channels=row["channels"],
        cover_path=row["cover_path"],
        file_size=row["file_size"],
        file_mtime=row["file_mtime"],
        added_at=row["added_at"],
        last_played_at=row["last_played_at"],
        play_count=row["play_count"] or 0,
        is_favorite=bool(row["is_favorite"] or 0),
    )


# ------------------------------------------------- operaciones (conexión)
def _resolve_artist(conn: sqlite3.Connection, name: str | None) -> int | None:
    """Devuelve el id del artista (creándolo si hace falta); None si no hay."""
    cleaned = str(name).strip() if name else ""
    if not cleaned:
        return None
    conn.execute("INSERT OR IGNORE INTO artists (name) VALUES (?)", (cleaned,))
    row = conn.execute("SELECT id FROM artists WHERE name = ?", (cleaned,)).fetchone()
    return int(row["id"]) if row is not None else None


def _resolve_album(
    conn: sqlite3.Connection, title: str | None, artist_id: int | None, year: str | None
) -> int | None:
    """Devuelve el id del álbum (creándolo si hace falta); None si no hay."""
    cleaned = str(title).strip() if title else ""
    if not cleaned:
        return None
    conn.execute(
        "INSERT OR IGNORE INTO albums (title, artist_id, year) VALUES (?, ?, ?)",
        (cleaned, artist_id, year),
    )
    row = conn.execute(
        "SELECT id FROM albums WHERE title = ? AND COALESCE(artist_id, 0) = COALESCE(?, 0)",
        (cleaned, artist_id),
    ).fetchone()
    return int(row["id"]) if row is not None else None


def upsert_track(conn: sqlite3.Connection, track: Track, *, commit: bool = True) -> int:
    """Inserta o actualiza la pista por ``path``, resolviendo artista/álbum.

    En actualización se conservan ``added_at``, ``play_count`` y
    ``last_played_at`` (el escáner no debe borrar las estadísticas).

    Args:
        conn: Conexión activa.
        track: Pista con metadatos leídos.
        commit: False para agrupar varios upserts (el escáner usa lotes).

    Returns:
        El id de la pista en la BD.
    """
    artist_id = _resolve_artist(conn, track.artist)
    album_id = _resolve_album(conn, track.album, artist_id, track.year)

    existing = conn.execute("SELECT id FROM tracks WHERE path = ?", (track.path,)).fetchone()
    fields = {
        "path": track.path,
        "title": track.title,
        "artist": track.artist,
        "album": track.album,
        "albumartist": track.albumartist,
        "genre": track.genre,
        "year": track.year,
        "duration_ms": max(0, int(track.duration_ms or 0)),
        "track_no": track.track_no,
        "disc_no": track.disc_no,
        "bitrate": track.bitrate,
        "samplerate": track.samplerate,
        "channels": track.channels,
        "cover_path": track.cover_path,
        "artist_id": artist_id,
        "album_id": album_id,
        "file_size": track.file_size,
        "file_mtime": track.file_mtime,
    }

    if existing is not None:
        track_id = int(existing["id"])
        conn.execute(
            """UPDATE tracks SET
                title = :title, artist = :artist, album = :album,
                albumartist = :albumartist, genre = :genre, year = :year,
                duration_ms = :duration_ms, track_no = :track_no,
                disc_no = :disc_no, bitrate = :bitrate,
                samplerate = :samplerate, channels = :channels,
                cover_path = :cover_path, artist_id = :artist_id,
                album_id = :album_id, file_size = :file_size,
                file_mtime = :file_mtime
            WHERE id = :id""",
            {**fields, "id": track_id},
        )
    else:
        cursor = conn.execute(
            """INSERT INTO tracks (
                path, title, artist, album, albumartist, genre, year,
                duration_ms, track_no, disc_no, bitrate, samplerate, channels,
                cover_path, artist_id, album_id, file_size, file_mtime,
                added_at, play_count
            ) VALUES (
                :path, :title, :artist, :album, :albumartist, :genre, :year,
                :duration_ms, :track_no, :disc_no, :bitrate, :samplerate,
                :channels, :cover_path, :artist_id, :album_id, :file_size,
                :file_mtime, :added_at, 0
            )""",
            {**fields, "added_at": now_iso()},
        )
        track_id = int(cursor.lastrowid or 0)

    # Si aparece carátula y el álbum aún no tenía, se hereda al álbum.
    if track.cover_path and album_id is not None:
        conn.execute(
            "UPDATE albums SET cover_path = ? WHERE id = ? AND cover_path IS NULL",
            (track.cover_path, album_id),
        )
    if commit:
        conn.commit()
    return track_id


def remove_missing_tracks(conn: sqlite3.Connection, existing_paths: set[str]) -> int:
    """Borra las pistas cuyo archivo ya no está en ``existing_paths``.

    Returns:
        Número de pistas eliminadas.
    """
    rows = conn.execute("SELECT path FROM tracks").fetchall()
    missing = [row["path"] for row in rows if row["path"] not in existing_paths]
    if not missing:
        return 0
    conn.executemany("DELETE FROM tracks WHERE path = ?", [(p,) for p in missing])
    conn.commit()
    logger.info("Biblioteca: %d pistas eliminadas (archivo ausente)", len(missing))
    return len(missing)


def cleanup_orphan_albums_artists(conn: sqlite3.Connection) -> tuple[int, int]:
    """Elimina álbumes/artistas sin pistas. Returns: (álbumes, artistas)."""
    cursor = conn.execute(
        "DELETE FROM albums WHERE id NOT IN "
        "(SELECT DISTINCT album_id FROM tracks WHERE album_id IS NOT NULL)"
    )
    albums_removed = max(0, cursor.rowcount)
    cursor = conn.execute(
        "DELETE FROM artists WHERE id NOT IN "
        "(SELECT DISTINCT artist_id FROM tracks WHERE artist_id IS NOT NULL)"
    )
    artists_removed = max(0, cursor.rowcount)
    conn.commit()
    return albums_removed, artists_removed


def record_play_by_path(conn: sqlite3.Connection, path: str) -> bool:
    """Suma una reproducción a la pista con ese ``path``.

    Returns:
        True si existía una pista con ese path en la biblioteca.
    """
    cursor = conn.execute(
        "UPDATE tracks SET play_count = play_count + 1, last_played_at = ? " "WHERE path = ?",
        (now_iso(), path),
    )
    conn.commit()
    return cursor.rowcount > 0


def toggle_favorite(conn: sqlite3.Connection, path: str) -> bool:
    """Alterna el favorito de la pista con ese ``path``.

    Si la pista aún no está en la biblioteca (música abierta sin escanear)
    se crea una fila mínima para poder marcarla igualmente.

    Returns:
        El nuevo estado (True = favorito).
    """
    row = conn.execute("SELECT is_favorite FROM tracks WHERE path = ?", (path,)).fetchone()
    if row is None:
        upsert_track(conn, Track(path=path), commit=False)
        conn.execute("UPDATE tracks SET is_favorite = 1 WHERE path = ?", (path,))
        conn.commit()
        logger.debug("Favorito creado para pista no indexada: %s", path)
        return True
    new_value = 0 if row["is_favorite"] else 1
    conn.execute("UPDATE tracks SET is_favorite = ? WHERE path = ?", (new_value, path))
    conn.commit()
    return bool(new_value)


def is_favorite(conn: sqlite3.Connection, path: str) -> bool:
    """True si la pista con ese ``path`` está marcada como favorita."""
    row = conn.execute("SELECT is_favorite FROM tracks WHERE path = ?", (path,)).fetchone()
    return bool(row["is_favorite"]) if row is not None else False


def _escape_like(term: str) -> str:
    """Escapa los comodines LIKE para búsqueda literal."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# --------------------------------------------------------------- fachada
class LibraryDatabase:
    """Fachada de la biblioteca sobre una conexión propia (hilo principal).

    Args:
        path: Ruta del .db (por defecto ``<datos>/PyAmp/library.db``).
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else DATABASE_FILE
        self._conn = open_connection(self._path)
        _migrate(self._conn)

    @property
    def path(self) -> str:
        """Ruta del archivo de base de datos."""
        return str(self._path)

    @property
    def connection(self) -> sqlite3.Connection:
        """Conexión activa (para repositorios de nivel superior)."""
        return self._conn

    def close(self) -> None:
        """Cierra la conexión.

        Ojo: no usar ``with self._conn`` aquí — el ``__exit__`` intentaría
        hacer commit tras el ``close()`` y lanzaría ``ProgrammingError``.
        """
        self._conn.close()

    # ---------------------------------------------------------- escritura
    def upsert_track(self, track: Track, *, commit: bool = True) -> int:
        """Inserta/actualiza una pista; devuelve su id."""
        return upsert_track(self._conn, track, commit=commit)

    def remove_missing_tracks(self, existing_paths: set[str]) -> int:
        """Borra pistas cuyo archivo ya no existe; devuelve el total."""
        return remove_missing_tracks(self._conn, existing_paths)

    def cleanup_orphan_albums_artists(self) -> tuple[int, int]:
        """Limpia álbumes/artistas huérfanos; devuelve (álbumes, artistas)."""
        return cleanup_orphan_albums_artists(self._conn)

    def record_play_by_path(self, path: str) -> bool:
        """Registra una reproducción por path (True si la pista existía)."""
        return record_play_by_path(self._conn, path)

    def toggle_favorite(self, path: str) -> bool:
        """Alterna el favorito por path; devuelve el nuevo estado."""
        return toggle_favorite(self._conn, path)

    def is_favorite(self, path: str) -> bool:
        """True si la pista con ese path está marcada como favorita."""
        return is_favorite(self._conn, path)

    def track_states(self) -> dict[str, tuple[int | None, int | None]]:
        """Mapa path → (mtime, size) para el escáner incremental."""
        rows = self._conn.execute("SELECT path, file_mtime, file_size FROM tracks").fetchall()
        return {row["path"]: (row["file_mtime"], row["file_size"]) for row in rows}

    # ------------------------------------------------------------- lectura
    def get_track(self, track_id: int) -> Track | None:
        """Pista por id o None."""
        row = self._conn.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
        return row_to_track(row) if row is not None else None

    def get_track_by_path(self, path: str) -> Track | None:
        """Pista por path o None."""
        row = self._conn.execute("SELECT * FROM tracks WHERE path = ?", (path,)).fetchone()
        return row_to_track(row) if row is not None else None

    def all_tracks(self, limit: int = 10000) -> list[Track]:
        """Todas las pistas ordenadas por artista/álbum/pista."""
        rows = self._conn.execute(
            """SELECT * FROM tracks
               ORDER BY artist COLLATE NOCASE, album COLLATE NOCASE,
                        track_no, title COLLATE NOCASE
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [row_to_track(row) for row in rows]

    def search_tracks(self, term: str, limit: int = 500) -> list[Track]:
        """Búsqueda por texto en título, artista o álbum (literal)."""
        cleaned = term.strip()
        if not cleaned:
            return []
        like = f"%{_escape_like(cleaned)}%"
        rows = self._conn.execute(
            """SELECT * FROM tracks
               WHERE title LIKE ? ESCAPE '\\'
                  OR artist LIKE ? ESCAPE '\\'
                  OR album LIKE ? ESCAPE '\\'
               ORDER BY artist COLLATE NOCASE, album COLLATE NOCASE, track_no
               LIMIT ?""",
            (like, like, like, limit),
        ).fetchall()
        return [row_to_track(row) for row in rows]

    def list_artists(self) -> list[Artist]:
        """Artistas con número de pistas."""
        rows = self._conn.execute("""SELECT a.id, a.name, COUNT(t.id) AS track_count
               FROM artists a
               LEFT JOIN tracks t ON t.artist_id = a.id
               GROUP BY a.id
               ORDER BY a.name COLLATE NOCASE""").fetchall()
        return [
            Artist(id=row["id"], name=row["name"], track_count=row["track_count"]) for row in rows
        ]

    def list_albums(self) -> list[Album]:
        """Álbumes con artista, año, carátula y número de pistas."""
        rows = self._conn.execute("""SELECT al.id, al.title, al.artist_id, ar.name AS artist_name,
                      al.year, al.cover_path, COUNT(t.id) AS track_count
               FROM albums al
               LEFT JOIN artists ar ON ar.id = al.artist_id
               LEFT JOIN tracks t ON t.album_id = al.id
               GROUP BY al.id
               ORDER BY al.title COLLATE NOCASE""").fetchall()
        return [
            Album(
                id=row["id"],
                title=row["title"],
                artist_id=row["artist_id"],
                artist_name=row["artist_name"],
                year=row["year"],
                cover_path=row["cover_path"],
                track_count=row["track_count"],
            )
            for row in rows
        ]

    # ------------------------------------------- consultas del árbol (Fase 3)
    def albums_by_artist(self, artist_id: int | None) -> list[Album]:
        """Álbumes con pistas de ese artista (None → pistas sin artista)."""
        if artist_id is None:
            where = "al.artist_id IS NULL"
            params: tuple[object, ...] = ()
        else:
            where = "al.artist_id = ?"
            params = (artist_id,)
        rows = self._conn.execute(
            f"""SELECT al.id, al.title, al.artist_id, ar.name AS artist_name,
                       al.year, al.cover_path, COUNT(t.id) AS track_count
                FROM albums al
                LEFT JOIN artists ar ON ar.id = al.artist_id
                LEFT JOIN tracks t ON t.album_id = al.id
                WHERE {where}
                GROUP BY al.id
                ORDER BY al.title COLLATE NOCASE""",
            params,
        ).fetchall()
        return [
            Album(
                id=row["id"],
                title=row["title"],
                artist_id=row["artist_id"],
                artist_name=row["artist_name"],
                year=row["year"],
                cover_path=row["cover_path"],
                track_count=row["track_count"],
            )
            for row in rows
        ]

    def tracks_by_album(self, album_id: int) -> list[Track]:
        """Pistas de un álbum ordenadas por nº de pista."""
        rows = self._conn.execute(
            "SELECT * FROM tracks WHERE album_id = ? " "ORDER BY track_no, title COLLATE NOCASE",
            (album_id,),
        ).fetchall()
        return [row_to_track(row) for row in rows]

    def tracks_without_album_by_artist(self, artist_id: int | None) -> list[Track]:
        """Pistas del artista (None → sin artista) que no tienen álbum."""
        if artist_id is None:
            where = "album_id IS NULL AND artist_id IS NULL"
            params: tuple[object, ...] = ()
        else:
            where = "album_id IS NULL AND artist_id = ?"
            params = (artist_id,)
        rows = self._conn.execute(
            f"SELECT * FROM tracks WHERE {where} ORDER BY title COLLATE NOCASE",
            params,
        ).fetchall()
        return [row_to_track(row) for row in rows]

    def count_tracks_without_artist(self) -> int:
        """Pistas sin artista asignado (bucket «(Sin artista)» del árbol)."""
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM tracks WHERE artist_id IS NULL"
        ).fetchone()
        return int(row["n"]) if row is not None else 0

    def stats(self) -> dict[str, int]:
        """Contadores de la biblioteca (pistas, artistas, álbumes, listas)."""
        result: dict[str, int] = {}
        for key, table in (
            ("tracks", "tracks"),
            ("artists", "artists"),
            ("albums", "albums"),
            ("playlists", "playlists"),
        ):
            row = self._conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
            result[key] = int(row["n"]) if row is not None else 0
        return result
