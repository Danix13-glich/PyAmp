# PyAmp 0.2.4

## Correcciones

- Corregidos bugs y fallos leves.
- **Letras sincronizadas**: la búsqueda online solo acepta letras con marcas de tiempo, descarta las letras planas y sustituye las antiguas por una sincronizada cuando la encuentra.
- **Búsqueda de letras más fiable**: deduce el artista desde el nombre del archivo, limpia `feat.`, paréntesis y corchetes, prueba varias combinaciones y reintenta ante errores temporales.
- **Botón A para ver la letra** junto a Favoritos, también con el atajo `Ctrl+L`.
- La letra encontrada se guarda automáticamente junto a la canción.
- **Corregido el bloqueo de la barra de posición** al saltar a una parte de la canción desde el lector de letras.
- Corregido el avance de la reproducción después de un salto manual si VLC se quedaba detenido en ese punto.

## Archivos

- `pyamp_0.2.4.AppImage` — Linux (x86_64)
- `pyamp_0.2.4.exe` — Windows (x64)
- `pyamp_0.2.4.dmg` — macOS (Intel, funciona también en Apple Silicon con Rosetta)

> En Linux el AppImage incluye libVLC. En Windows y macOS las versiones empaquetadas también lo incluyen; si el audio no arranca, instala VLC desde videolan.org.
