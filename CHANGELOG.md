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
- **Fase 2 — biblioteca (SQLite, escáner, carátulas)**:
  - `src/app/library/models.py` ampliado: campos de gestión en `Track` (`file_size`, `file_mtime`, `added_at`, `last_played_at`) y nuevos dataclasses `Artist`, `Album`, `Playlist`.
  - `src/app/library/database.py`: SQLite en `<datos>/PyAmp/library.db` (WAL + foreign keys), migraciones por `PRAGMA user_version` (v1), CRUD de pistas (upsert incremental preserva estadísticas, borrado de ausentes, limpieza de álbumes/artistas huérfanos), búsqueda literal, `list_artists`/`list_albums`/`stats`, `record_play_by_path`.
  - `src/app/library/covers.py`: extracción de carátulas movida aquí desde `metadata.py` (única implementación; `metadata.extract_cover` delega por compatibilidad con la Fase 1).
  - `src/app/library/scanner.py`: `ScannerThread` (QThread) — escaneo recursivo incremental por `(mtime, size)`, progreso y cancelación, conexión propia por hilo, commits por lotes, extrae carátulas y elimina archivos desaparecidos.
  - `src/app/library/playlist_repository.py`: playlists con nombre en SQLite (crear/borrar/renombrar/contenido ordenado) complementarias a los `.m3u`.
  - `src/app/ui/main_window.py`: menú «Archivo → Escanear carpeta en biblioteca...» con progreso en la barra de estado, y wiring `track_changed → record_play_by_path` (estadísticas en cada cambio real de pista).
  - `AUDIO_EXTENSIONS` movido de `core/playlist.py` a `library/metadata.py` (fuente única; la playlist lo reimporta por compatibilidad).
  - Tests: `tests/test_database.py` (esquema, CRUD, cascadas, playlists, escáner incremental/cancelación) — total 32 tests.
- **Fase 3 — UI de biblioteca**:
  - `src/app/ui/library_panel.py`: `LibraryPanel` con árbol **Artista → Álbum → Pista** de carga perezosa (artistas al mostrar; álbumes y pistas al expandir), buckets «(Sin artista)»/«(Sin álbum)», búsqueda en vivo con debounce (vista plana, tope 500 con aviso), contador de totales y botón de refresco; señales `track_activated(track, contexto)` y `selection_changed`.
  - `src/app/ui/cover_widget.py`: `CoverLabel` — carátula cuadrada 64 px escalada con placeholder.
  - `src/app/core/player.py`: `replace_playlist(tracks, start_index)` — la biblioteca reemplaza la playlist visible y reproduce (auto-avance continúa en ese contexto).
  - `src/app/library/database.py`: consultas del árbol (`albums_by_artist`, `tracks_by_album`, `tracks_without_album_by_artist`, `count_tracks_without_artist`).
  - `src/app/ui/main_window.py`: splitter biblioteca|playlist, carátula en la fila de información (pista sonando o selección), wiring doble clic → playlist, refresco automático tras escanear.
  - `src/app/core/settings.py`: clave `window/splitter_state` (tamaño del splitter al reabrir).
  - Tests: `tests/test_library_panel.py` (árbol perezoso, búsqueda, activación con contexto, selección, carátulas, `replace_playlist`) — total 42 tests.
- **Fase 4 — vistas, ajustes, favoritos y espectro**:
  - `src/app/ui/songs_table.py`: vista «Canciones» — `QAbstractTableModel` + `QSortFilterProxyModel` con columnas Nombre | Duración | Artista | ★; la duración **ordena por milisegundos** (no texto), el filtro de búsqueda es local y debounce; doble clic/Enter reproduce con el contexto visible; doble clic sobre ★ alterna el favorito; etiquetas de vacío/sin resultados y contador.
  - `src/app/ui/settings_dialog.py`: «Editar → Ajustes...» (Ctrl+,) — notificaciones on/off, duración 1–60 s, botón «Probar notificación» (pasa por el MISMO `Notifier`), información de versión/backend/biblioteca; la ventana aplica los cambios al vuelo y los persiste en QSettings.
  - `src/app/ui/spectrum_widget.py`: espectrograma de barras (numpy + QPainter, 40 barras, FFT log 40 Hz–16 kHz, ~30 fps) alimentado por **captura real** de la salida del sistema (`parec` sobre el monitor del sink por defecto vía `pactl`, típico en Fedora/PipeWire); sin `parec`/`pactl` muestra «Espectro no disponible» (nunca anima datos inventados); la lectura va en hilo propio y `shutdown()` termina el proceso al cerrar.
  - Favoritos: migración de BD **v2** (`ALTER TABLE tracks ADD COLUMN is_favorite`), `Track.is_favorite`, `toggle_favorite`/`is_favorite` (crea una fila mínima si el path aún no está indexado) y upsert que **preserva** el favorito en re-escaneos; botón ★ en la barra de transporte sincronizado con la pista actual y columna ★ en la tabla.
  - Play/pausa unificado en un solo botón con icono dinámico (▶/⏸), tooltip por estado y etiqueta de estado «▶ Reproduciendo / ⏸ En pausa / ■ Detenido» junto al tiempo.
  - Atajos de transporte: F9 (anterior), F10 (reproducir/pausar), F11 (siguiente) y teclas multimedia (Play/Pause/Next/Previous/Toggle) con `ApplicationShortcut`; construidos con enums `Qt.Key` (el parse por nombre «MediaPlay» no es portable en Qt6).
  - Menú «Ver»: Canciones (Ctrl+1, por defecto) y Biblioteca (Ctrl+2) en `QStackedWidget` a todo el ancho, con vista persistida en `ui/view_mode`.
  - «Archivo → Abrir carpeta...» además lanza el escáner de biblioteca en segundo plano (`_start_scan` compartido), de modo que las canciones siempre aparecen en la vista Canciones.
  - Tests: favoritos/migración en `tests/test_database.py`; tabla, ajustes y espectro en `tests/test_library_panel.py` — total 54 tests.
