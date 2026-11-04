# PyAmp 0.2.5

## Correcciones y mejoras

- **Radio sin cortes permanentes**: si una emisora deja de sonar, PyAmp detecta el bloqueo y vuelve a conectar automáticamente. También reconecta si VLC sigue diciendo que reproduce pero el reloj del directo se ha quedado congelado.
- **Audio por Bluetooth**: nueva salida de audio en Ajustes → General. PyAmp usa automáticamente los auriculares o altavoces Bluetooth conectados y mueve el sonido a esa salida.
- **Botones multimedia y Bluetooth**: más botones compatibles (anterior, siguiente, reproducir, pausar, detener, volumen, retroceder/avanzar, repetir y aleatorio). Se pueden cambiar o desactivar en Ajustes → Avanzado.
- **Sin pitidos al enrutar el audio**: se evita mover una y otra vez el mismo flujo de sonido cuando ya está en la salida correcta.
- **Letras sincronizadas**: la búsqueda online solo acepta letras con marcas de tiempo; las letras planas se sustituyen cuando aparece una sincronizada.
- **Búsqueda manual de letras**: si la búsqueda automática falla, aparece un botón para introducir solo el nombre y el artista.
- **Letras sin congelarse**: la letra se actualiza también al cambiar de escritorio, abrir diálogos o cambiar ajustes.
- **Saltar desde la letra**: la barra de posición ya no se queda bloqueada al seleccionar una parte de la canción.
- **Tamaño de ventana**: el tamaño elegido en Apariencia se aplica al pulsar OK y se conserva tras reiniciar.
- **Favoritos**: las canciones favoritas tienen la misma probabilidad que el resto al usar el modo aleatorio. Importar y exportar favoritos están disponibles desde la vista Favoritos.
- **Historial y radio**: pestañas de Más escuchadas y Búsquedas, descarga automática a la biblioteca y búsqueda de canciones de radio.
- **Importar M3U**: se pregunta si se quiere eliminar el archivo `.m3u` después de importarlo.
- **Notificaciones**: pulsar la notificación de restablecimiento abre PyAmp.

## Archivos

- `pyamp_0.2.5.AppImage` — Linux (x86_64)
- `pyamp_0.2.5.exe` — Windows (x64)
- `pyamp_0.2.5.dmg` — macOS (Intel, funciona también en Apple Silicon con Rosetta)

> En Linux el AppImage incluye libVLC. En Windows y macOS las versiones empaquetadas también lo incluyen; si el audio no arranca, instala VLC desde videolan.org.
