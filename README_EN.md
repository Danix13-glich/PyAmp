<p align="center">
  <img src="assets/logo.svg" alt="PyAmp logo" width="160">
</p>

<h1 align="center">PyAmp</h1>

<p align="center">
  A modern Winamp-inspired music player for Linux, Windows and macOS.<br>
  Local files + online radios, real equalizer, visualizer, synced lyrics and native desktop notifications.
</p>

<p align="center">
  <a href="https://github.com/Danix13-glich/PyAmp/actions/workflows/ci.yml"><img src="https://github.com/Danix13-glich/PyAmp/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/platform-Linux%20%7C%20Windows%20%7C%20macOS-lightgrey" alt="Platforms">
  <img src="https://img.shields.io/github/v/release/Danix13-glich/PyAmp" alt="Release">
</p>

<p align="center">
  <b>Español:</b> <a href="README_ES.md">README_ES.md</a>
</p>

> ⚠️ **Status: Phase 0 (skeleton).** The app opens as an empty window. Features land phase by phase.

## Screenshots

| Main window | Playlist | Equalizer |
| ----------- | -------- | --------- |
| _(coming in Phase 3)_ | _(coming in Phase 3)_ | _(coming in Phase 4)_ |

## Features (roadmap)

- 🎵 Local playback (MP3, FLAC, OGG, M4A, WAV...) powered by libVLC
- 📻 Online radios via [radio-browser.info](https://www.radio-browser.info/) with favorites
- 🎚️ Real 10-band equalizer (VLC `AudioEqualizer`) with presets
- 📊 Real-time FFT visualizer (numpy + QPainter)
- 📝 Synced lyrics (`.lrc` local + [lrclib.net](https://lrclib.net/))
- 🔔 **Native desktop notifications on every track change** (D-Bus on Linux, Toasts on Windows, Notification Center on macOS)
- 🗄️ Music library with SQLite: scan, search, playlists, play history
- 🎨 Light/dark themes with configurable accents; classic `.wsz` skins (later phase)
- ⌨️ Media keys and MPRIS integration on Linux (KDE Plasma)
- 🖥️ Cross-platform: Linux first (Fedora KDE), Windows 10/11, macOS 12+

## Quick install

```bash
# Linux / macOS
curl -fsSL https://raw.githubusercontent.com/Danix13-glich/PyAmp/main/install.sh | bash
```

```powershell
# Windows PowerShell
iwr -useb https://raw.githubusercontent.com/Danix13-glich/PyAmp/main/install.ps1 | iex
```

```bash
# Universal (Python already installed)
git clone https://github.com/Danix13-glich/PyAmp.git
cd PyAmp
python install.py
```

> The universal installer creates a virtualenv, installs dependencies, checks for libVLC, and registers a desktop/menu shortcut. It is idempotent — run it as many times as you want (`--uninstall` to remove).

## Manual installation

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

## Notifications

PyAmp shows a **native** desktop notification every time the current track changes (play, next, previous, or a jump in the playlist — never on pause/resume of the same track):

```
┌─────────────────────────────┐
│  PyAmp                      │  ← app name
│  Song title                 │  ← title (falls back to file name)
│  Artist name                │  ← artist (falls back to "Artista desconocido")
└─────────────────────────────┘
```

- Linux: D-Bus `org.freedesktop.Notifications` via `dbus-next` — integrates with the KDE/GNOME notification center and history, respects *Do Not Disturb*.
- Windows: Windows Toasts (`windows-toasts`).
- macOS: Notification Center (`pync`).
- Fallback: `plyer`. Failures are logged and never interrupt playback.
- Configurable (duration, on/off) in *Settings → Notifications*.

## Development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest                # tests
ruff check src tests main.py
black --check src tests main.py
mypy
python main.py        # run
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full workflow (phases, branches, Conventional Commits, releases).

## Contributing

Contributions are welcome! Read [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md). Open an issue before big changes.

## License

⚠️ **License pending decision.** PyAmp depends on [mutagen](https://mutagen.readthedocs.io/) (GPL-2.0-or-later), libVLC/python-vlc (LGPL-2.1+) and PySide6 (LGPL-3.0). The project license will be chosen before the first public release — see [SECURITY.md](SECURITY.md).
