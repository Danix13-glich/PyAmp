from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal

from .covers import extract_cover
from .database import (
    cleanup_orphan_albums_artists,
    ensure_schema,
    open_connection,
    remove_missing_tracks,
    upsert_track,
)
from .metadata import AUDIO_EXTENSIONS, read_metadata
from .models import Track

logger = logging.getLogger(__name__)

#: Archivos procesados entre commits/avisos de progreso.
BATCH_SIZE = 25


class ScannerThread(QThread):

    progress = Signal(int, str)
    scan_error = Signal(str)
    scan_finished = Signal(object)

    def __init__(self, db_path: str, folder: str, parent: Any = None) -> None:
        super().__init__(parent)
        self._db_path = db_path
        self._folder = folder
        self._cancel_requested = False

    def cancel(self) -> None:
        logger.info("Escáner: cancelación solicitada")
        self._cancel_requested = True

    # ---------------------------------------------------------------- hilo
    def run(self) -> None:
        summary: dict[str, Any] = {
            "found": 0,
            "added": 0,
            "updated": 0,
            "skipped": 0,
            "removed": 0,
            "errors": 0,
            "cancelled": False,
        }
        conn = None
        try:
            folder = Path(self._folder).expanduser()
            if not folder.is_dir():
                raise ValueError(f"Carpeta no válida: {self._folder}")
            conn = open_connection(self._db_path)
            ensure_schema(conn)
            self._scan(folder, conn, summary)
        except Exception as exc:  # noqa: BLE001 - un fallo no debe tumbar la app
            logger.error("Escáner falló: %s", exc)
            summary["errors"] += 1
            self.scan_error.emit(str(exc))
        finally:
            if conn is not None:
                with contextlib.suppress(Exception):
                    conn.close()
        self.scan_finished.emit(summary)

    def _scan(self, folder: Path, conn: Any, summary: dict[str, Any]) -> None:
        existing = _track_states(conn)
        seen: set[str] = set()
        processed = 0

        for path in folder.rglob("*"):
            if self._cancel_requested:
                summary["cancelled"] = True
                break
            if not path.is_file() or path.suffix.lower() not in AUDIO_EXTENSIONS:
                continue
            summary["found"] += 1
            resolved = str(path.resolve())
            seen.add(resolved)

            try:
                stat = path.stat()
                mtime = int(stat.st_mtime)
                size = stat.st_size
            except OSError as exc:
                logger.warning("Escáner: no se pudo leer %s: %s", path, exc)
                summary["errors"] += 1
                continue

            stored = existing.get(resolved)
            processed += 1
            if stored == (mtime, size):
                summary["skipped"] += 1
            else:
                track = _read_track(path, resolved, mtime, size)
                if track is None:
                    summary["errors"] += 1
                else:
                    upsert_track(conn, track, commit=False)
                    summary["updated" if stored is not None else "added"] += 1

            if processed % BATCH_SIZE == 0:
                conn.commit()
                self.progress.emit(processed, path.name)

        conn.commit()
        self.progress.emit(processed, "…")

        if not summary["cancelled"]:
            summary["removed"] = remove_missing_tracks(conn, set(seen))
            cleanup_orphan_albums_artists(conn)
        logger.info(
            "Escáner finalizado: %(found)s encontradas, %(added)s añadidas, "
            "%(updated)s actualizadas, %(skipped)s sin cambios, %(removed)s "
            "eliminadas, %(errors)s errores, cancelado=%(cancelled)s",
            summary,
        )


def _track_states(conn: Any) -> dict[str, tuple[int | None, int | None]]:
    rows = conn.execute("SELECT path, file_mtime, file_size FROM tracks").fetchall()
    return {row["path"]: (row["file_mtime"], row["file_size"]) for row in rows}


def _read_track(path: Path, resolved: str, mtime: int, size: int) -> Track | None:
    try:
        track = read_metadata(resolved)
        track.file_mtime = mtime
        track.file_size = size
        track.cover_path = extract_cover(resolved)
    except Exception as exc:  # noqa: BLE001 - corruptos no rompen el escaneo
        logger.warning("Escáner: metadatos ilegibles en %s: %s", path.name, exc)
        return None
    return track
