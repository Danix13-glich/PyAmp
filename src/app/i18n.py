from __future__ import annotations

#: Idioma por defecto (y fuente de los textos del programa).
DEFAULT_LANGUAGE = "es"

#: Idiomas disponibles: código → nombre para mostrar (en su propio idioma).
LANGUAGES: dict[str, str] = {
    "es": "Español",
    "en": "English",
    "it": "Italiano",
    "ar": "العربية",
}

#: Idiomas que se escriben de derecha a izquierda.
RTL_LANGUAGES = frozenset({"ar"})

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
    "Repetir: repite la pista actual una vez y se desactiva": (
        "Repeat: play the current track once more, then turn off"
    ),
    "Repetición desactivada (repetida una vez)": "Repeat off (played once more)",
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
    "PyAmp funciona correctamente": "PyAmp is working correctly",
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
    "No hay emisoras: busca o añade una": "No stations: search or add one",
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
    "Buscar emisoras": "Search stations",
    "Busca emisoras online de tu zona": "Search online stations near you",
    "Aún no tienes emisoras. Busca las de tu zona.": (
        "You have no stations yet. Search for ones near you."
    ),
    "Buscando emisoras…": "Searching stations…",
    "Usando tu ubicación para buscarlas…": "Using your location to find them…",
    "Se encontraron {n} emisoras": "Found {n} stations",
    "No se pudieron buscar emisoras: {error}": "Could not search stations: {error}",
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
    # --------------------------------------------------- 0.2.0: ventana/temas
    "Tamaño de la ventana:": "Window size:",
    "Ancho": "Width",
    "Alto": "Height",
    "Tamaño por defecto de la ventana principal": "Default main window size",
    "Tamaño de ventana: {width}×{height}": "Window size: {width}×{height}",
    "Crear tema nuevo…": "Create new theme…",
    "Crear tema nuevo": "Create new theme",
    "Nombre del tema:": "Theme name:",
    "Mi tema": "My theme",
    "Nombre para el nuevo tema": "Name for the new theme",
    "Fondo:": "Background:",
    "Texto:": "Text:",
    "Acento:": "Accent:",
    "Elegir color": "Choose color",
    "Mostrar archivos ocultos": "Show hidden files",
    "Los archivos ocultos aparecen al principio, con un «-» delante.": (
        "Hidden files appear first, prefixed with a “-”."
    ),
    "Mostrando archivos ocultos": "Showing hidden files",
    "Ocultando archivos ocultos": "Hiding hidden files",
    # ------------------------------------------------- 0.2.0: menú canciones
    "Mover a favoritos": "Move to favorites",
    "Quitar de favoritos": "Remove from favorites",
    "Ocultar": "Hide",
    "Mostrar": "Show",
    "Renombrar": "Rename",
    "Editar metadata": "Edit metadata",
    "Pista oculta": "Track hidden",
    "Pista visible": "Track visible",
    "Nuevo nombre:": "New name:",
    "Ya existe un archivo con ese nombre": "A file with that name already exists",
    "No se pudo renombrar: {error}": "Could not rename: {error}",
    "Renombrado a {name}": "Renamed to {name}",
    "No se encontró el archivo: {path}": "File not found: {path}",
    "¿Quitar «{name}» de la biblioteca?\n(El archivo no se borra del disco.)": (
        "Remove “{name}” from the library?\n(The file is not deleted from disk.)"
    ),
    "Pista eliminada de la biblioteca": "Track removed from the library",
    "No se pudo eliminar: {error}": "Could not remove: {error}",
    "No se pudo guardar la metadata: {error}": "Could not save metadata: {error}",
    "Metadata actualizada": "Metadata updated",
    # -------------------------------------------------- 0.2.0: editor metadata
    "Título:": "Title:",
    "Artista:": "Artist:",
    "Álbum:": "Album:",
    "Artista del álbum:": "Album artist:",
    "Año:": "Year:",
    "N.º de pista:": "Track no.:",
    "N.º de disco:": "Disc no.:",
    # ------------------------------------------------------- 0.2.0: radio
    "Editar Valores": "Edit values",
    # ------------------------------------------------ 0.2.1: historial mensual
    "&Historial": "&History",
    "Ver historial del mes": "View this month's history",
    "Historial — PyAmp": "History — PyAmp",
    "Las 10 canciones más escuchadas": "The 10 most played songs",
    "Aún no está listo :/": "Not ready yet :/",
    "Cerrar": "Close",
    "{rank}. {title} — {artist}  ({count}×)": "{rank}. {title} — {artist}  ({count}×)",
    "Tu historial del mes ya está listo": "Your monthly history is ready",
    "Pulsa para ver las 10 canciones más escuchadas del mes pasado.": (
        "Click to see the 10 most played songs from last month."
    ),
    "Ver historial": "View history",
    # ------------------------------------------------ 0.2.1: ajustes/avanzado
    "Avanzado": "Advanced",
    "Proximamente... :)": "Coming soon... :)",
    "Eliminar tema": "Delete theme",
    "Nombre del tema actual": "Current theme name",
    "¿Eliminar el tema «{name}»?": "Delete the theme “{name}”?",
    "Solo se pueden renombrar los temas personalizados": "Only custom themes can be renamed",
    "Solo se pueden eliminar los temas personalizados": "Only custom themes can be deleted",
    "Tema eliminado": "Theme deleted",
    "Tema renombrado": "Theme renamed",
    # ------------------------------------------------ 0.2.1: información/instalar
    "Autor:": "Author:",
    "Sistema:": "System:",
    "Python:": "Python:",
    "Qt:": "Qt:",
    "Formato:": "Format:",
    "Código fuente (Python)": "Source code (Python)",
    "Ejecutable de Windows (.exe)": "Windows executable (.exe)",
    "Aplicación de macOS (.app)": "macOS application (.app)",
    "AppImage de Linux": "Linux AppImage",
    "Instalar": "Install",
    "Instala PyAmp en este equipo": "Install PyAmp on this computer",
    "Instalando PyAmp": "Installing PyAmp",
    "Instalación de PyAmp": "PyAmp installation",
    "Instalando PyAmp…": "Installing PyAmp…",
    "Preparando la instalación…": "Preparing installation…",
    "Copiando archivos…": "Copying files…",
    "Copiando la aplicación…": "Copying the application…",
    "Creando el acceso directo…": "Creating the shortcut…",
    "Actualizando el menú de aplicaciones…": "Updating the applications menu…",
    "Instalación completada.": "Installation complete.",
    "PyAmp se ha instalado correctamente.": "PyAmp was installed successfully.",
    "Instalación completada": "Installation complete",
    "¿Quieres eliminar el archivo instalador?\n{path}": (
        "Do you want to delete the installer file?\n{path}"
    ),
    "Archivo instalador eliminado.": "Installer file deleted.",
    "No se pudo eliminar el archivo instalador.": "Could not delete the installer file.",
    "No se pudo instalar: {error}": "Could not install: {error}",
    "No se encontró la carpeta de aplicaciones.": "The applications folder was not found.",
    "La instalación automática solo está disponible en la app empaquetada.": (
        "Automatic installation is only available in the packaged app."
    ),
    "Sistema operativo no compatible.": "Unsupported operating system.",
}

