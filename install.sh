#!/usr/bin/env bash
# Instala PyAmp como aplicación de escritorio para el usuario actual:
# acceso directo en el menú de aplicaciones + icono. No necesita sudo.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$(command -v python3 || command -v python || true)"
if [ -z "$PYTHON" ]; then
    echo "No encuentro python3 en el PATH." >&2
    exit 1
fi

ICON_ROOT="$HOME/.local/share/icons/hicolor"
APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$APPS_DIR" "$ICON_ROOT/scalable/apps"

# Icono en varios tamaños (PNG) + SVG escalable, para que aparezca en el
# menú de aplicaciones y en el buscador, no solo en la barra de tareas.
if ! QT_QPA_PLATFORM=offscreen "$PYTHON" "$APP_DIR/packaging/make_icons.py" \
    "$APP_DIR/assets/logo.svg" "$ICON_ROOT"; then
    echo "Aviso: no se pudieron generar los PNG; se instala solo el SVG." >&2
    cp "$APP_DIR/assets/logo.svg" "$ICON_ROOT/scalable/apps/pyamp.svg"
fi

# Ruta absoluta al PNG: evita que el cajón de aplicaciones dependa de la
# caché del tema de iconos (que a veces tarda en refrescarse o no lo ve).
ICON_PNG="$ICON_ROOT/256x256/apps/pyamp.png"
if [ -f "$ICON_PNG" ]; then
    ICON_VALUE="$ICON_PNG"
else
    ICON_VALUE="pyamp"
fi

cat > "$APPS_DIR/pyamp.desktop" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=PyAmp
GenericName=Reproductor de música
Comment=Escucha música local y radios online
Exec=$PYTHON $APP_DIR/main.py
Path=$APP_DIR
Icon=$ICON_VALUE
Terminal=false
Categories=AudioVideo;Audio;Player;
Keywords=musica;música;player;winamp;radio;
StartupNotify=true
StartupWMClass=PyAmp
EOF

chmod +x "$APPS_DIR/pyamp.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$ICON_ROOT" >/dev/null 2>&1 || true
fi
for KBS in kbuildsycoca6 kbuildsycoca5; do
    if command -v "$KBS" >/dev/null 2>&1; then
        "$KBS" --noincremental >/dev/null 2>&1 || true
        break
    fi
done

echo "PyAmp instalado. Búscalo en el menú de aplicaciones como «PyAmp»."
echo "Para desinstalarlo: rm \"$APPS_DIR/pyamp.desktop\" y la carpeta \"$ICON_ROOT\" de pyamp."
