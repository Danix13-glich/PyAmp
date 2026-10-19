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

ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$ICON_DIR" "$APPS_DIR"

cp "$APP_DIR/assets/logo.svg" "$ICON_DIR/pyamp.svg"

cat > "$APPS_DIR/pyamp.desktop" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=PyAmp
GenericName=Reproductor de música
Comment=Escucha música local y radios online
Exec=$PYTHON $APP_DIR/main.py
Path=$APP_DIR
Icon=pyamp
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
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi

echo "PyAmp instalado. Búscalo en el menú de aplicaciones como «PyAmp»."
echo "Para desinstalarlo: rm \"$APPS_DIR/pyamp.desktop\" \"$ICON_DIR/pyamp.svg\""
