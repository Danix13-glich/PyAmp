from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from app.utils.paths import DATABASE_FILE

from .models import Album, Artist, Track

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 4

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
    return datetime.now().isoformat(timespec="seconds")


def current_month_key(moment: datetime | None = None) -> str:
    """Mes actual como ``AAAA-MM``."""
    return (moment or datetime.now()).strftime("%Y-%m")


def previous_month_key(moment: datetime | None = None) -> str:
    """Mes anterior (el último terminado) como ``AAAA-MM``."""
    reference = moment or datetime.now()
    first = reference.replace(day=1)
    previous = first - timedelta(days=1)
    return previous.strftime("%Y-%m")


def open_connection(path: str | Path) -> sqlite3.Connection:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    row = conn.execute("PRAGMA user_version").fetchone()
    version = int(row[0]) if row is not None else 0

    if version < 1:
        conn.executescript(_SCHEMA_V1)
        conn.execute("PRAGMA user_version = 1")
        conn.commit()
        logger.info("Biblioteca inicializada (esquema v1)")
        version = 1

    if version < 2:
        # Favoritos marcados por el usuario.
        conn.execute("ALTER TABLE tracks ADD COLUMN is_favorite INTEGER NOT NULL DEFAULT 0")
        conn.execute("PRAGMA user_version = 2")
        conn.commit()
        logger.info("Biblioteca migrada a esquema v2 (favoritos)")

    if version < 3:
        # Pistas ocultas por el usuario (Ajustes → Apariencia → Mostrar ocultos).
        conn.execute("ALTER TABLE tracks ADD COLUMN is_hidden INTEGER NOT NULL DEFAULT 0")
        conn.execute("PRAGMA user_version = 3")
        conn.commit()
        logger.info("Biblioteca migrada a esquema v3 (ocultos)")

    if version < 4:
        # Reproducciones contadas por mes (para el Historial mensual).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS play_history (
                month TEXT NOT NULL,
                path TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (month, path)
            )
            """)
        conn.execute("PRAGMA user_version = 4")
        conn.commit()
        logger.info("Biblioteca migrada a esquema v4 (historial mensual)")


def ensure_schema(conn: sqlite3.Connection) -> None:
    _migrate(conn)


# ------------------------------------------------------------------ mapping
def row_to_track(row: sqlite3.Row) -> Track:
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
        is_hidden=bool(row["is_hidden"] or 0),
    )


# ------------------------------------------------- operaciones (conexión)
def _resolve_artist(conn: sqlite3.Connection, name: str | None) -> int | None:
    cleaned = str(name).strip() if name else ""
    if not cleaned:
        return None
    conn.execute("INSERT OR IGNORE INTO artists (name) VALUES (?)", (cleaned,))
    row = conn.execute("SELECT id FROM artists WHERE name = ?", (cleaned,)).fetchone()
    return int(row["id"]) if row is not None else None


def _resolve_album(
    conn: sqlite3.Connection, title: str | None, artist_id: int | None, year: str | None
) -> int | None:
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
    rows = conn.execute("SELECT path FROM tracks").fetchall()
    missing = [row["path"] for row in rows if row["path"] not in existing_paths]
    if not missing:
        return 0
    conn.executemany("DELETE FROM tracks WHERE path = ?", [(p,) for p in missing])
    conn.commit()
    logger.info("Biblioteca: %d pistas eliminadas (archivo ausente)", len(missing))
    return len(missing)


def cleanup_orphan_albums_artists(conn: sqlite3.Connection) -> tuple[int, int]:
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
    cursor = conn.execute(
        "UPDATE tracks SET play_count = play_count + 1, last_played_at = ? " "WHERE path = ?",
        (now_iso(), path),
    )
    # Contador mensual para el Historial (se guarda aunque la pista se borre).
    conn.execute(
        """INSERT INTO play_history (month, path, count) VALUES (?, ?, 1)
           ON CONFLICT(month, path) DO UPDATE SET count = count + 1""",
        (current_month_key(), path),
    )
    conn.commit()
    return cursor.rowcount > 0


def monthly_top(conn: sqlite3.Connection, month: str, limit: int = 10) -> list[dict[str, object]]:
    rows = conn.execute(
        """SELECT h.path AS path, h.count AS count, t.title AS title, t.artist AS artist
           FROM play_history h
           LEFT JOIN tracks t ON t.path = h.path
           WHERE h.month = ?
           ORDER BY h.count DESC, h.path
           LIMIT ?""",
        (month, limit),
    ).fetchall()
    return [
        {
            "path": row["path"],
            "count": int(row["count"]),
            "title": row["title"],
            "artist": row["artist"],
        }
        for row in rows
    ]


def toggle_favorite(conn: sqlite3.Connection, path: str) -> bool:
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
    row = conn.execute("SELECT is_favorite FROM tracks WHERE path = ?", (path,)).fetchone()
    return bool(row["is_favorite"]) if row is not None else False


def favorite_tracks(conn: sqlite3.Connection, limit: int = 10000) -> list[Track]:
    rows = conn.execute(
        """SELECT * FROM tracks WHERE is_favorite = 1
           ORDER BY artist COLLATE NOCASE, album COLLATE NOCASE,
                    track_no, title COLLATE NOCASE
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [row_to_track(row) for row in rows]


