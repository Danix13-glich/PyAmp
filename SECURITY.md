# Seguridad de PyAmp

## Soporte de versiones

Solo la última versión publicada (`main` y las releases de GitHub) recibe
correcciones de seguridad. Usa siempre la release más reciente.

## Reportar una vulnerabilidad

**Por favor, no abras una issue pública para vulnerabilidades.**

1. Usa la función **"Report a vulnerability"** de la pestaña *Security* del
   repo de GitHub (recomendado), o
2. Contacta al mantenedor (@Danix13-glich) por privado indicando:
   - descripción del problema y pasos para reproducirlo,
   - versión de PyAmp y SO,
   - impacto estimado (p. ej. ejecución remota de código, robo de datos),
   - corrección sugerida si la tienes.

Responderé en un plazo razonable y coordinaremos la publicación del fix
antes de hacerlo público.

## Alcance típico

- Código de este repositorio (`src/`, `install.py`, workflows de CI/CD).
- Dependencias directas: se reportan aquí y se upstream cuando aplica.

Fuera de alcance (reportar al proyecto correspondiente):
- Vulnerabilidades en VLC/libVLC, PySide6/Qt, mutagen u otras dependencias.
- Problemas del propio entorno del usuario (permisos de archivos, etc.).

## Datos locales

PyAmp guarda su configuración en `~/.config/PyAmp/` (Linux),
`%APPDATA%\PyAmp\` (Windows) o `~/Library/Application Support/PyAmp/`
(macOS), y datos (BD, logs) en las rutas estándar de datos del SO.
Ningún dato personal sale de tu equipo salvo:
- búsquedas de radios en radio-browser.info,
- búsquedas de letras en lrclib.net.

No se envían telemetría ni analíticas.

## Estado de la licencia

⚠️ La licencia del proyecto está **pendiente de decisión** y se fijará
antes de la primera release pública (ver README).
