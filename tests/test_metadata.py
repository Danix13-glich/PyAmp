from __future__ import annotations

import base64
import wave
from pathlib import Path

import pytest
from mutagen.id3 import TALB, TDRC, TIT2, TPE1, TPOS, TRCK
from mutagen.wave import WAVE

from app.library.metadata import (
    MetadataError,
    extract_cover,
    format_audio_info,
    read_metadata,
)
from app.library.models import Track

# PNG de 1x1 píxel (base64) para simular una carátula incrustada.
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8"
    "z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _make_wav(path: Path, duration_s: float = 0.25, rate: int = 8000) -> Path:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * int(rate * duration_s))
    return path


def _tag_wav(path: Path, cover: bytes | None = None) -> Path:
    audio = WAVE(str(path))
    audio.add_tags()
    assert audio.tags is not None
    audio.tags.add(TIT2(encoding=3, text=["Canción de prueba"]))
    audio.tags.add(TPE1(encoding=3, text=["Artista de prueba"]))
    audio.tags.add(TALB(encoding=3, text=["Álbum de prueba"]))
    audio.tags.add(TDRC(encoding=3, text=["2024"]))
    audio.tags.add(TRCK(encoding=3, text=["3/10"]))
    audio.tags.add(TPOS(encoding=3, text=["2"]))
    if cover is not None:
        from mutagen.id3 import APIC

        audio.tags.add(APIC(encoding=3, mime="image/png", type=3, desc="Cover", data=cover))
    audio.save()
    return path


def test_read_tagged_wav(tmp_path: Path) -> None:
    path = _tag_wav(_make_wav(tmp_path / "cancion.wav"))
    track = read_metadata(path)

    assert track.title == "Canción de prueba"
    assert track.artist == "Artista de prueba"
    assert track.album == "Álbum de prueba"
    assert track.year == "2024"
    assert track.track_no == 3
    assert track.disc_no == 2
    assert 200 <= track.duration_ms <= 500  # WAV de 0,25 s
    assert track.samplerate == 8000
    assert track.channels == 1


def test_read_untagged_wav_falls_back_to_filename(tmp_path: Path) -> None:
    path = _make_wav(tmp_path / "Mi Cancion Bonita.wav")
    track = read_metadata(path)

    assert track.title is None
    assert track.artist is None
    assert track.display_title == "Mi Cancion Bonita"
    assert track.display_artist == "Artista desconocido"
    assert track.duration_ms > 0


def test_read_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(MetadataError):
        read_metadata(tmp_path / "no-existe.mp3")


def test_read_corrupt_file_does_not_crash(tmp_path: Path) -> None:
    broken = tmp_path / "roto.mp3"
    broken.write_bytes(b"esto no es un mp3 " * 100)

    track = read_metadata(broken)

    assert isinstance(track.title, type(None))
    assert track.path.endswith("roto.mp3")
    assert track.display_title == "roto"


def test_extract_cover_without_image_returns_none(tmp_path: Path) -> None:
    path = _make_wav(tmp_path / "sin-caratula.wav")
    assert extract_cover(path, dest_dir=tmp_path / "covers") is None


def test_extract_cover_returns_cached_file(tmp_path: Path) -> None:
    path = _tag_wav(_make_wav(tmp_path / "con-caratula.wav"), cover=TINY_PNG)
    dest = tmp_path / "covers"

    result = extract_cover(path, dest_dir=dest)

    assert result is not None
    assert Path(result).is_file()
    assert Path(result).read_bytes() == TINY_PNG
    # Caché: la segunda llamada devuelve el mismo archivo sin reescribirlo.
    assert extract_cover(path, dest_dir=dest) == result


def test_extract_cover_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(MetadataError):
        extract_cover(tmp_path / "no-existe.flac", dest_dir=tmp_path / "covers")


# ------------------------------------------- códec y texto real (ajustes)
def test_read_metadata_reports_real_codec(tmp_path: Path) -> None:
    path = _tag_wav(_make_wav(tmp_path / "codec-test.wav"))
    track = read_metadata(path)

    assert track.codec == "WAV"
    assert track.bitrate == 128000  # 8 kHz * 16 bit * 1 canal, real


def test_read_corrupt_file_has_no_codec(tmp_path: Path) -> None:
    broken = tmp_path / "roto-sin-codec.mp3"
    broken.write_bytes(b"esto no es un mp3 " * 100)

    track = read_metadata(broken)

    assert track.codec is None
    assert format_audio_info(track) == ""


def test_format_audio_info_builds_from_real_fields(tmp_path: Path) -> None:
    path = _tag_wav(_make_wav(tmp_path / "formato-test.wav", rate=8000))
    track = read_metadata(path)

    assert format_audio_info(track) == "WAV, mono, 8 kHz, 128 kbit/s"


def test_format_audio_info_omits_missing_fields() -> None:
    assert format_audio_info(Track(path="/x/a.mp3")) == ""
    assert (
        format_audio_info(Track(path="/x/a.mp3", codec="MPEG-1 layer 3", samplerate=44100))
        == "MPEG-1 layer 3, 44 kHz"
    )
    assert (
        format_audio_info(
            Track(path="/x/a.flac", codec="FLAC", channels=6, samplerate=96000, bitrate=1411200)
        )
        == "FLAC, 6 canales, 96 kHz, 1411 kbit/s"
    )
