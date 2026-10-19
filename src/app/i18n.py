from __future__ import annotations

#: Idioma por defecto (y fuente de los textos del programa).
DEFAULT_LANGUAGE = "es"

#: Idiomas disponibles: código → nombre para mostrar (en su propio idioma).
LANGUAGES: dict[str, str] = {
    "es": "Español",
    "en": "English",
}

#: Idioma activo en este proceso (lo cambia :func:`set_language`).
_LANGUAGE = DEFAULT_LANGUAGE

#: Traducciones al inglés, con la cadena española como clave.
#: Los textos con ``{...}`` son plantillas: el llamante las formatea.
_EN: dict[str, str] = {
    # ------------------------------------------------------- ventana: menús
    "&Archivo": "&File",
    "Abrir &archivo(s)...": "Open &file(s)...",
    "Abrir &carpeta...": "Open &folder...",
    "Escanear carpeta en &biblioteca...": "Scan folder into &library...",
    "&Cargar playlist...": "&Load playlist...",
    "&Guardar playlist como...": "&Save playlist as...",
    "&Vaciar lista": "&Clear list",
    "&Salir": "&Quit",
    "&Ver": "&View",
    "Canciones (&tabla)": "Songs (&table)",
    "F&avoritos (★)": "F&avorites (★)",
    "&Radio online": "&Online radio",
    "Mostrar es&trograma": "Show s&pectrum",
    "Mostrar &imagen": "Show &image",
    "Ver &letra": "View &lyrics",
    "&Tema": "&Theme",
    "&Editar": "&Edit",
    "&Editar letra...": "&Edit lyrics...",
    "Editar o escribir la letra de la canción seleccionada": (
        "Edit or write the lyrics of the selected song"
    ),
    "&Ajustes...": "&Settings...",
    # -------------------------------------------------- ventana: transporte
    "Anterior": "Previous",
    "Siguiente": "Next",
    "Pista anterior": "Previous track",
    "Pista siguiente": "Next track",
    "Reproducir/pausar": "Play/pause",
    "Pausar": "Pause",
    "Reanudar": "Resume",
    "Reproducir": "Play",
    "Aleatorio": "Shuffle",
    "Aleatorio: siguiente pista al azar": "Shuffle: play the next track at random",
    "Repetir": "Repeat",
    "Repetir: al terminar la playlist se vuelve a la primera": (
        "Repeat: when the playlist ends, start over from the first track"
    ),
    "Marcar la pista actual como favorita": "Mark the current track as a favorite",
    "Favorito": "Favorite",
    "Silenciar": "Mute",
    "Silenciar (mute)": "Mute",
    "Volumen": "Volume",
    "Posición": "Position",
    "Posición de reproducción": "Playback position",
    "Pista anterior (multimedia)": "Previous track (media)",
    "Reproducir/pausar (multimedia)": "Play/pause (media)",
    "Reproducir (multimedia)": "Play (media)",
    "Pausar (multimedia)": "Pause (media)",
    "Pista siguiente (multimedia)": "Next track (media)",
    # ---------------------------------------------------- ventana: estados
    "Audio no disponible": "Audio unavailable",
    "Escaneando {folder} ...": "Scanning {folder} ...",
    "No se encontraron archivos de audio": "No audio files found",
    "{count} pistas añadidas": "{count} tracks added",
    "Ya hay un escaneo en curso": "A scan is already running",
    "Sin carpetas guardadas — «Archivo → Escanear carpeta en biblioteca...»": (
        "No saved folders — “File → Scan folder into library...”"
    ),
    "Escaneando… {processed} archivos ({current})": "Scanning… {processed} files ({current})",
    "Biblioteca: {added} añadidas, {updated} actualizadas, {skipped} sin cambios, "
    "{removed} eliminadas": (
        "Library: {added} added, {updated} updated, {skipped} unchanged, {removed} removed"
    ),
    ", {errors} errores": ", {errors} errors",
    " (escaneo cancelado)": " (scan cancelled)",
    "▶ {name} ({count} pistas en cola)": "▶ {name} ({count} tracks queued)",
    "{count} pistas en cola — ▶ para reproducir": "{count} tracks queued — ▶ to play",
    "Playlist cargada ({count} pistas en cola)": "Playlist loaded ({count} tracks queued)",
    "La playlist está vacía": "The playlist is empty",
    "Playlist guardada en {path}": "Playlist saved to {path}",
    "Playlist vaciada": "Playlist cleared",
    "Atajos de teclado actualizados": "Keyboard shortcuts updated",
    "Ajustes aplicados: notificaciones {state}, {seconds} s": (
        "Settings applied: notifications {state}, {seconds} s"
    ),
    "activadas": "enabled",
    "desactivadas": "disabled",
    "Notificación de prueba": "Test notification",
    "PyAmp funciona correctamente ✓": "PyAmp is working correctly ✓",
    "La notificación falló: {error}": "The notification failed: {error}",
    "Notificación de prueba enviada": "Test notification sent",
    "Favorito no guardado: {error}": "Favorite not saved: {error}",
    "★ Añadida a favoritos": "★ Added to favorites",
    "★ Quitada de favoritos": "★ Removed from favorites",
    "Espectrograma visible": "Spectrum shown",
    "Espectrograma oculto": "Spectrum hidden",
    "Imagen visible": "Image shown",
    "Imagen oculta": "Image hidden",
    "Aleatorio activado": "Shuffle on",
    "Aleatorio desactivado": "Shuffle off",
    "Repetición activada": "Repeat on",
    "Repetición desactivada": "Repeat off",
    "Selecciona una canción para editar su letra (o reproduce una)": (
        "Select a song to edit its lyrics (or play one)"
    ),
    "Letra guardada en {path}": "Lyrics saved to {path}",
    "▶ Saltado a {time} (letra)": "▶ Jumped to {time} (lyrics)",
    # ------------------------------------------------- diálogos de fichero
    "Abrir archivos de audio": "Open audio files",
    "Archivos de audio ({filters});;Todos los archivos (*)": (
        "Audio files ({filters});;All files (*)"
    ),
    "Abrir carpeta": "Open folder",
    "Escanear carpeta para la biblioteca": "Scan folder for the library",
    "Cargar playlist": "Load playlist",
    "Playlists (*.m3u *.m3u8);;Todos los archivos (*)": ("Playlists (*.m3u *.m3u8);;All files (*)"),
    "Guardar playlist como": "Save playlist as",
    "Playlist M3U (*.m3u);;Todos los archivos (*)": "M3U playlist (*.m3u);;All files (*)",
    "No se pudo cargar la playlist: {error}": "Could not load the playlist: {error}",
    "No se pudo guardar la playlist: {error}": "Could not save the playlist: {error}",
    # ------------------------------------------------------ vista Canciones
    "Nombre": "Name",
    "Duración": "Duration",
    "Artista": "Artist",
    "Buscar nombre, artista o álbum...": "Search name, artist or album...",
    "Refrescar canciones": "Refresh songs",
    "Catálogo cargado": "Catalog loaded",
    "Sin resultados para «{term}»": "No results for “{term}”",
    "Aún no hay favoritas — marca ★ en la vista Canciones": (
        "No favorites yet — mark ★ in the Songs view"
    ),
    "Biblioteca vacía — «Archivo → Escanear carpeta en biblioteca...»": (
        "Library empty — “File → Scan folder into library...”"
    ),
    "{visible} de {total} canciones · {favorites} favoritas": (
        "{visible} of {total} songs · {favorites} favorites"
    ),
    # ------------------------------------------------------ panel Biblioteca
    "Buscar título, artista o álbum...": "Search title, artist or album...",
    "Refrescar biblioteca": "Refresh library",
    "Biblioteca": "Library",
    "Totales de la biblioteca": "Library totals",
    "(Sin artista)": "(No artist)",
    "(Sin álbum)": "(No album)",
    "(mostrando solo los primeros {limit} resultados)": (
        "(showing only the first {limit} results)"
    ),
    "{count} pistas": "{count} tracks",
    "{tracks} pistas · {artists} artistas · {albums} álbumes": (
        "{tracks} tracks · {artists} artists · {albums} albums"
    ),
    # -------------------------------------------------------------- Ajustes
    "Ajustes de PyAmp": "PyAmp Settings",
    "General": "General",
    "Idioma:": "Language:",
    "Idioma de la aplicación. Al aceptar, PyAmp se reinicia en el idioma elegido.": (
        "Application language. On accept, PyAmp restarts in the chosen language."
    ),
    "Notificaciones": "Notifications",
    "Apariencia": "Appearance",
    "Atajos": "Shortcuts",
    "Información": "About",
    "Activar notificaciones de escritorio": "Enable desktop notifications",
    "Duración en pantalla de cada notificación": "On-screen duration of each notification",
    "Duración:": "Duration:",
    "Probar notificación": "Test notification",
    "Envía una notificación de prueba ahora": "Send a test notification now",
    "Tema:": "Theme:",
    "Tema visual de toda la aplicación": "Visual theme for the whole application",
    "Mostrar espectrograma en la cabecera": "Show spectrum in the header",
    "Mostrar imagen en la cabecera": "Show image in the header",
    "Pulsa la combinación nueva en cada recuadro. Vacío = valor por defecto.": (
        "Press the new combination in each box. Empty = default value."
    ),
    "Ver: Canciones": "View: Songs",
    "Ver: Favoritos": "View: Favorites",
    "Ver: Radio": "View: Radio",
    "Abrir archivo(s)": "Open file(s)",
    "Guardar playlist": "Save playlist",
    "Ajustes": "Settings",
    "Salir": "Quit",
    "Versión:": "Version:",
    "Notificador:": "Notifier:",
    "Biblioteca:": "Library:",
    "Idioma": "Language",
    # ---------------------------------------------------------------- radio
    "Radio online": "Online radio",
    "Radio": "Radio",
    "Emisora": "Station",
    "Género": "Genre",
    "País": "Country",
    "Detener": "Stop",
    "Añadir": "Add",
    "Editar": "Edit",
    "Eliminar": "Remove",
    "Buscar emisora, género o país...": "Search station, genre or country...",
    "{shown} de {total} emisoras": "{shown} of {total} stations",
    "Selecciona una emisora": "Select a station",
    "Esa emisora ya está en la lista.": "That station is already in the list.",
    "Solo se pueden editar tus emisoras": "Only your stations can be edited",
    "Solo se pueden borrar tus emisoras": "Only your stations can be deleted",
    "¿Eliminar «{name}»?": "Delete “{name}”?",
    "Reproduciendo {name}": "Playing {name}",
    "▶ {name} (radio)": "▶ {name} (radio)",
    "Radio detenida": "Radio stopped",
    "Emisora de radio": "Radio station",
    "Nombre:": "Name:",
    "Dirección (URL):": "Address (URL):",
    "Género:": "Genre:",
    "Clásica": "Classical",
    "Actualidad": "News",
    "Cultura": "Culture",
    "EE. UU.": "USA",
    "Suiza": "Switzerland",
    "Francia": "France",
    "España": "Spain",
    # ----------------------------------------------------------------- letra
    "Letra — PyAmp": "Lyrics — PyAmp",
    "Letra no disponible :(": "Lyrics not available :(",
    "No hay ninguna pista en reproducción": "No track is playing",
    "No encontré «{stem}.lrc» (junto al audio o en {directory})": (
        "I couldn't find “{stem}.lrc” (next to the audio or in {directory})"
    ),
    "No se pudo leer {name}: {error}": "Could not read {name}: {error}",
    "{name}: sin marcas de tiempo [mm:ss]": "{name}: no timestamps [mm:ss]",
    "Letra: {name}": "Lyrics: {name}",
    # -------------------------------------------------------- editor de letras
    "Editar letra — {title}": "Edit lyrics — {title}",
    "Existente": "Existing",
    "Nuevo": "New",
    "Formato: una línea por frase. Para sincronizar añade marcas de tiempo "
    "«[mm:ss]» al principio de cada línea.": (
        "Format: one line per phrase. To sync, add timestamps “[mm:ss]” "
        "at the start of each line."
    ),
    "Escribe aquí la letra de la canción...": "Write the song lyrics here...",
    "Guardar": "Save",
    "No se pudo guardar": "Could not save",
    "No se pudo escribir {path}:\n{error}": "Could not write {path}:\n{error}",
    # --------------------------------------------------- carátula / metadatos
    "Carátula": "Cover",
    "Artista desconocido": "Unknown artist",
    "Sin título": "Untitled",
}


def set_language(code: str) -> str:
    global _LANGUAGE
    key = str(code).strip().lower()
    _LANGUAGE = key if key in LANGUAGES else DEFAULT_LANGUAGE
    return _LANGUAGE


def current_language() -> str:
    return _LANGUAGE


def language_name(code: str) -> str:
    return LANGUAGES.get(str(code).strip().lower(), LANGUAGES[DEFAULT_LANGUAGE])


def tr(text: str) -> str:
    if _LANGUAGE == DEFAULT_LANGUAGE:
        return text
    return _EN.get(text, text)
