<p align="center">
  <img src="assets/logo.svg" alt="PyAmp logo" width="160">
</p>

<h1 align="center">PyAmp</h1>

<p align="center">
  A modern Winamp-style music player for Linux, Windows and macOS.<br>
  Local music, online radio, real-time spectrum, lyrics and desktop notifications.
</p>

<p align="center">
  <a href="https://github.com/Danix13-glich/PyAmp/actions/workflows/ci.yml"><img src="https://github.com/Danix13-glich/PyAmp/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/platform-Linux%20%7C%20Windows%20%7C%20macOS-lightgrey" alt="Platforms">
</p>

<p align="center">
  <b>Español:</b> <a href="README.md">README.md</a>
</p>

## Features

- Local playback (MP3, FLAC, OGG, M4A, WAV...) through libVLC.
- SQLite library: scan folders, search and browse songs.
- Favorites with their own view.
- Online radio: stations found from your location and those you add manually (name and URL).
- Real FFT spectrum in the header (numpy + QPainter).
- Synced `.lrc` lyrics and a lyrics editor.
- Native desktop notification on every track change.
- 🔀 Shuffle and 🔁 repeat.
- Three visual themes (Winamp dark, Terminal green and Light sand).
- Spanish, English, Italian and Arabic interface.
- Media keys and MPRIS integration on Linux.
- Cross-platform: Linux first (Fedora KDE), Windows and macOS.

## Installation

You can also download the package for each platform from the
[Releases](https://github.com/Danix13-glich/PyAmp/releases) page.

If you run from source and a Python package is missing, the app installs it on
first launch into a local environment (`~/.local/share/PyAmp/runtime`) and
restarts itself; you do not need to create the `.venv` or run `pip`. On Linux,
libVLC is still a system library (or use the AppImage, which bundles it). On
Windows, if VLC is not installed, a portable copy is downloaded.

### Fedora (primary platform)

```bash
sudo dnf install vlc python3-vlc python3.12
git clone https://github.com/Danix13-glich/PyAmp.git
cd PyAmp
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

To install it in the applications menu with its icon: open PyAmp and press
**“Install”** in **Settings → General → About**.

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
# 1. Install VLC (for libVLC): https://www.videolan.org/
# 2. Install Python 3.11+: https://www.python.org/ (check "Add to PATH")
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

## Usage

- **File → Open file(s) / Open folder** to play.
- **File → Scan folder into library** to add music to the catalog.
- **View → Songs / Favorites / Online radio** (`Ctrl+1`, `Ctrl+2`, `Ctrl+3`).
- **Settings** (`Ctrl+,`) for language, notifications, theme and shortcuts.

## Notifications

PyAmp shows a native notification every time the current track changes
(play, next, previous or a playlist jump; never when pausing or resuming
the same track). It can be enabled/disabled and its duration changed in
**Settings → General**.

## Development

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

## Contact

For more information or to report a usage issue, write to
**danieldiaz.dx3@gmail.com**.

## License

MIT — see [LICENSE](LICENSE). Copyright © 2026 Danix13-glich.
