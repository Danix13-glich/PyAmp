from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import mutagen

from .covers import CoverError
from .covers import extract_cover as _extract_cover
from .models import Track

logger = logging.getLogger(__name__)

__all__ = ["MetadataError", "read_metadata", "extract_cover", "AUDIO_EXTENSIONS"]

#: Extensiones que PyAmp reconoce como audio (fuente única del proyecto:
#: la playlist y el escáner de la biblioteca la importan de aquí).
AUDIO_EXTENSIONS = frozenset(
    {
        ".mp3",
        ".flac",
        ".ogg",
        ".oga",
        ".opus",
        ".m4a",
        ".aac",
        ".wav",
        ".aiff",
        ".aif",
        ".wma",
    }
)


class MetadataError(Exception):
    pass


# --------------------------------------------------------------------- tags
# Cada campo en varios dialectos: fácil (mutagen easy), ID3 y MP4.
_TITLE_KEYS = ("title", "TIT2", "©nam")
_ARTIST_KEYS = ("artist", "TPE1", "©ART")
_ALBUM_KEYS = ("album", "TALB", "©alb")
_ALBUMARTIST_KEYS = ("albumartist", "TPE2", "aART")
_GENRE_KEYS = ("genre", "TGEN", "©gen")
_YEAR_KEYS = ("date", "year", "TDRC", "TYER", "©day")
_TRACKNO_KEYS = ("tracknumber", "TRCK", "trkn")
_DISCNO_KEYS = ("discnumber", "TPOS", "disk")


def _stringify(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip() or None
    if isinstance(value, (list, tuple)) and value:
        return _stringify(value[0])
    text = getattr(value, "text", None)  # frame ID3 (TIT2, TPE1...) o ID3TimeStamp
    if isinstance(text, str):
        # ID3TimeStamp.text es un str crudo: NUNCA list() (list('2024') = ['2',...])
        return text.strip() or None
    if text is not None:
        return _stringify(list(text))
    if isinstance(value, str):
        return value.strip() or None
    return str(value).strip() or None


def _first_tag(tags: Any, keys: tuple[str, ...]) -> str | None:
    if not tags:
        return None
    for key in keys:
        try:
            if key in tags:
                result = _stringify(tags[key])
                if result:
                    return result
        except (TypeError, KeyError, AttributeError):
            continue
    return None


def _to_int(value: Any) -> int | None:
    text = _stringify(value)
    if text is None:
        return None
    head = text.split("/")[0].strip()
    try:
        return int(head)
    except ValueError:
        return None


# ------------------------------------------------------------------ lectura
#: Códec por clase concreta que mutagen detecta al abrir el archivo.
_CODEC_BY_CLASS = {
    "AIFF": "AIFF",
    "FLAC": "FLAC",
    "MP4": "AAC",
    "OggFLAC": "FLAC",
    "OggOpus": "Opus",
    "OggVorbis": "OGG Vorbis",
    "WAVE": "WAV",
}


def _codec_name(audio: object) -> str | None:
    name = type(audio).__name__
    if name == "MP3":
        info = getattr(audio, "info", None)
        version = getattr(info, "version", None)
        layer = getattr(info, "layer", None)
        if version and layer:
            label = {1: "1", 2: "2", 2.5: "2.5"}.get(version, str(version))
            return f"MPEG-{label} layer {layer}"
        return "MPEG" if version else None
    return _CODEC_BY_CLASS.get(name)


def format_audio_info(track: Track) -> str:
    parts = [track.codec] if track.codec else []
    if track.channels == 1:
        parts.append("mono")
    elif track.channels == 2:
        parts.append("estéreo")
    elif track.channels:
        parts.append(f"{track.channels} canales")
    if track.samplerate:
        parts.append(f"{round(track.samplerate / 1000)} kHz")
    if track.bitrate:
        parts.append(f"{round(track.bitrate / 1000)} kbit/s")
    return ", ".join(parts)


def read_metadata(path: str | Path) -> Track:
    file_path = Path(path).expanduser()
    if not file_path.is_file():
        raise MetadataError(f"Archivo no encontrado: {path}")

    track = Track(path=str(file_path.resolve()))

    try:
        audio = mutagen.File(str(file_path))
    except Exception as exc:  # noqa: BLE001 - archivos corruptos: no crash
        logger.warning("Metadatos ilegibles (%s): %s", file_path.name, exc)
        return track
    if audio is None:
        logger.warning("Formato no soportado por mutagen: %s", file_path.name)
        return track

    tags = audio.tags
    track.codec = _codec_name(audio)
    track.title = _first_tag(tags, _TITLE_KEYS)
    track.artist = _first_tag(tags, _ARTIST_KEYS)
    track.album = _first_tag(tags, _ALBUM_KEYS)
    track.albumartist = _first_tag(tags, _ALBUMARTIST_KEYS)
    track.genre = _first_tag(tags, _GENRE_KEYS)
    track.year = _first_tag(tags, _YEAR_KEYS)
    track.track_no = _to_int(_first_tag(tags, _TRACKNO_KEYS))
    track.disc_no = _to_int(_first_tag(tags, _DISCNO_KEYS))

    info = getattr(audio, "info", None)
    if info is not None:
        length = getattr(info, "length", None)
        if length:
            track.duration_ms = int(round(float(length) * 1000))
        bitrate = getattr(info, "bitrate", None)
        if bitrate:
            track.bitrate = int(bitrate)
        samplerate = getattr(info, "sample_rate", None) or getattr(info, "samplerate", None)
        if samplerate:
            track.samplerate = int(samplerate)
        channels = getattr(info, "channels", None)
        if channels:
            track.channels = int(channels)

    return track


# ---------------------------------------------------------------- carátula
def extract_cover(path: str | Path, dest_dir: str | Path | None = None) -> str | None:
    try:
        return _extract_cover(path, dest_dir)
    except CoverError as exc:
        raise MetadataError(str(exc)) from exc