#: Traducciones al italiano (misma clave: la cadena española).
_IT: dict[str, str] = {
    # ------------------------------------------------------- ventana: menús
    "&Archivo": "&File",
    "Abrir &archivo(s)...": "Apri &file...",
    "Abrir &carpeta...": "Apri &cartella...",
    "Escanear carpeta en &biblioteca...": "Scansiona cartella nella &libreria...",
    "&Cargar playlist...": "&Carica playlist...",
    "&Guardar playlist como...": "&Salva playlist come...",
    "&Vaciar lista": "&Svuota elenco",
    "&Salir": "&Esci",
    "&Ver": "&Visualizza",
    "Canciones (&tabla)": "Brani (&tabella)",
    "F&avoritos (★)": "P&referiti (★)",
    "&Radio online": "&Radio online",
    "Mostrar es&trograma": "Mostra &spettro",
    "Mostrar &imagen": "Mostra &immagine",
    "Ver &letra": "Vedi &testo",
    "&Tema": "&Tema",
    "&Editar": "&Modifica",
    "&Editar letra...": "&Modifica testo...",
    "Editar o escribir la letra de la canción seleccionada": (
        "Modifica o scrivi il testo del brano selezionato"
    ),
    "&Ajustes...": "&Impostazioni...",
    # -------------------------------------------------- ventana: transporte
    "Anterior": "Precedente",
    "Siguiente": "Successivo",
    "Pista anterior": "Brano precedente",
    "Pista siguiente": "Brano successivo",
    "Reproducir/pausar": "Riproduci/pausa",
    "Pausar": "Pausa",
    "Reanudar": "Riprendi",
    "Reproducir": "Riproduci",
    "Aleatorio": "Casuale",
    "Aleatorio: siguiente pista al azar": "Casuale: riproduci il brano successivo a caso",
    "Repetir": "Ripeti",
    "Repetir: repite la pista actual una vez y se desactiva": (
        "Ripeti: riproduce il brano attuale una volta, poi si disattiva"
    ),
    "Repetición desactivada (repetida una vez)": ("Ripetizione disattivata (riprodotto una volta)"),
    "Marcar la pista actual como favorita": "Segna il brano attuale come preferito",
    "Favorito": "Preferito",
    "Silenciar": "Muto",
    "Silenciar (mute)": "Muto",
    "Volumen": "Volume",
    "Posición": "Posizione",
    "Posición de reproducción": "Posizione di riproduzione",
    "Pista anterior (multimedia)": "Brano precedente (multimedia)",
    "Reproducir/pausar (multimedia)": "Riproduci/pausa (multimedia)",
    "Reproducir (multimedia)": "Riproduci (multimedia)",
    "Pausar (multimedia)": "Pausa (multimedia)",
    "Pista siguiente (multimedia)": "Brano successivo (multimedia)",
    # ---------------------------------------------------- ventana: estados
    "Audio no disponible": "Audio non disponibile",
    "Escaneando {folder} ...": "Scansione di {folder} ...",
    "No se encontraron archivos de audio": "Nessun file audio trovato",
    "{count} pistas añadidas": "{count} brani aggiunti",
    "Ya hay un escaneo en curso": "Una scansione è già in corso",
    "Sin carpetas guardadas — «Archivo → Escanear carpeta en biblioteca...»": (
        "Nessuna cartella salvata — «File → Scansiona cartella nella libreria...»"
    ),
    "Escaneando… {processed} archivos ({current})": "Scansione… {processed} file ({current})",
    "Biblioteca: {added} añadidas, {updated} actualizadas, {skipped} sin cambios, "
    "{removed} eliminadas": (
        "Libreria: {added} aggiunti, {updated} aggiornati, {skipped} invariati, "
        "{removed} rimossi"
    ),
    ", {errors} errores": ", {errors} errori",
    " (escaneo cancelado)": " (scansione annullata)",
    "▶ {name} ({count} pistas en cola)": "▶ {name} ({count} brani in coda)",
    "{count} pistas en cola — ▶ para reproducir": "{count} brani in coda — ▶ per riprodurre",
    "Playlist cargada ({count} pistas en cola)": "Playlist caricata ({count} brani in coda)",
    "La playlist está vacía": "La playlist è vuota",
    "Playlist guardada en {path}": "Playlist salvata in {path}",
    "Playlist vaciada": "Playlist svuotata",
    "Atajos de teclado actualizados": "Scorciatoie da tastiera aggiornate",
    "Ajustes aplicados: notificaciones {state}, {seconds} s": (
        "Impostazioni applicate: notifiche {state}, {seconds} s"
    ),
    "activadas": "attive",
    "desactivadas": "disattivate",
    "Notificación de prueba": "Notifica di prova",
    "PyAmp funciona correctamente": "PyAmp funziona correttamente",
    "La notificación falló: {error}": "La notifica non è riuscita: {error}",
    "Notificación de prueba enviada": "Notifica di prova inviata",
    "Favorito no guardado: {error}": "Preferito non salvato: {error}",
    "★ Añadida a favoritos": "★ Aggiunto ai preferiti",
    "★ Quitada de favoritos": "★ Rimosso dai preferiti",
    "Espectrograma visible": "Spettro visibile",
    "Espectrograma oculto": "Spettro nascosto",
    "Imagen visible": "Immagine visibile",
    "Imagen oculta": "Immagine nascosta",
    "Aleatorio activado": "Casuale attivato",
    "Aleatorio desactivado": "Casuale disattivato",
    "Repetición activada": "Ripetizione attivata",
    "Repetición desactivada": "Ripetizione disattivata",
    "Selecciona una canción para editar su letra (o reproduce una)": (
        "Seleziona un brano per modificarne il testo (o riproduci un brano)"
    ),
    "Letra guardada en {path}": "Testo salvato in {path}",
    "▶ Saltado a {time} (letra)": "▶ Saltato a {time} (testo)",
    # ------------------------------------------------- diálogos de fichero
    "Abrir archivos de audio": "Apri file audio",
    "Archivos de audio ({filters});;Todos los archivos (*)": (
        "File audio ({filters});;Tutti i file (*)"
    ),
    "Abrir carpeta": "Apri cartella",
    "Escanear carpeta para la biblioteca": "Scansiona cartella per la libreria",
    "Cargar playlist": "Carica playlist",
    "Playlists (*.m3u *.m3u8);;Todos los archivos (*)": (
        "Playlist (*.m3u *.m3u8);;Tutti i file (*)"
    ),
    "Guardar playlist como": "Salva playlist come",
    "Playlist M3U (*.m3u);;Todos los archivos (*)": "Playlist M3U (*.m3u);;Tutti i file (*)",
    "No se pudo cargar la playlist: {error}": "Impossibile caricare la playlist: {error}",
    "No se pudo guardar la playlist: {error}": "Impossibile salvare la playlist: {error}",
    # ------------------------------------------------------ vista Canciones
    "Nombre": "Nome",
    "Duración": "Durata",
    "Artista": "Artista",
    "Buscar nombre, artista o álbum...": "Cerca nome, artista o album...",
    "Refrescar canciones": "Aggiorna brani",
    "Catálogo cargado": "Catalogo caricato",
    "Sin resultados para «{term}»": "Nessun risultato per «{term}»",
    "Aún no hay favoritas — marca ★ en la vista Canciones": (
        "Nessun preferito — segna ★ nella vista Brani"
    ),
    "Biblioteca vacía — «Archivo → Escanear carpeta en biblioteca...»": (
        "Libreria vuota — «File → Scansiona cartella nella libreria...»"
    ),
    "{visible} de {total} canciones · {favorites} favoritas": (
        "{visible} di {total} brani · {favorites} preferiti"
    ),
    # ------------------------------------------------------ panel Biblioteca
    "Buscar título, artista o álbum...": "Cerca titolo, artista o album...",
    "Refrescar biblioteca": "Aggiorna libreria",
    "Biblioteca": "Libreria",
    "Totales de la biblioteca": "Totali della libreria",
    "(Sin artista)": "(Nessun artista)",
    "(Sin álbum)": "(Nessun album)",
    "(mostrando solo los primeros {limit} resultados)": (
        "(mostrati solo i primi {limit} risultati)"
    ),
    "{count} pistas": "{count} brani",
    "{tracks} pistas · {artists} artistas · {albums} álbumes": (
        "{tracks} brani · {artists} artisti · {albums} album"
    ),
    # -------------------------------------------------------------- Ajustes
    "Ajustes de PyAmp": "Impostazioni di PyAmp",
    "General": "Generale",
    "Idioma:": "Lingua:",
    "Idioma de la aplicación. Al aceptar, PyAmp se reinicia en el idioma elegido.": (
        "Lingua dell'applicazione. Alla conferma, PyAmp si riavvia nella lingua scelta."
    ),
    "Notificaciones": "Notifiche",
    "Apariencia": "Aspetto",
    "Atajos": "Scorciatoie",
    "Información": "Informazioni",
    "Activar notificaciones de escritorio": "Attiva le notifiche desktop",
    "Duración en pantalla de cada notificación": "Durata sullo schermo di ogni notifica",
    "Duración:": "Durata:",
    "Probar notificación": "Prova notifica",
    "Envía una notificación de prueba ahora": "Invia ora una notifica di prova",
    "Tema:": "Tema:",
    "Tema visual de toda la aplicación": "Tema visivo per tutta l'applicazione",
    "Mostrar espectrograma en la cabecera": "Mostra lo spettro nell'intestazione",
    "Mostrar imagen en la cabecera": "Mostra l'immagine nell'intestazione",
    "Pulsa la combinación nueva en cada recuadro. Vacío = valor por defecto.": (
        "Premi la nuova combinazione in ogni casella. Vuoto = valore predefinito."
    ),
    "Ver: Canciones": "Vedi: Brani",
    "Ver: Favoritos": "Vedi: Preferiti",
    "Ver: Radio": "Vedi: Radio",
    "Abrir archivo(s)": "Apri file",
    "Guardar playlist": "Salva playlist",
    "Ajustes": "Impostazioni",
    "Salir": "Esci",
    "Versión:": "Versione:",
    "Notificador:": "Notificatore:",
    "Biblioteca:": "Libreria:",
    "Idioma": "Lingua",
    # ---------------------------------------------------------------- radio
    "Radio online": "Radio online",
    "Radio": "Radio",
    "Emisora": "Stazione",
    "Género": "Genere",
    "País": "Paese",
    "Detener": "Ferma",
    "Añadir": "Aggiungi",
    "Editar": "Modifica",
    "Eliminar": "Rimuovi",
    "Buscar emisora, género o país...": "Cerca stazione, genere o paese...",
    "{shown} de {total} emisoras": "{shown} di {total} stazioni",
    "Selecciona una emisora": "Seleziona una stazione",
    "No hay emisoras: busca o añade una": "Nessuna stazione: cercane o aggiungine una",
    "Esa emisora ya está en la lista.": "Questa stazione è già nell'elenco.",
    "Solo se pueden editar tus emisoras": "Puoi modificare solo le tue stazioni",
    "Solo se pueden borrar tus emisoras": "Puoi eliminare solo le tue stazioni",
    "¿Eliminar «{name}»?": "Eliminare «{name}»?",
    "Reproduciendo {name}": "Riproduzione di {name}",
    "▶ {name} (radio)": "▶ {name} (radio)",
    "Radio detenida": "Radio fermata",
    "Emisora de radio": "Stazione radio",
    "Nombre:": "Nome:",
    "Dirección (URL):": "Indirizzo (URL):",
    "Género:": "Genere:",
    "Clásica": "Classica",
    "Actualidad": "Attualità",
    "Cultura": "Cultura",
    "EE. UU.": "USA",
    "Suiza": "Svizzera",
    "Francia": "Francia",
    "España": "Spagna",
    "Buscar emisoras": "Cerca stazioni",
    "Busca emisoras online de tu zona": "Cerca stazioni online vicino a te",
    "Aún no tienes emisoras. Busca las de tu zona.": (
        "Non hai ancora stazioni. Cerca quelle della tua zona."
    ),
    "Buscando emisoras…": "Ricerca stazioni…",
    "Usando tu ubicación para buscarlas…": "Uso della tua posizione per trovarle…",
    "Se encontraron {n} emisoras": "Trovate {n} stazioni",
    "No se pudieron buscar emisoras: {error}": "Impossibile cercare le stazioni: {error}",
    # ----------------------------------------------------------------- letra
    "Letra — PyAmp": "Testo — PyAmp",
    "Letra no disponible :(": "Testo non disponibile :(",
    "No hay ninguna pista en reproducción": "Nessun brano in riproduzione",
    "No encontré «{stem}.lrc» (junto al audio o en {directory})": (
        "Non ho trovato «{stem}.lrc» (accanto all'audio o in {directory})"
    ),
    "No se pudo leer {name}: {error}": "Impossibile leggere {name}: {error}",
    "{name}: sin marcas de tiempo [mm:ss]": "{name}: senza marche temporali [mm:ss]",
    "Letra: {name}": "Testo: {name}",
    # -------------------------------------------------------- editor de letras
    "Editar letra — {title}": "Modifica testo — {title}",
    "Existente": "Esistente",
    "Nuevo": "Nuovo",
    "Formato: una línea por frase. Para sincronizar añade marcas de tiempo "
    "«[mm:ss]» al principio de cada línea.": (
        "Formato: una riga per frase. Per sincronizzare aggiungi le marche temporali "
        "«[mm:ss]» all'inizio di ogni riga."
    ),
    "Escribe aquí la letra de la canción...": "Scrivi qui il testo del brano...",
    "Guardar": "Salva",
    "No se pudo guardar": "Impossibile salvare",
    "No se pudo escribir {path}:\n{error}": "Impossibile scrivere {path}:\n{error}",
    # --------------------------------------------------- carátula / metadatos
    "Carátula": "Copertina",
    "Artista desconocido": "Artista sconosciuto",
    "Sin título": "Senza titolo",
    # --------------------------------------------------- 0.2.0: ventana/temas
    "Tamaño de la ventana:": "Dimensione della finestra:",
    "Ancho": "Larghezza",
    "Alto": "Altezza",
    "Tamaño por defecto de la ventana principal": (
        "Dimensione predefinita della finestra principale"
    ),
    "Tamaño de ventana: {width}×{height}": "Dimensione finestra: {width}×{height}",
    "Crear tema nuevo…": "Crea nuovo tema…",
    "Crear tema nuevo": "Crea nuovo tema",
    "Nombre del tema:": "Nome del tema:",
    "Mi tema": "Il mio tema",
    "Nombre para el nuevo tema": "Nome per il nuovo tema",
    "Fondo:": "Sfondo:",
    "Texto:": "Testo:",
    "Acento:": "Accento:",
    "Elegir color": "Scegli colore",
    "Mostrar archivos ocultos": "Mostra file nascosti",
    "Los archivos ocultos aparecen al principio, con un «-» delante.": (
        "I file nascosti appaiono all'inizio, preceduti da «-»."
    ),
    "Mostrando archivos ocultos": "Visualizzazione dei file nascosti",
    "Ocultando archivos ocultos": "Nascondendo i file nascosti",
    # ------------------------------------------------- 0.2.0: menú canciones
    "Mover a favoritos": "Sposta nei preferiti",
    "Quitar de favoritos": "Rimuovi dai preferiti",
    "Ocultar": "Nascondi",
    "Mostrar": "Mostra",
    "Renombrar": "Rinomina",
    "Editar metadata": "Modifica metadati",
    "Pista oculta": "Brano nascosto",
    "Pista visible": "Brano visibile",
    "Nuevo nombre:": "Nuovo nome:",
    "Ya existe un archivo con ese nombre": "Esiste già un file con quel nome",
    "No se pudo renombrar: {error}": "Impossibile rinominare: {error}",
    "Renombrado a {name}": "Rinominato in {name}",
    "No se encontró el archivo: {path}": "File non trovato: {path}",
    "¿Quitar «{name}» de la biblioteca?\n(El archivo no se borra del disco.)": (
        "Rimuovere «{name}» dalla libreria?\n(Il file non viene eliminato dal disco.)"
    ),
    "Pista eliminada de la biblioteca": "Brano rimosso dalla libreria",
    "No se pudo eliminar: {error}": "Impossibile eliminare: {error}",
    "No se pudo guardar la metadata: {error}": "Impossibile salvare i metadati: {error}",
    "Metadata actualizada": "Metadati aggiornati",
    # -------------------------------------------------- 0.2.0: editor metadata
    "Título:": "Titolo:",
    "Artista:": "Artista:",
    "Álbum:": "Album:",
    "Artista del álbum:": "Artista dell'album:",
    "Año:": "Anno:",
    "N.º de pista:": "N. brano:",
    "N.º de disco:": "N. disco:",
    # ------------------------------------------------------- 0.2.0: radio
    "Editar Valores": "Modifica valori",
    # ------------------------------------------------ 0.2.1: historial mensual
    "&Historial": "&Cronologia",
    "Ver historial del mes": "Vedi la cronologia del mese",
    "Historial — PyAmp": "Cronologia — PyAmp",
    "Las 10 canciones más escuchadas": "I 10 brani più ascoltati",
    "Aún no está listo :/": "Non è ancora pronto :/",
    "Cerrar": "Chiudi",
    "{rank}. {title} — {artist}  ({count}×)": "{rank}. {title} — {artist}  ({count}×)",
    "Tu historial del mes ya está listo": "La cronologia del mese è pronta",
    "Pulsa para ver las 10 canciones más escuchadas del mes pasado.": (
        "Premi per vedere i 10 brani più ascoltati del mese scorso."
    ),
    "Ver historial": "Vedi cronologia",
    # ------------------------------------------------ 0.2.1: ajustes/avanzado
    "Avanzado": "Avanzate",
    "Proximamente... :)": "Prossimamente... :)",
    "Eliminar tema": "Elimina tema",
    "Nombre del tema actual": "Nome del tema attuale",
    "¿Eliminar el tema «{name}»?": "Eliminare il tema «{name}»?",
    "Solo se pueden renombrar los temas personalizados": (
        "Solo i temi personalizzati possono essere rinominati"
    ),
    "Solo se pueden eliminar los temas personalizados": (
        "Solo i temi personalizzati possono essere eliminati"
    ),
    "Tema eliminado": "Tema eliminato",
    "Tema renombrado": "Tema rinominato",
    # ------------------------------------------------ 0.2.1: información/instalar
    "Autor:": "Autore:",
    "Sistema:": "Sistema:",
    "Python:": "Python:",
    "Qt:": "Qt:",
    "Formato:": "Formato:",
    "Código fuente (Python)": "Codice sorgente (Python)",
    "Ejecutable de Windows (.exe)": "Eseguibile di Windows (.exe)",
    "Aplicación de macOS (.app)": "Applicazione macOS (.app)",
    "AppImage de Linux": "AppImage per Linux",
    "Instalar": "Installa",
    "Instala PyAmp en este equipo": "Installa PyAmp su questo computer",
    "Instalando PyAmp": "Installazione di PyAmp",
    "Instalación de PyAmp": "Installazione di PyAmp",
    "Instalando PyAmp…": "Installazione di PyAmp…",
    "Preparando la instalación…": "Preparazione dell'installazione…",
    "Copiando archivos…": "Copia dei file…",
    "Copiando la aplicación…": "Copia dell'applicazione…",
    "Creando el acceso directo…": "Creazione del collegamento…",
    "Actualizando el menú de aplicaciones…": "Aggiornamento del menu delle applicazioni…",
    "Instalación completada.": "Installazione completata.",
    "PyAmp se ha instalado correctamente.": "PyAmp è stato installato correttamente.",
    "Instalación completada": "Installazione completata",
    "¿Quieres eliminar el archivo instalador?\n{path}": (
        "Vuoi eliminare il file di installazione?\n{path}"
    ),
    "Archivo instalador eliminado.": "File di installazione eliminato.",
    "No se pudo eliminar el archivo instalador.": (
        "Impossibile eliminare il file di installazione."
    ),
    "No se pudo instalar: {error}": "Impossibile installare: {error}",
    "No se encontró la carpeta de aplicaciones.": "Cartella delle applicazioni non trovata.",
    "La instalación automática solo está disponible en la app empaquetada.": (
        "L'installazione automatica è disponibile solo nell'app pacchettizzata."
    ),
    "Sistema operativo no compatible.": "Sistema operativo non supportato.",
}