- **Fase 5 — ajustes de interfaz, MPRIS y letras** (versión **0.1.4**):
  - Política de versionado: cada componente MAYOR.MENOR.PARCHE es un solo
    dígito (0–9); cada cambio del programa sube el parche y al desbordarse
    conmuta el siguiente componente (0.1.9 → 0.2.0). Declarada en
    `src/app/version.py` (fuente única) y `pyproject.toml`.
  - **Cabecera estilo Winamp** (panel oscuro `#17171b`, radio 6 px): a la
    izquierda la carátula; título en blanco grande y negrita, artista y
    álbum en gris debajo; **espectrograma integrado a la derecha**; y una
    franja inferior con el formato técnico del audio a la izquierda
    («MPEG-1 layer 3, estéreo, 44 kHz, 128 kbit/s», derivado de la
    extensión + metadatos mutagen) y el tiempo a la derecha. El texto ya
    no está fijado a 148 px: ocupa el espacio hasta el espectrograma.
  - `src/app/core/mpris.py`: integración **MPRIS v2** (`org.mpris.MediaPlayer2.pyamp`, dbus-next en hilo propio con event loop asyncio) — el sistema (Plasma/KDE) reconoce a PyAmp como reproductor: widget multimedia del sistema, volumen global y teclas de hardware; comandos Play/Pause/PlayPause/Stop/Next/Previous/Seek/SetPosition, propiedades PlaybackStatus/Metadata/Volume/Position y señal Seeked; fallo silencioso si no hay sesión D-Bus.
  - `src/app/ui/lyrics_window.py`: «Ver → Ver letra» (Ctrl+L) — ventana modeless junto a la principal con **letra LRC local sincronizada** (busca `cancion.lrc` junto al audio y en `<datos>/PyAmp/lyrics/`); línea activa resaltada en negrita azul según la posición; parser `parse_lrc` puro (metatags ignorados, múltiples marcas por línea).
  - `src/app/ui/spectrum_widget.py`: ecualizador compacto — **5 barras** azules (tono fijo, brillo por nivel) y 32 px de alto.
  - Menú Ver: «Mostrar espectrograma» (checkable, persistido en `ui/show_spectrum`; al ocultarse se detiene la captura) y «Ver letra».
  - Interfaz: tamaño inicial **630×485**, zona de título/artista fijada a **148 px**, barra de posición **justo debajo del tiempo**, y eliminados el botón de detener (■) y el texto de estado «▶ Reproduciendo / ⏸ En pausa / ■ Detenido» (el estado sigue en el icono del play unificado).
  - `src/app/utils/paths.py`: `LYRICS_DIR` (`<datos>/PyAmp/lyrics/`).
  - `src/app/core/settings.py`: clave `ui/show_spectrum` (espectrograma visible por defecto).
  - Tests: letras (parser, sidecar, sincronización) en `tests/test_library_panel.py`; regresiones de posición y play/pausa en `tests/test_player.py` — total 61 tests.
