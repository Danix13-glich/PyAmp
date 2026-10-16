<p align="center">
  <img src="assets/logo.svg" alt="Logotipo de PyAmp" width="160">
</p>

<h1 align="center">PyAmp</h1>

<p align="center">
  Reproductor de música estilo Winamp moderno para Linux, Windows y macOS.<br>
  Música local + radios online, ecualizador real, visualizador, letras sincronizadas y notificaciones nativas de escritorio.
</p>

<p align="center">
  <a href="https://github.com/Danix13-glich/PyAmp/actions/workflows/ci.yml"><img src="https://github.com/Danix13-glich/PyAmp/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/platform-Linux%20%7C%20Windows%20%7C%20macOS-lightgrey" alt="Plataformas">
  <img src="https://img.shields.io/github/v/release/Danix13-glich/PyAmp" alt="Release">
</p>

<p align="center">
  <b>English:</b> <a href="README_EN.md">README_EN.md</a>
</p>

> ⚠️ **Estado: Fase 0 (esqueleto).** La app abre como una ventana vacía. Las funciones llegan fase a fase.

## Capturas

| Ventana principal | Lista de reproducción | Ecualizador |
| ----------------- | --------------------- | ----------- |
| _(llega en Fase 3)_ | _(llega en Fase 3)_ | _(llega en Fase 4)_ |

## Funciones (hoja de ruta)

- 🎵 Reproducción local (MP3, FLAC, OGG, M4A, WAV...) con libVLC
- 📻 Radios online vía [radio-browser.info](https://www.radio-browser.info/) con favoritos
- 🎚️ Ecualizador real de 10 bandas (VLC `AudioEqualizer`) con presets
- 📊 Visualizador FFT en tiempo real (numpy + QPainter)
- 📝 Letras sincronizadas (`.lrc` local + [lrclib.net](https://lrclib.net/))
- 🔔 **Notificación nativa de escritorio en cada cambio de pista** (D-Bus en Linux, Toasts en Windows, Notification Center en macOS)
- 🗄️ Biblioteca musical con SQLite: escaneo, búsqueda, playlists e historial
- 🎨 Temas claro/oscuro con acentos configurables; skins clásicos `.wsz` (fase avanzada)
- ⌨️ Teclas multimedia e integración MPRIS en Linux (KDE Plasma)
- 🖥️ Multiplataforma: Linux primero (Fedora KDE), Windows 10/11, macOS 12+

## Instalación rápida

```bash
# Linux / macOS
curl -fsSL https://raw.githubusercontent.com/Danix13-glich/PyAmp/main/install.sh | bash
```

```powershell
# Windows PowerShell
iwr -useb https://raw.githubusercontent.com/Danix13-glich/PyAmp/main/install.ps1 | iex
```

```bash
# Universal (si ya tienes Python)
git clone https://github.com/Danix13-glich/PyAmp.git
cd PyAmp
python install.py
```

> El instalador universal crea un virtualenv, instala dependencias, comprueba libVLC y registra un acceso directo. Es idempotente: se puede ejecutar tantas veces como quieras (`--uninstall` para desinstalar).

## Instalación manual

### Fedora (plataforma principal)

```bash
sudo dnf install vlc python3-vlc python3.12
git clone https://github.com/Danix13-glich/PyAmp.git
cd PyAmp
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Debian / Ubuntu

```bash
sudo apt install vlc python3-venv python3-pip
git clone https://github.com/Danix13-glich/PyAmp.git
cd PyAmp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Windows 10/11

```powershell
# 1. Instala VLC (para libVLC): https://www.videolan.org/
# 2. Instala Python 3.11+: https://www.python.org/ (marca "Add to PATH")
git clone https://github.com/Danix13-glich/PyAmp.git
cd PyAmp
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### macOS 12+

```bash
brew install --cask vlc
git clone https://github.com/Danix13-glich/PyAmp.git
cd PyAmp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Notificaciones

PyAmp muestra una notificación **nativa** de escritorio cada vez que cambia la pista actual (play, siguiente, anterior o salto en la playlist — nunca al pausar/reanudar la misma pista):

```
┌─────────────────────────────┐
│  PyAmp                      │  ← nombre de la app
│  Título de la canción       │  ← título (fallback: nombre del archivo)
│  Nombre del autor           │  ← artista (fallback: "Artista desconocido")
└─────────────────────────────┘
```

- Linux: D-Bus `org.freedesktop.Notifications` con `dbus-next` — se integra con el centro de notificaciones de KDE/GNOME (bandeja + historial) y respeta "No molestar".
- Windows: Windows Toasts (`windows-toasts`).
- macOS: Notification Center (`pync`).
- Fallback universal: `plyer`. Si un backend falla, se registra en el log y la reproducción no se interrumpe.
- Configurable (duración, activar/desactivar) en *Ajustes → Notificaciones*.

## Desarrollo

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest                # tests
ruff check src tests main.py
black --check src tests main.py
mypy
python main.py        # ejecutar
```

Consulta [CONTRIBUTING.md](CONTRIBUTING.md) para el flujo completo (fases, ramas, Conventional Commits, releases).

## Contribuir

¡Las contribuciones son bienvenidas! Lee [CONTRIBUTING.md](CONTRIBUTING.md) y el [Código de Conducta](CODE_OF_CONDUCT.md). Abre una issue antes de cambios grandes.

## Licencia

⚠️ **Licencia pendiente de decisión.** PyAmp depende de [mutagen](https://mutagen.readthedocs.io/) (GPL-2.0-or-later), libVLC/python-vlc (LGPL-2.1+) y PySide6 (LGPL-3.0). La licencia del proyecto se elegirá antes de la primera release pública — ver [SECURITY.md](SECURITY.md).
