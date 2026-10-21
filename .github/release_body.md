# PyAmp 0.2.1

## Novedades

- **Espectro**: fondo igual al de la cabecera (sin costura) en todos los temas, barras repartidas a todo el ancho y eliminada la última barra que no se usaba.
- **Vista Radio**: se ocultan Aleatorio, Repetir, Favorito y la barra de posición; el tiempo muestra `∞ / ∞`.
- **Repetir**: repite la pista actual una vez y se desactiva solo.
- **Anterior / Siguiente** cambian de emisora cuando estás en Radio.
- **Aleatorio**: las pistas favoritas pesan 3 veces más.
- **Barra de posición**: un clic salta a ese punto de la canción.
- **Temas personalizados**: se les puede poner nombre al crearlos y el espectro usa su color de fondo real.
- **Icono del cajón de aplicaciones**: ruta absoluta al PNG (se ve siempre).
- **Emisoras**: la lista arranca vacía; botón **«Buscar emisoras»** que usa tu ubicación aproximada y radio-browser para traer las de tu zona. Se guardan en local y se pueden reproducir, editar y eliminar.
- **Historial mensual**: nuevo menú **Historial** con el top 10 del último mes terminado (dorado, plata, bronce y gris) y aviso el día 1 de cada mes.
- **Idiomas**: añadidos **Italiano** y **Árabe** (con interfaz de derecha a izquierda).
- **Apariencia**: renombrar y eliminar temas personalizados desde la misma línea del selector.
- **Avanzado**: nueva pestaña en Ajustes.
- **Instalación integrada**: botón **«Instalar»** en Ajustes → General → Información, con barra de progreso y opción de borrar el archivo instalador al terminar.
- **Información ampliada**: autor, sistema operativo, versión de Python, versión de Qt y formato de la app.
- **Distribuciones**: AppImage para Linux, ejecutable para Windows y DMG para macOS.

> En Linux, el AppImage incluye libVLC; si tu distribución no lo detecta, instala VLC (`sudo dnf install vlc` o `sudo apt install vlc`).
