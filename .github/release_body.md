# PyAmp 0.2.1 beta 16

## Novedades

- **Botones de Aleatorio y Repetir**: usan el emoji como imagen (el mismo dibujo de 🔀 y 🔁), así que se ven siempre, incluso cuando Qt no puede pintar emojis como texto.
- **Iconos visibles en todos los temas**: en el tema Winamp nativo los iconos toman el color real del texto del botón del sistema, de modo que ya no desaparecen con temas claros.
- **Espectro sin micrófono**: el estograma no captura audio del sistema; libVLC decodifica una segunda copia en paralelo y entrega las muestras directamente.
- **Dependencias automáticas**: si ejecutas desde el código y falta algún paquete, la app lo instala sola la primera vez en un entorno local (`~/.local/share/PyAmp/runtime`) y se reinicia. En Windows, si no hay VLC, se descarga una copia portátil.
- **Instalación**: la barra de progreso aparece en su propia ventana y se detiene un instante en el 90 % antes de completar.
- **Radio**: sin botones Añadir/Editar/Eliminar (siguen en el menú contextual). Al abrir con la vista Radio la cabecera aparece limpia.

## Archivos

- `pyamp_0.2.1-beta16.AppImage` — Linux (x86_64)
- `pyamp_0.2.1-beta16.exe` — Windows (x64)
- `pyamp_0.2.1-beta16.dmg` — macOS (Intel, funciona también en Apple Silicon con Rosetta)

> En Linux el AppImage incluye libVLC. En Windows y macOS las versiones empaquetadas también lo incluyen; si el audio no arranca, instala VLC desde videolan.org.
