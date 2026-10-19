from __future__ import annotations

import os
import platform
from pathlib import Path

APP_NAME = "PyAmp"


def _base_config_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        appdata = os.environ.get("APPDATA")
        return Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    return Path(xdg) if xdg else Path.home() / ".config"


def _base_data_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        local = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        return Path(local) if local else Path.home() / "AppData" / "Local"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support"
    xdg = os.environ.get("XDG_DATA_HOME")
    return Path(xdg) if xdg else Path.home() / ".local" / "share"


CONFIG_DIR: Path = _base_config_dir() / APP_NAME
DATA_DIR: Path = _base_data_dir() / APP_NAME
LOGS_DIR: Path = DATA_DIR / "logs"
COVERS_DIR: Path = DATA_DIR / "covers"
PLAYLISTS_DIR: Path = DATA_DIR / "playlists"
LYRICS_DIR: Path = DATA_DIR / "lyrics"
THEMES_DIR: Path = DATA_DIR / "themes"
DATABASE_FILE: Path = DATA_DIR / "library.db"


def ensure_app_dirs() -> None:
    for directory in (
        CONFIG_DIR,
        DATA_DIR,
        LOGS_DIR,
        COVERS_DIR,
        PLAYLISTS_DIR,
        LYRICS_DIR,
        THEMES_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
