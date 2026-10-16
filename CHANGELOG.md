# Changelog

Todo notable de PyAmp se documenta aquí.

El formato se basa en [Keep a Changelog](https://keepachangelog.com/es-1.1.0/),
y el proyecto sigue [SemVer](https://semver.org/lang/es/spec/v2.0.0.html).

## [Unreleased]

### Added
- Estructura inicial del proyecto (Fase 0).
- `main.py` que abre una ventana vacía titulada "PyAmp".
- `src/app/version.py` con `__version__ = "0.1.0"`.
- `src/app/notifications/notifier.py`: interfaz completa y `format_track_notification` (PyAmp / título / artista).
- Configuración de proyecto: `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`.
- CI en GitHub Actions (ruff + black + mypy + pytest) en Linux, Windows y macOS (Python 3.11 y 3.12).
- Plantillas de issues y pull requests.
- Documentación inicial: README (EN/ES), CONTRIBUTING, CODE_OF_CONDUCT, SECURITY.
- **Fase 1 — reproducción y notificaciones**:
  - `src/app/audio/base_backend.py`: interfaz abstracta `AudioBackend` + `BackendError`.
  - `src/app/audio/vlc_backend.py`: backend libVLC (play/pause/stop/seek/volumen/mute, eventos de fin y error).
  - `src/app/core/player.py`: fachada con señales Qt (`track_changed`, `playback_state_changed`, `position_changed`, `duration_changed`, `volume_changed`, `error_occurred`); auto-avance al terminar pista; `track_changed` SOLO en cambio real de pista (no en pausa/reanudar).
  - `src/app/core/signals.py`: bus global `app_signals` (reenvío de `track_changed`).
  - `src/app/core/playlist.py`: playlist en memoria + carga/guardado `.m3u` extendido + `collect_audio_files`.
  - `src/app/core/settings.py`: persistencia con QSettings (volumen, mute, playlist, geometría, claves de notificaciones).
  - `src/app/library/models.py`: dataclass `Track` con `display_title`/`display_artist`.
  - `src/app/library/metadata.py`: lectura con mutagen (título, artista, álbum, año, pista, duración, bitrate, kHz, canales) y extracción de carátulas cacheadas.
  - `src/app/utils/paths.py`, `src/app/utils/time_format.py`, `src/app/utils/logging.py`.
  - `src/app/notifications/linux_notifier.py`: notificaciones nativas D-Bus (dbus-next, hilo propio, hint `suppress-sound`, carátula `image-data`).
  - `src/app/notifications/windows_notifier.py` y `macos_notifier.py`: stubs con TODO para Fase 8.
  - `src/app/ui/main_window.py`: UI mínima (abrir archivo/carpeta en QThread, transporte, seek, volumen, mute, lista, `.m3u`, QSettings) + única conexión `track_changed → Notifier`.
  - Tests: `tests/test_metadata.py` (fixtures WAV generados) — total 16 tests.

### Fixed
- Workaround en `VlcBackend`: libVLC (Fedora 44, VLC 3.0.23) hace SIGSEGV si se llama `audio_set_volume`/`audio_set_mute` antes de existir la salida de audio; el volumen/mute se difiere hasta que `is_playing()` es True.
- `_stringify` de metadatos: `ID3TimeStamp.text` es `str` (no se debe iterar como lista; provocaba año `"2"` en lugar de `"2024"`).

[Unreleased]: https://github.com/Danix13-glich/PyAmp/compare/v0.1.0...HEAD