def set_hidden(conn: sqlite3.Connection, path: str, hidden: bool) -> bool:
    cursor = conn.execute(
        "UPDATE tracks SET is_hidden = ? WHERE path = ?", (1 if hidden else 0, path)
    )
    conn.commit()
    return cursor.rowcount > 0


def remove_track(conn: sqlite3.Connection, path: str) -> bool:
    cursor = conn.execute("DELETE FROM tracks WHERE path = ?", (path,))
    conn.commit()
    return cursor.rowcount > 0


def reset_library(conn: sqlite3.Connection) -> None:
    # Orden seguro con claves foráneas: primero las tablas dependientes.
    with conn:
        conn.execute("DELETE FROM playlist_tracks")
        conn.execute("DELETE FROM playlists")
        conn.execute("DELETE FROM play_history")
        conn.execute("DELETE FROM tracks")
        conn.execute("DELETE FROM albums")
        conn.execute("DELETE FROM artists")
    logger.info("Biblioteca restablecida: canciones, favoritos, listas e historial eliminados")


def rename_track_path(conn: sqlite3.Connection, old_path: str, new_path: str) -> bool:
    cursor = conn.execute("UPDATE tracks SET path = ? WHERE path = ?", (new_path, old_path))
    conn.commit()
    return cursor.rowcount > 0


