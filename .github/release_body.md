# PyAmp 0.2.3

## Novedades

- **Letras automáticas desde internet**: al reproducir una canción sin archivo `.lrc`, PyAmp busca la letra en LRCLIB y la guarda **junto a la canción**, con el mismo nombre y extensión `.lrc` (por ejemplo, `Cancion.mp3` → `Cancion.lrc`). Si la carpeta no permite escribir, usa `~/.local/share/PyAmp/lyrics`. Antes de aceptarla comprueba que la **duración** coincida (margen de 3 segundos), que **coincida algún artista** y que el **título del archivo esté en el nombre de la letra online**. Se prefiere la letra sincronizada; si no existe, guarda la letra plana.
- **Botón para buscar la letra** cuando la canción no tiene letra o el `.lrc` está vacío.
- **Reanudación al abrir**: si cierras la app a mitad de una canción, al volver a abrirla continúa desde ese mismo punto (o queda lista para continuar si estaba en pausa).
- **Barra de posición arrastrable**: se puede pulsar y arrastrar para saltar a cualquier punto de la canción.
- **Restaurar valores de fábrica** desde **Ajustes → Avanzado**, con confirmación; no borra la biblioteca ni los archivos de música.
- El botón **Instalar** desaparece cuando PyAmp ya se está ejecutando desde su instalación.
- **Velocidad de reproducción** para música y favoritos: botón a la derecha de Repetir que alterna **1x → 1.5x → 2x**. La radio suena siempre a velocidad normal.
- **Radio**: botones **Editar**, **Eliminar** y **Nuevo** debajo de la lista; el botón Play retoma la última emisora escuchada.
- **Corrección de cuelgues de libVLC** al cambiar de pista rápidamente o al terminar una canción: cada reproductor usa su propio objeto `Media` y no se llama a VLC desde sus callbacks.
- **Notificaciones de escritorio** con carátula corregidas (el formato `image-data` de D-Bus era rechazado).
- **Espectro sin micrófono**: libVLC decodifica una copia en paralelo y entrega las muestras directamente, sin capturar el audio del sistema.
- **Dependencias automáticas** si ejecutas desde el código, e instalación en una ventana propia con pausa al 90 %.

## Archivos

- `pyamp_0.2.3.AppImage` — Linux (x86_64)
- `pyamp_0.2.3.exe` — Windows (x64)
- `pyamp_0.2.3.dmg` — macOS (Intel, funciona también en Apple Silicon con Rosetta)

> En Linux el AppImage incluye libVLC. En Windows y macOS las versiones empaquetadas también lo incluyen; si el audio no arranca, instala VLC desde videolan.org.
