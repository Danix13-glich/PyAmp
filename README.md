<p align="center">
  <img src="assets/logo.svg" alt="Logotipo de PyAmp" width="160">
</p>

<h1 align="center">PyAmp</h1>

<p align="center">
  Reproductor de música estilo Winamp para Linux, Windows y macOS.<br>
  Música local, radios online, espectro en tiempo real, letras y notificaciones de escritorio.
</p>

<p align="center">
  <a href="https://github.com/Danix13-glich/PyAmp/actions/workflows/ci.yml"><img src="https://github.com/Danix13-glich/PyAmp/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/platform-Linux%20%7C%20Windows%20%7C%20macOS-lightgrey" alt="Plataformas">
</p>

<p align="center">
  <b>English version:</b> <a href="README_EN.md">README_EN.md</a>
</p>

## Funciones

- 🎵 Reproducción local (MP3, FLAC, OGG, M4A, WAV...) con libVLC.
- 📚 Biblioteca en SQLite: escanear carpetas, buscar y vista de canciones.
- ⭐ Favoritos con su propia vista.
- 📻 Radio online: emisoras incluidas y las que añadas tú (nombre y URL).
- 📊 Espectro FFT real en la cabecera (numpy + QPainter).
- 📝 Letras `.lrc` sincronizadas y editor de letras.
- 🔔 Notificación nativa de escritorio en cada cambio de pista.
- 🔀 Aleatorio y 🔁 repetir.
- 🎨 Tres temas visuales (Winamp oscuro, Verde terminal y Arena clara).
- 🌍 Interfaz en español e inglés.
- ⌨️ Teclas multimedia e integración MPRIS en Linux.
- 🖥️ Multiplataforma: Linux primero (Fedora KDE), Windows y macOS.

## Instalación

### Fedora

```bash
sudo dnf install vlc python3-vlc python3.12
git clone https://github.com/Danix13-glich/PyAmp.git
cd PyAmp
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Para que aparezca en el menú de aplicaciones con su icono: abre PyAmp y pulsa
**«Instalar»** en **Ajustes → General → Información**.

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

## Uso

- **Archivo → Abrir archivo(s) / Abrir carpeta** para reproducir.
- **Archivo → Escanear carpeta en biblioteca** para añadir música al catálogo.
- **Ver → Canciones / Favoritos / Radio online** (`Ctrl+1`, `Ctrl+2`, `Ctrl+3`).
- **Ajustes** (`Ctrl+,`) para idioma, notificaciones, tema y atajos.

## Notificaciones

PyAmp muestra una notificación nativa cada vez que cambia la pista actual
(play, siguiente, anterior o salto en la playlist; nunca al pausar o
reanudar la misma pista). Se puede activar o desactivar y ajustar su
duración en **Ajustes → General**.

## Desarrollo

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest
ruff check src tests main.py
black --check src tests main.py
mypy
python main.py
```

## Contacto

¿Quieres más información o has tenido algún error de uso? Escríbeme a
**danieldiaz.dx3@gmail.com**.

## Licencia

MIT — ver [LICENSE](LICENSE). Copyright © 2026 Danix13-glich.