def update_track_fields(conn: sqlite3.Connection, path: str, fields: dict[str, object]) -> bool:
    allowed = {
        "title",
        "artist",
        "album",
        "albumartist",
        "genre",
        "year",
        "track_no",
        "disc_no",
    }
    clean = {key: value for key, value in fields.items() if key in allowed}
    if not clean:
        return False
    artist_id = _resolve_artist(conn, str(clean.get("artist") or ""))
    album_id = _resolve_album(
        conn,
        str(clean.get("album") or ""),
        artist_id,
        str(clean.get("year") or "") or None,
    )
    assignments = ", ".join(f"{key} = :{key}" for key in clean)
    params: dict[str, object] = {**clean, "path": path}
    sets = f"{assignments}, artist_id = :artist_id, album_id = :album_id"
    params["artist_id"] = artist_id
    params["album_id"] = album_id
    cursor = conn.execute(f"UPDATE tracks SET {sets} WHERE path = :path", params)
    conn.commit()
    return cursor.rowcount > 0


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# --------------------------------------------------------------- fachada
class LibraryDatabase:

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else DATABASE_FILE
        self._conn = open_connection(self._path)
        _migrate(self._conn)

    @property
    def path(self) -> str:
        return str(self._path)

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    def close(self) -> None:
        self._conn.close()

    # ---------------------------------------------------------- escritura
    def upsert_track(self, track: Track, *, commit: bool = True) -> int:
        return upsert_track(self._conn, track, commit=commit)

    def remove_missing_tracks(self, existing_paths: set[str]) -> int:
        return remove_missing_tracks(self._conn, existing_paths)

    def cleanup_orphan_albums_artists(self) -> tuple[int, int]:
        return cleanup_orphan_albums_artists(self._conn)

    def record_play_by_path(self, path: str) -> bool:
        return record_play_by_path(self._conn, path)

    def monthly_top(self, month: str, limit: int = 10) -> list[dict[str, object]]:
        return monthly_top(self._conn, month, limit)

    def toggle_favorite(self, path: str) -> bool:
        return toggle_favorite(self._conn, path)

    def is_favorite(self, path: str) -> bool:
        return is_favorite(self._conn, path)

    def favorite_tracks(self, limit: int = 10000) -> list[Track]:
        return favorite_tracks(self._conn, limit)

    def set_hidden(self, path: str, hidden: bool) -> bool:
        return set_hidden(self._conn, path, hidden)

    def remove_track(self, path: str) -> bool:
        return remove_track(self._conn, path)

    def reset(self) -> None:
        reset_library(self._conn)

    def rename_track_path(self, old_path: str, new_path: str) -> bool:
        return rename_track_path(self._conn, old_path, new_path)

    def update_track_fields(self, path: str, fields: dict[str, object]) -> bool:
        return update_track_fields(self._conn, path, fields)

    def track_states(self) -> dict[str, tuple[int | None, int | None]]:
        rows = self._conn.execute("SELECT path, file_mtime, file_size FROM tracks").fetchall()
        return {row["path"]: (row["file_mtime"], row["file_size"]) for row in rows}

    # ------------------------------------------------------------- lectura
    def get_track(self, track_id: int) -> Track | None:
        row = self._conn.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
        return row_to_track(row) if row is not None else None

    def get_track_by_path(self, path: str) -> Track | None:
        row = self._conn.execute("SELECT * FROM tracks WHERE path = ?", (path,)).fetchone()
        return row_to_track(row) if row is not None else None

    def all_tracks(self, limit: int = 10000) -> list[Track]:
        rows = self._conn.execute(
            """SELECT * FROM tracks
               ORDER BY artist COLLATE NOCASE, album COLLATE NOCASE,
                        track_no, title COLLATE NOCASE
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [row_to_track(row) for row in rows]

    def search_tracks(self, term: str, limit: int = 500) -> list[Track]:
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
        rows = self._conn.execute("""SELECT a.id, a.name, COUNT(t.id) AS track_count
               FROM artists a
               LEFT JOIN tracks t ON t.artist_id = a.id
               GROUP BY a.id
               ORDER BY a.name COLLATE NOCASE""").fetchall()
        return [
            Artist(id=row["id"], name=row["name"], track_count=row["track_count"]) for row in rows
        ]

    def list_artists_grouped(self) -> list[Artist]:
        rows = self._conn.execute("""SELECT a.name, COUNT(t.id) AS track_count
               FROM artists a
               LEFT JOIN tracks t ON t.artist_id = a.id
               GROUP BY a.id""").fetchall()
        names: dict[str, str] = {}
        counts: dict[str, int] = {}
        for row in rows:
            count = int(row["track_count"])
            for part in str(row["name"]).split(","):
                token = part.strip()
                if not token:
                    continue
                key = token.casefold()
                names.setdefault(key, token)
                counts[key] = counts.get(key, 0) + count
        return [
            Artist(id=None, name=names[key], track_count=counts[key])
            for key in sorted(names, key=lambda key: names[key].casefold())
        ]

    def artist_ids_by_name(self, name: str) -> list[int]:
        key = str(name).strip().casefold()
        if not key:
            return []
        rows = self._conn.execute("SELECT id, name FROM artists").fetchall()
        artist_ids: list[int] = []
        for row in rows:
            tokens = [part.strip().casefold() for part in str(row["name"]).split(",")]
            if key in tokens:
                artist_ids.append(int(row["id"]))
        return artist_ids

    def list_albums(self) -> list[Album]:
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

    # ------------------------------------------------ consultas del árbol
    def albums_by_artist(self, artist_id: int | None) -> list[Album]:
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

    def albums_by_artist_name(self, name: str | None) -> list[Album]:
        if name is None:
            rows = self._conn.execute(
                """SELECT al.title, al.year, al.cover_path, COUNT(t.id) AS track_count
                   FROM albums al
                   LEFT JOIN tracks t ON t.album_id = al.id
                   WHERE al.artist_id IS NULL
                   GROUP BY al.id"""
            ).fetchall()
        else:
            artist_ids = self.artist_ids_by_name(name)
            if not artist_ids:
                return []
            placeholders = ",".join("?" * len(artist_ids))
            rows = self._conn.execute(
                f"""SELECT al.title, al.year, al.cover_path, COUNT(t.id) AS track_count
                    FROM albums al
                    LEFT JOIN tracks t ON t.album_id = al.id
                    WHERE al.artist_id IN ({placeholders})
                    GROUP BY al.id""",
                tuple(artist_ids),
            ).fetchall()
        merged: dict[str, Album] = {}
        for row in rows:
            title = str(row["title"])
            key = title.casefold()
            count = int(row["track_count"])
            album = merged.get(key)
            if album is None:
                merged[key] = Album(
                    title=title,
                    artist_name=name,
                    year=row["year"],
                    cover_path=row["cover_path"],
                    track_count=count,
                )
            else:
                album.track_count += count
        return sorted(merged.values(), key=lambda album: album.title.casefold())

    def tracks_by_artist_name_and_album(self, name: str | None, album_title: str) -> list[Track]:
        if name is None:
            rows = self._conn.execute(
                """SELECT t.* FROM tracks t JOIN albums al ON al.id = t.album_id
                   WHERE t.artist_id IS NULL AND al.title = ? COLLATE NOCASE
                   ORDER BY t.track_no, t.title COLLATE NOCASE""",
                (album_title,),
            ).fetchall()
        else:
            artist_ids = self.artist_ids_by_name(name)
            if not artist_ids:
                return []
            placeholders = ",".join("?" * len(artist_ids))
            rows = self._conn.execute(
                f"""SELECT t.* FROM tracks t JOIN albums al ON al.id = t.album_id
                    WHERE t.artist_id IN ({placeholders}) AND al.title = ? COLLATE NOCASE
                    ORDER BY t.track_no, t.title COLLATE NOCASE""",
                (*artist_ids, album_title),
            ).fetchall()
        return [row_to_track(row) for row in rows]

    def tracks_by_album(self, album_id: int) -> list[Track]:
        rows = self._conn.execute(
            "SELECT * FROM tracks WHERE album_id = ? " "ORDER BY track_no, title COLLATE NOCASE",
            (album_id,),
        ).fetchall()
        return [row_to_track(row) for row in rows]

    def tracks_without_album_by_artist(self, artist_id: int | None) -> list[Track]:
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

    def tracks_without_album_by_artist_name(self, name: str | None) -> list[Track]:
        if name is None:
            return self.tracks_without_album_by_artist(None)
        artist_ids = self.artist_ids_by_name(name)
        if not artist_ids:
            return []
        placeholders = ",".join("?" * len(artist_ids))
        rows = self._conn.execute(
            "SELECT * FROM tracks WHERE album_id IS NULL"
            f" AND artist_id IN ({placeholders}) ORDER BY title COLLATE NOCASE",
            tuple(artist_ids),
        ).fetchall()
        return [row_to_track(row) for row in rows]

    def count_tracks_without_artist(self) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM tracks WHERE artist_id IS NULL"
        ).fetchone()
        return int(row["n"]) if row is not None else 0

    def stats(self) -> dict[str, int]:
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