#: Traducciones al árabe (misma clave: la cadena española).
_AR: dict[str, str] = {
    # ------------------------------------------------------- ventana: menús
    "&Archivo": "&ملف",
    "Abrir &archivo(s)...": "فتح &ملف...",
    "Abrir &carpeta...": "فتح &مجلد...",
    "Escanear carpeta en &biblioteca...": "فحص مجلد إلى &المكتبة...",
    "&Cargar playlist...": "&تحميل قائمة التشغيل...",
    "&Guardar playlist como...": "&حفظ قائمة التشغيل باسم...",
    "&Vaciar lista": "&تفريغ القائمة",
    "&Salir": "&خروج",
    "&Ver": "&عرض",
    "Canciones (&tabla)": "الأغاني (&جدول)",
    "F&avoritos (★)": "الم&فضلة (★)",
    "&Radio online": "&راديو عبر الإنترنت",
    "Mostrar es&trograma": "إظهار ال&طيف",
    "Mostrar &imagen": "إظهار ال&صورة",
    "Ver &letra": "عرض ال&كلمات",
    "&Tema": "&السمة",
    "&Editar": "&تحرير",
    "&Editar letra...": "&تحرير الكلمات...",
    "Editar o escribir la letra de la canción seleccionada": (
        "تحرير أو كتابة كلمات الأغنية المحددة"
    ),
    "&Ajustes...": "&الإعدادات...",
    # -------------------------------------------------- ventana: transporte
    "Anterior": "السابق",
    "Siguiente": "التالي",
    "Pista anterior": "المقطع السابق",
    "Pista siguiente": "المقطع التالي",
    "Reproducir/pausar": "تشغيل/إيقاف مؤقت",
    "Pausar": "إيقاف مؤقت",
    "Reanudar": "استئناف",
    "Reproducir": "تشغيل",
    "Aleatorio": "عشوائي",
    "Aleatorio: siguiente pista al azar": "عشوائي: تشغيل المقطع التالي عشوائياً",
    "Repetir": "تكرار",
    "Repetir: repite la pista actual una vez y se desactiva": (
        "تكرار: يعيد المقطع الحالي مرة واحدة ثم يتوقف"
    ),
    "Repetición desactivada (repetida una vez)": "تم إيقاف التكرار (أُعيد مرة واحدة)",
    "Marcar la pista actual como favorita": "وضع علامة على المقطع الحالي كمفضل",
    "Favorito": "مفضل",
    "Silenciar": "كتم",
    "Silenciar (mute)": "كتم الصوت",
    "Volumen": "مستوى الصوت",
    "Posición": "الموضع",
    "Posición de reproducción": "موضع التشغيل",
    "Pista anterior (multimedia)": "المقطع السابق (وسائط)",
    "Reproducir/pausar (multimedia)": "تشغيل/إيقاف مؤقت (وسائط)",
    "Reproducir (multimedia)": "تشغيل (وسائط)",
    "Pausar (multimedia)": "إيقاف مؤقت (وسائط)",
    "Pista siguiente (multimedia)": "المقطع التالي (وسائط)",
    # ---------------------------------------------------- ventana: estados
    "Audio no disponible": "الصوت غير متاح",
    "Escaneando {folder} ...": "جارٍ فحص {folder} ...",
    "No se encontraron archivos de audio": "لم يتم العثور على ملفات صوتية",
    "{count} pistas añadidas": "تمت إضافة {count} مقطعاً",
    "Ya hay un escaneo en curso": "هناك فحص قيد التنفيذ بالفعل",
    "Sin carpetas guardadas — «Archivo → Escanear carpeta en biblioteca...»": (
        "لا توجد مجلدات محفوظة — «ملف ← فحص مجلد إلى المكتبة...»"
    ),
    "Escaneando… {processed} archivos ({current})": "جارٍ الفحص… {processed} ملفاً ({current})",
    "Biblioteca: {added} añadidas, {updated} actualizadas, {skipped} sin cambios, "
    "{removed} eliminadas": (
        "المكتبة: {added} مضافة، {updated} محدّثة، {skipped} دون تغيير، {removed} محذوفة"
    ),
    ", {errors} errores": "، {errors} أخطاء",
    " (escaneo cancelado)": " (تم إلغاء الفحص)",
    "▶ {name} ({count} pistas en cola)": "▶ {name} ({count} مقطعاً في قائمة الانتظار)",
    "{count} pistas en cola — ▶ para reproducir": ("{count} مقطعاً في قائمة الانتظار — ▶ للتشغيل"),
    "Playlist cargada ({count} pistas en cola)": (
        "تم تحميل قائمة التشغيل ({count} مقطعاً في قائمة الانتظار)"
    ),
    "La playlist está vacía": "قائمة التشغيل فارغة",
    "Playlist guardada en {path}": "تم حفظ قائمة التشغيل في {path}",
    "Playlist vaciada": "تم تفريغ قائمة التشغيل",
    "Atajos de teclado actualizados": "تم تحديث اختصارات لوحة المفاتيح",
    "Ajustes aplicados: notificaciones {state}, {seconds} s": (
        "تم تطبيق الإعدادات: الإشعارات {state}، {seconds} ث"
    ),
    "activadas": "مفعّلة",
    "desactivadas": "معطّلة",
    "Notificación de prueba": "إشعار تجريبي",
    "PyAmp funciona correctamente": "PyAmp يعمل بشكل صحيح",
    "La notificación falló: {error}": "فشل الإشعار: {error}",
    "Notificación de prueba enviada": "تم إرسال الإشعار التجريبي",
    "Favorito no guardado: {error}": "لم يتم حفظ المفضلة: {error}",
    "★ Añadida a favoritos": "★ أُضيف إلى المفضلة",
    "★ Quitada de favoritos": "★ أُزيل من المفضلة",
    "Espectrograma visible": "الطيف ظاهر",
    "Espectrograma oculto": "الطيف مخفي",
    "Imagen visible": "الصورة ظاهرة",
    "Imagen oculta": "الصورة مخفية",
    "Aleatorio activado": "تم تفعيل العشوائي",
    "Aleatorio desactivado": "تم إيقاف العشوائي",
    "Repetición activada": "تم تفعيل التكرار",
    "Repetición desactivada": "تم إيقاف التكرار",
    "Selecciona una canción para editar su letra (o reproduce una)": (
        "اختر أغنية لتحرير كلماتها (أو شغّل واحدة)"
    ),
    "Letra guardada en {path}": "تم حفظ الكلمات في {path}",
    "▶ Saltado a {time} (letra)": "▶ تم الانتقال إلى {time} (الكلمات)",
    # ------------------------------------------------- diálogos de fichero
    "Abrir archivos de audio": "فتح ملفات صوتية",
    "Archivos de audio ({filters});;Todos los archivos (*)": (
        "ملفات صوتية ({filters});;كل الملفات (*)"
    ),
    "Abrir carpeta": "فتح مجلد",
    "Escanear carpeta para la biblioteca": "فحص مجلد للمكتبة",
    "Cargar playlist": "تحميل قائمة التشغيل",
    "Playlists (*.m3u *.m3u8);;Todos los archivos (*)": (
        "قوائم التشغيل (*.m3u *.m3u8);;كل الملفات (*)"
    ),
    "Guardar playlist como": "حفظ قائمة التشغيل باسم",
    "Playlist M3U (*.m3u);;Todos los archivos (*)": "قائمة تشغيل M3U (*.m3u);;كل الملفات (*)",
    "No se pudo cargar la playlist: {error}": "تعذّر تحميل قائمة التشغيل: {error}",
    "No se pudo guardar la playlist: {error}": "تعذّر حفظ قائمة التشغيل: {error}",
    # ------------------------------------------------------ vista Canciones
    "Nombre": "الاسم",
    "Duración": "المدة",
    "Artista": "الفنان",
    "Buscar nombre, artista o álbum...": "ابحث عن اسم أو فنان أو ألبوم...",
    "Refrescar canciones": "تحديث الأغاني",
    "Catálogo cargado": "تم تحميل الفهرس",
    "Sin resultados para «{term}»": "لا نتائج لـ «{term}»",
    "Aún no hay favoritas — marca ★ en la vista Canciones": ("لا مفضلة بعد — ضع ★ في عرض الأغاني"),
    "Biblioteca vacía — «Archivo → Escanear carpeta en biblioteca...»": (
        "المكتبة فارغة — «ملف ← فحص مجلد إلى المكتبة...»"
    ),
    "{visible} de {total} canciones · {favorites} favoritas": (
        "{visible} من {total} أغنية · {favorites} مفضلة"
    ),
    # ------------------------------------------------------ panel Biblioteca
    "Buscar título, artista o álbum...": "ابحث عن عنوان أو فنان أو ألبوم...",
    "Refrescar biblioteca": "تحديث المكتبة",
    "Biblioteca": "المكتبة",
    "Totales de la biblioteca": "إجماليات المكتبة",
    "(Sin artista)": "(بدون فنان)",
    "(Sin álbum)": "(بدون ألبوم)",
    "(mostrando solo los primeros {limit} resultados)": ("(تُعرض أول {limit} نتيجة فقط)"),
    "{count} pistas": "{count} مقطعاً",
    "{tracks} pistas · {artists} artistas · {albums} álbumes": (
        "{tracks} مقطعاً · {artists} فناناً · {albums} ألبوماً"
    ),
    # -------------------------------------------------------------- Ajustes
    "Ajustes de PyAmp": "إعدادات PyAmp",
    "General": "عام",
    "Idioma:": "اللغة:",
    "Idioma de la aplicación. Al aceptar, PyAmp se reinicia en el idioma elegido.": (
        "لغة التطبيق. عند الموافقة، سيعيد PyAmp التشغيل باللغة المختارة."
    ),
    "Notificaciones": "الإشعارات",
    "Apariencia": "المظهر",
    "Atajos": "الاختصارات",
    "Información": "معلومات",
    "Activar notificaciones de escritorio": "تفعيل إشعارات سطح المكتب",
    "Duración en pantalla de cada notificación": "مدة عرض كل إشعار على الشاشة",
    "Duración:": "المدة:",
    "Probar notificación": "اختبار الإشعار",
    "Envía una notificación de prueba ahora": "أرسل إشعاراً تجريبياً الآن",
    "Tema:": "السمة:",
    "Tema visual de toda la aplicación": "السمة المرئية للتطبيق بأكمله",
    "Mostrar espectrograma en la cabecera": "إظهار الطيف في الترويسة",
    "Mostrar imagen en la cabecera": "إظهار الصورة في الترويسة",
    "Pulsa la combinación nueva en cada recuadro. Vacío = valor por defecto.": (
        "اضغط التركيبة الجديدة في كل مربع. فارغ = القيمة الافتراضية."
    ),
    "Ver: Canciones": "عرض: الأغاني",
    "Ver: Favoritos": "عرض: المفضلة",
    "Ver: Radio": "عرض: الراديو",
    "Abrir archivo(s)": "فتح ملف",
    "Guardar playlist": "حفظ قائمة التشغيل",
    "Ajustes": "الإعدادات",
    "Salir": "خروج",
    "Versión:": "الإصدار:",
    "Notificador:": "أداة الإشعارات:",
    "Biblioteca:": "المكتبة:",
    "Idioma": "اللغة",
    # ---------------------------------------------------------------- radio
    "Radio online": "راديو عبر الإنترنت",
    "Radio": "راديو",
    "Emisora": "محطة",
    "Género": "النوع",
    "País": "البلد",
    "Detener": "إيقاف",
    "Añadir": "إضافة",
    "Editar": "تحرير",
    "Eliminar": "إزالة",
    "Buscar emisora, género o país...": "ابحث عن محطة أو نوع أو بلد...",
    "{shown} de {total} emisoras": "{shown} من {total} محطة",
    "Selecciona una emisora": "اختر محطة",
    "No hay emisoras: busca o añade una": "لا توجد محطات: ابحث أو أضف واحدة",
    "Esa emisora ya está en la lista.": "هذه المحطة موجودة بالفعل في القائمة.",
    "Solo se pueden editar tus emisoras": "يمكن تحرير محطاتك فقط",
    "Solo se pueden borrar tus emisoras": "يمكن حذف محطاتك فقط",
    "¿Eliminar «{name}»?": "هل تريد حذف «{name}»؟",
    "Reproduciendo {name}": "جارٍ تشغيل {name}",
    "▶ {name} (radio)": "▶ {name} (راديو)",
    "Radio detenida": "تم إيقاف الراديو",
    "Emisora de radio": "محطة راديو",
    "Nombre:": "الاسم:",
    "Dirección (URL):": "العنوان (URL):",
    "Género:": "النوع:",
    "Clásica": "كلاسيكية",
    "Actualidad": "أخبار",
    "Cultura": "ثقافة",
    "EE. UU.": "الولايات المتحدة",
    "Suiza": "سويسرا",
    "Francia": "فرنسا",
    "España": "إسبانيا",
    "Buscar emisoras": "البحث عن محطات",
    "Busca emisoras online de tu zona": "ابحث عن محطات عبر الإنترنت قريبة منك",
    "Aún no tienes emisoras. Busca las de tu zona.": ("ليس لديك محطات بعد. ابحث عن محطات منطقتك."),
    "Buscando emisoras…": "جارٍ البحث عن محطات…",
    "Usando tu ubicación para buscarlas…": "يُستخدم موقعك للعثور عليها…",
    "Se encontraron {n} emisoras": "تم العثور على {n} محطة",
    "No se pudieron buscar emisoras: {error}": "تعذّر البحث عن المحطات: {error}",
    # ----------------------------------------------------------------- letra
    "Letra — PyAmp": "الكلمات — PyAmp",
    "Letra no disponible :(": "الكلمات غير متاحة :(",
    "No hay ninguna pista en reproducción": "لا يوجد مقطع قيد التشغيل",
    "No encontré «{stem}.lrc» (junto al audio o en {directory})": (
        "لم أجد «{stem}.lrc» (بجانب الصوت أو في {directory})"
    ),
    "No se pudo leer {name}: {error}": "تعذّرت قراءة {name}: {error}",
    "{name}: sin marcas de tiempo [mm:ss]": "{name}: بدون طوابع زمنية [mm:ss]",
    "Letra: {name}": "الكلمات: {name}",
    # -------------------------------------------------------- editor de letras
    "Editar letra — {title}": "تحرير الكلمات — {title}",
    "Existente": "موجود",
    "Nuevo": "جديد",
    "Formato: una línea por frase. Para sincronizar añade marcas de tiempo "
    "«[mm:ss]» al principio de cada línea.": (
        "التنسيق: سطر واحد لكل عبارة. للمزامنة أضف طوابع زمنية «[mm:ss]» " "في بداية كل سطر."
    ),
    "Escribe aquí la letra de la canción...": "اكتب كلمات الأغنية هنا...",
    "Guardar": "حفظ",
    "No se pudo guardar": "تعذّر الحفظ",
    "No se pudo escribir {path}:\n{error}": "تعذّرت الكتابة في {path}:\n{error}",
    # --------------------------------------------------- carátula / metadatos
    "Carátula": "الغلاف",
    "Artista desconocido": "فنان غير معروف",
    "Sin título": "بدون عنوان",
    # --------------------------------------------------- 0.2.0: ventana/temas
    "Tamaño de la ventana:": "حجم النافذة:",
    "Ancho": "العرض",
    "Alto": "الارتفاع",
    "Tamaño por defecto de la ventana principal": "الحجم الافتراضي للنافذة الرئيسية",
    "Tamaño de ventana: {width}×{height}": "حجم النافذة: {width}×{height}",
    "Crear tema nuevo…": "إنشاء سمة جديدة…",
    "Crear tema nuevo": "إنشاء سمة جديدة",
    "Nombre del tema:": "اسم السمة:",
    "Mi tema": "سمتي",
    "Nombre para el nuevo tema": "اسم للسمة الجديدة",
    "Fondo:": "الخلفية:",
    "Texto:": "النص:",
    "Acento:": "اللون المميز:",
    "Elegir color": "اختر لوناً",
    "Mostrar archivos ocultos": "إظهار الملفات المخفية",
    "Los archivos ocultos aparecen al principio, con un «-» delante.": (
        "تظهر الملفات المخفية في البداية مع «-» قبلها."
    ),
    "Mostrando archivos ocultos": "جارٍ إظهار الملفات المخفية",
    "Ocultando archivos ocultos": "جارٍ إخفاء الملفات المخفية",
    # ------------------------------------------------- 0.2.0: menú canciones
    "Mover a favoritos": "نقل إلى المفضلة",
    "Quitar de favoritos": "إزالة من المفضلة",
    "Ocultar": "إخفاء",
    "Mostrar": "إظهار",
    "Renombrar": "إعادة تسمية",
    "Editar metadata": "تحرير البيانات الوصفية",
    "Pista oculta": "مقطع مخفي",
    "Pista visible": "مقطع ظاهر",
    "Nuevo nombre:": "الاسم الجديد:",
    "Ya existe un archivo con ese nombre": "يوجد ملف بهذا الاسم بالفعل",
    "No se pudo renombrar: {error}": "تعذّرت إعادة التسمية: {error}",
    "Renombrado a {name}": "أُعيدت التسمية إلى {name}",
    "No se encontró el archivo: {path}": "لم يتم العثور على الملف: {path}",
    "¿Quitar «{name}» de la biblioteca?\n(El archivo no se borra del disco.)": (
        "هل تريد إزالة «{name}» من المكتبة؟\n(لن يُحذف الملف من القرص.)"
    ),
    "Pista eliminada de la biblioteca": "تمت إزالة المقطع من المكتبة",
    "No se pudo eliminar: {error}": "تعذّرت الإزالة: {error}",
    "No se pudo guardar la metadata: {error}": "تعذّر حفظ البيانات الوصفية: {error}",
    "Metadata actualizada": "تم تحديث البيانات الوصفية",
    # -------------------------------------------------- 0.2.0: editor metadata
    "Título:": "العنوان:",
    "Artista:": "الفنان:",
    "Álbum:": "الألبوم:",
    "Artista del álbum:": "فنان الألبوم:",
    "Año:": "السنة:",
    "N.º de pista:": "رقم المقطع:",
    "N.º de disco:": "رقم القرص:",
    # ------------------------------------------------------- 0.2.0: radio
    "Editar Valores": "تحرير القيم",
    # ------------------------------------------------ 0.2.1: historial mensual
    "&Historial": "&السجل",
    "Ver historial del mes": "عرض سجل الشهر",
    "Historial — PyAmp": "السجل — PyAmp",
    "Las 10 canciones más escuchadas": "أكثر 10 أغانٍ استماعاً",
    "Aún no está listo :/": "ليس جاهزاً بعد :/",
    "Cerrar": "إغلاق",
    "{rank}. {title} — {artist}  ({count}×)": "{rank}. {title} — {artist}  ({count}×)",
    "Tu historial del mes ya está listo": "سجل الشهر جاهز الآن",
    "Pulsa para ver las 10 canciones más escuchadas del mes pasado.": (
        "اضغط لعرض أكثر 10 أغانٍ استماعاً في الشهر الماضي."
    ),
    "Ver historial": "عرض السجل",
    # ------------------------------------------------ 0.2.1: ajustes/avanzado
    "Avanzado": "متقدم",
    "Proximamente... :)": "قريباً... :)",
    "Eliminar tema": "حذف السمة",
    "Nombre del tema actual": "اسم السمة الحالية",
    "¿Eliminar el tema «{name}»?": "هل تريد حذف السمة «{name}»؟",
    "Solo se pueden renombrar los temas personalizados": ("يمكن إعادة تسمية السمات المخصصة فقط"),
    "Solo se pueden eliminar los temas personalizados": "يمكن حذف السمات المخصصة فقط",
    "Tema eliminado": "تم حذف السمة",
    "Tema renombrado": "تمت إعادة تسمية السمة",
    # ------------------------------------------------ 0.2.1: información/instalar
    "Autor:": "المؤلف:",
    "Sistema:": "النظام:",
    "Python:": "Python:",
    "Qt:": "Qt:",
    "Formato:": "التنسيق:",
    "Código fuente (Python)": "الشيفرة المصدرية (Python)",
    "Ejecutable de Windows (.exe)": "ملف تنفيذي لويندوز (.exe)",
    "Aplicación de macOS (.app)": "تطبيق macOS (.app)",
    "AppImage de Linux": "AppImage لينكس",
    "Instalar": "تثبيت",
    "Instala PyAmp en este equipo": "ثبّت PyAmp على هذا الجهاز",
    "Instalando PyAmp": "جارٍ تثبيت PyAmp",
    "Instalación de PyAmp": "تثبيت PyAmp",
    "Instalando PyAmp…": "جارٍ تثبيت PyAmp…",
    "Preparando la instalación…": "جارٍ تحضير التثبيت…",
    "Copiando archivos…": "جارٍ نسخ الملفات…",
    "Copiando la aplicación…": "جارٍ نسخ التطبيق…",
    "Creando el acceso directo…": "جارٍ إنشاء الاختصار…",
    "Actualizando el menú de aplicaciones…": "جارٍ تحديث قائمة التطبيقات…",
    "Instalación completada.": "اكتمل التثبيت.",
    "PyAmp se ha instalado correctamente.": "تم تثبيت PyAmp بنجاح.",
    "Instalación completada": "اكتمل التثبيت",
    "¿Quieres eliminar el archivo instalador?\n{path}": ("هل تريد حذف ملف التثبيت؟\n{path}"),
    "Archivo instalador eliminado.": "تم حذف ملف التثبيت.",
    "No se pudo eliminar el archivo instalador.": "تعذّر حذف ملف التثبيت.",
    "No se pudo instalar: {error}": "تعذّر التثبيت: {error}",
    "No se encontró la carpeta de aplicaciones.": "لم يتم العثور على مجلد التطبيقات.",
    "La instalación automática solo está disponible en la app empaquetada.": (
        "التثبيت التلقائي متاح فقط في التطبيق المعبّأ."
    ),
    "Sistema operativo no compatible.": "نظام التشغيل غير مدعوم.",
}

#: Traducciones por código de idioma.
_TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": _EN,
    "it": _IT,
    "ar": _AR,
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


def is_rtl(code: str | None = None) -> bool:
    # El árabe (y otros idiomas RTL) se escriben de derecha a izquierda.
    key = str(code or _LANGUAGE).strip().lower()
    return key in RTL_LANGUAGES


def tr(text: str) -> str:
    if _LANGUAGE == DEFAULT_LANGUAGE:
        return text
    return _TRANSLATIONS.get(_LANGUAGE, {}).get(text, text)
