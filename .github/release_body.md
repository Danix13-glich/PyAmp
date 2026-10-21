# PyAmp 0.2.1 beta 16

## Novedades

- **Espectro sin micrófono**: el estograma ya no captura el audio del sistema. libVLC decodifica una segunda copia en paralelo y entrega las muestras directamente, así que el sistema operativo deja de mostrar que PyAmp usa el micrófono.
- **Dependencias automáticas**: si ejecutas desde el código y falta algún paquete de Python, la app lo instala sola la primera vez en un entorno local (`~/.local/share/PyAmp/runtime`) y se reinicia. En Windows, si no hay VLC, se descarga una copia portátil. Los paquetes AppImage, .exe y .dmg ya llevan todo incluido.
- **Instalación**: la barra de progreso aparece en su propia ventana, con el aspecto normal de una barra de carga. Al llegar al 90 % se detiene un instante antes de completar, para que el proceso no termine de golpe.
- **Radio**: se han eliminado los botones **Añadir**, **Editar** y **Eliminar** de debajo de **Reproducir** y **Detener**. La edición y el borrado siguen disponibles con el botón derecho sobre una emisora.
- **Inicio en Radio**: si la app se cerró con la vista de radio, al abrirla la cabecera aparece limpia, sin la carátula, el título ni el formato de la última canción reproducida.
- **Pruebas**: cobertura del instalador en Linux, Windows y macOS, de la pausa de la barra de progreso y de la instalación automática de dependencias.

## Archivos

- `pyamp_0.2.1-beta16.AppImage` — Linux (x86_64)
- `pyamp_0.2.1-beta16.exe` — Windows (x64)
- `pyamp_0.2.1-beta16.dmg` — macOS (Intel, funciona también en Apple Silicon con Rosetta)

> En Linux el AppImage incluye libVLC. En Windows y macOS las versiones empaquetadas también lo incluyen; si el audio no arranca, instala VLC desde videolan.org.
