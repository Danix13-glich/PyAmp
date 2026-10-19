from __future__ import annotations

import base64
import hashlib
import logging
from pathlib import Path
from typing import Any

import mutagen

from app.utils.paths import COVERS_DIR

logger = logging.getLogger(__name__)


class CoverError(Exception):
    pass


def _cover_bytes(audio: Any) -> tuple[bytes, str] | None:
    tags = audio.tags
    if tags is None:
        return None

    # ID3 (MP3, WAV, AIFF): APIC
    getall = getattr(tags, "getall", None)
    if callable(getall):
        try:
            pictures = getall("APIC")
        except Exception:  # noqa: BLE001 - IDs de tag malformados
            pictures = []
        if pictures:
            pic = pictures[0]
            data = bytes(pic.data)
            mime = str(pic.mime or "image/jpeg")
            if data:
                return data, mime

    # FLAC / Ogg (Vorbis): lista de pictures o metadata_block_picture base64
    pictures = getattr(tags, "pictures", None)
    if pictures:
        pic = pictures[0]
        data = bytes(pic.data)
        if data:
            return data, str(pic.mime or "image/jpeg")

    try:
        block = tags.get("metadata_block_picture") if hasattr(tags, "get") else None
    except Exception:  # noqa: BLE001
        block = None
    if block:
        raw_value = block[0] if isinstance(block, (list, tuple)) and block else block
        raw = raw_value if isinstance(raw_value, str) else str(raw_value)
        if raw:
            try:
                from mutagen.flac import Picture

                pic = Picture(base64.b64decode(raw))
                if pic.data:
                    return bytes(pic.data), str(pic.mime or "image/jpeg")
            except Exception as exc:  # noqa: BLE001
                logger.debug("metadata_block_picture ilegible: %s", exc)

    # MP4/M4A: covr (JPEG o PNG según primer byte)
    try:
        cover = tags.get("covr") if hasattr(tags, "get") else None
    except Exception:  # noqa: BLE001
        cover = None
    if cover:
        data = bytes(cover[0])
        if data:
            mime = "image/png" if data[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
            return data, mime

    return None


def extract_cover(path: str | Path, dest_dir: str | Path | None = None) -> str | None:
    file_path = Path(path).expanduser()
    if not file_path.is_file():
        raise CoverError(f"Archivo no encontrado: {path}")

    destination = Path(dest_dir) if dest_dir else COVERS_DIR
    destination.mkdir(parents=True, exist_ok=True)

    try:
        audio = mutagen.File(str(file_path))
    except Exception as exc:  # noqa: BLE001
        logger.debug("extract_cover: mutagen falló en %s: %s", file_path.name, exc)
        return None
    if audio is None:
        return None

    found = _cover_bytes(audio)
    if found is None:
        return None
    data, mime = found
    extension = "png" if "png" in mime.lower() else "jpg"
    digest = hashlib.sha1(str(file_path.resolve()).encode("utf-8")).hexdigest()[:16]
    target = destination / f"{digest}.{extension}"
    if target.is_file():
        return str(target)
    try:
        target.write_bytes(data)
    except OSError as exc:
        logger.warning("No se pudo guardar la carátula: %s", exc)
        return None
    logger.info("Carátula extraída: %s", target.name)
    return str(target)