- **Ronda de ajustes post-Fase 5 — versión 0.1.5**:
  - Info de formato **real** en la cabecera: `Track._codec_name()` + `_CODEC_BY_CLASS` + `format_audio_info()` (`library/metadata.py`) derivan el códec de los **metadatos** de mutagen (clase `*Info`), nunca de la extensión; el campo `codec` entra en la fusión de metadatos (`_MERGED_FIELDS`) y la franja inferior muestra p. ej. «WAV, mono, 8 kHz, 128 kbit/s». Los MP3 corruptos quedan en «Archivo de audio» sin inventar datos.
  - Espectrograma rediseñado: **12 barras** iguales (`BAR_COUNT=12`) **simétricas** respecto a una línea central, 120 px de ancho fijo y **64 px de alto** (el doble que en Fase 5).
  - Ajustes → «Atajos de teclado»: cuadrícula de `QKeySequenceEdit` para reasignar 12 atajos (transporte, vistas, archivo, letra, ajustes, salir); solo se persisten los que difieren del valor por defecto (`shortcuts/custom` en QSettings, `SHORTCUT_DEFAULTS` en `core/settings.py`) y la ventana principal los reaplica al vuelo; vacío = valor por defecto. Las teclas de hardware del sistema (MPRIS) no se tocan.
  - Letra sin LRC: en vez de una lista vacía, la ventana de letra muestra «Letra no disponible :(» centrado en gris (`PLACEHOLDER_TEXT`), que desaparece al encontrar letra real o al cambiar de pista.
  - Tests: 71 en total (códec real, espectro, atajos, letras).
- **Ronda de ajustes 0.1.6 — temas, ajustes en pestañas, favoritos, aleatorio/repetir y letras editables** (versión **0.1.6**):
  - **Temas visuales (3)** — `src/app/themes/`: `manager.py` (dataclass `Theme` + QSS generado con `string.Template` y `header_stylesheet()` para la cabecera) y `data/*.json` (`winamp-oscuro` nativo = look histórico; `verde-terminal`; `arena-clara`); submenú «Ver → Temas» (`QActionGroup`) y `Ajustes → Apariencia`, persistido en `ui/theme`; el tono del espectro se adapta al tema.
  - **Ajustes en pestañas** — `settings_dialog.py` reescrito con `QTabWidget`: Notificaciones / Apariencia (tema, espectro, carátula) / Atajos / Información; nueva señal `apply_appearance(theme, spectrum, cover)`.
  - **Favoritos como vista** — «Ver → Favoritos» (Ctrl+3, `view_favoritos`): tercera vista con la tabla en modo `favorites_only` y consulta `favorite_tracks()` en `library/database.py`.
  - **Aleatorio (🔀) y Repetir (🔁)** — botones en el transporte con estado persistido (`playback/shuffle`, `playback/repeat`); `Player._advance_index()` elige un índice al azar distinto del actual (aleatorio) o vuelve a la primera pista al final (repetir).
  - **Letras editables** — «Editar → Editar letra...» (`ui/lyrics_editor.py`): edita el `.lrc` existente (junto al audio o en la biblioteca de letras) o crea uno nuevo con el nombre de la canción; **doble clic en una línea** de la letra salta a ese punto y sigue reproduciendo (`LyricsWindow.seek_requested`).
  - «Ver → Mostrar carátula» (`ui/show_cover`).
  - «Refrescar canciones» re-escanea **todas** las carpetas recordadas: cada escaneo se guarda en `library/folders` (`Settings.library_folders`) y el botón lanza la cola completa en vez de solo recargar la BD.
  - Espectro: `parec` **solo corre mientras suena** (`SpectrumWidget.stop_capture()` al pausar/parar/ocultar), así Plasma no muestra el indicador de grabación al abrir la app; nuevo `set_hue()` ligado al tema.
  - Tests: 87 en total (temas, pestañas del diálogo, favoritos, aleatorio/repetir, editor de letras, salto desde la letra, `stop_capture`).
- **Ronda de ajustes 0.1.7 — temas, árbol y textos** (versión **0.1.7**):
  - **Iconos de transporte por tema** (`icon` en el JSON del tema): los botones anterior/reproducir/siguiente (F9/F10/F11) y el de silencio se tiñen con el color del tema, así se ven sobre el fondo claro de «Arena clara» (antes heredaban el color del escritorio y quedaban invisibles).
  - **Espectro con los colores del tema**: fondo (`spectrum_bg`) y línea central (`spectrum_line`) ya siguen el tema; en «Verde terminal» el fondo del espectro deja de desentonar.
  - Diálogo de **Ajustes más cuadrado** (tamaño mínimo 620×560) en vez de la franja aplastada.
  - «Ver → Mostrar carátula» pasa a **«Ver → Mostrar imagen»** (y el ajuste equivalente en Apariencia).
  - Biblioteca (árbol): los álbumes sin año real ya no muestran «(0000)» (la BD guarda ese valor cuando la etiqueta no trae fecha).
  - Tests: 89 en total.
- **Ronda de ajustes 0.1.8 — artistas separados por coma e idioma ES/EN** (versión **0.1.8**):
  - **Biblioteca: un tema con varios artistas aparece bajo cada uno.** «Bad Bunny, Becky G» deja de ser un nodo propio: la pista se muestra bajo «Bad Bunny» y bajo «Becky G» (nodos individuales), y los álbumes de las colaboraciones se fusionan por título para no repetir el mismo nodo («Bad Bunny» aparece una vez). Nuevas consultas en `library/database.py`: `list_artists_grouped()`, `artist_ids_by_name()`, `albums_by_artist_name()` y `tracks_by_artist_name_and_album()`.
  - **Idioma español / English** (`src/app/i18n.py`): las dos versiones de los textos de la interfaz viven en el código (español de base, con la tabla inglesa resolviendo `tr()`); **Ajustes → General** elige el idioma y, al pulsar Aceptar, PyAmp **se reinicia** en el idioma elegido (`Settings.language` → clave `ui/language`); `main.py` fija el idioma guardado antes de construir la interfaz.
  - Corregido un `}` de más en `Theme.header_stylesheet()` que hacía que Qt descartara los estilos de la cabecera («Could not parse stylesheet»).
  - Tests: 99 en total (idioma, pestaña General, reinicio al cambiar de idioma, artistas agrupados por nombre).

### Removed
- (Fase 4) Splitter biblioteca|playlist y la lista lateral visible: ahora hay UNA vista a todo el ancho; la cola interna se controla con el transporte (▶/siguiente/anterior). La clave `window/splitter_state` se sustituye por `ui/view_mode`.
- (Fase 5) Botón de detener (■) de la barra de transporte y la etiqueta de texto «▶ Reproduciendo / ⏸ En pausa / ■ Detenido».

### Fixed
- `VlcBackend.seek()` usaba `set_position(ms/1000)` — `set_position()`
  espera una **fracción 0..1**, no segundos: al buscar, VLC saltaba al
  final del archivo y la canción **cambiaba de pista** en vez de
  reproducir desde el punto elegido. Ahora usa `set_time()` (ms
  directos) con fallback fracción×duración.
- El espectrograma de la cabecera colapsaba a **ancho 0** en la fila
  horizontal (el texto se llevaba todo el `stretch`); ahora tiene
  ancho fijo de 120 px (`SPECTRUM_WIDTH_PX`).
- La barra de posición y los controles de transporte ahora están
  **dentro del recuadro oscuro** de la cabecera (seek debajo del
  tiempo; transporte al pie del recuadro).
- `VlcBackend.position_ms()` usaba `get_position()` (fracción 0..1) × 1000: en archivos largos la barra de posición y el temporizador quedaban **congelados** (avanzaban ~192× más lento en un MP3 de 3 min). Ahora usa `get_time()` (ms directos) con fallback fracción×duración.
- Los E2E ya no tocan la configuración real: usan `XDG_CONFIG_HOME`/`XDG_DATA_HOME` aislados (los anteriores habían dejado la playlist de prueba «Rojo/Azul» y una geometría offscreen en el QSettings real; se limpiaron).
- Los tests ya no pueden contaminar la configuración real del usuario: aislar `XDG_CONFIG_HOME` **no bastaba** porque `QSettings` cachea la ruta por proceso, así que los `Settings()` «aislados» seguían leyendo y escribiendo `~/.config/PyAmp/PyAmp.conf`. Ahora `Settings` acepta una ruta explícita (`Settings(path)`), los tests usan un `.conf` temporal y un `conftest.py` redirige también el singleton `get_settings()`.
- Workaround en `VlcBackend`: libVLC (Fedora 44, VLC 3.0.23) hace SIGSEGV si se llama `audio_set_volume`/`audio_set_mute` antes de existir la salida de audio; el volumen/mute se difiere hasta que `is_playing()` es True.
- `_stringify` de metadatos: `ID3TimeStamp.text` es `str` (no se debe iterar como lista; provocaba año `"2"` en lugar de `"2024"`).
- Espectrograma con las barras **pegadas al máximo** (0.81–1.00 en casi
  todas las bandas, incluso sin señal fuerte): `_compute()` comparaba las
  magnitudes **crudas** de la FFT (cientos) contra una escala de −60..0 dB
  pensada para amplitudes 0..1, así que todo saturaba a `1.0`. Ahora se
  normalizan dividiendo por la ganancia de la ventana (`sum(hann)/2`, un
  seno a escala completa da 1.0) y cada barra sigue el nivel real de su
  banda (verificado: banda del tono ~0.97, bandas vacías 0.00, silencio
  0.00).

[Unreleased]: https://github.com/Danix13-glich/PyAmp/compare/v0.1.0...HEAD
