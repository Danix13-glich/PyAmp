# Runtime hook de PyInstaller: localiza las bibliotecas y plugins de VLC.
# En Linux se usan los del sistema; en Windows/macOS se buscan junto al
# ejecutable (los añade el flujo de empaquetado).
import os
import sys
from pathlib import Path


def _bundle_dir() -> Path | None:
    base = getattr(sys, "_MEIPASS", None)
    return Path(str(base)) if base else None


def _setup_plugins(root: Path | None) -> None:
    if os.environ.get("VLC_PLUGIN_PATH"):
        return
    candidates = []
    if root is not None:
        candidates += [root / "vlc" / "plugins", root / "plugins"]
    if sys.platform.startswith("linux"):
        candidates += [
            Path("/usr/lib64/vlc/plugins"),
            Path("/usr/lib/x86_64-linux-gnu/vlc/plugins"),
            Path("/usr/lib/vlc/plugins"),
        ]
    elif sys.platform == "darwin" and root is not None:
        candidates.append(root / "lib" / "vlc" / "plugins")
    for candidate in candidates:
        if candidate.is_dir():
            os.environ["VLC_PLUGIN_PATH"] = str(candidate)
            return


def _setup_library(root: Path | None) -> None:
    if root is None or os.environ.get("PYTHON_VLC_LIB_PATH"):
        return
    if sys.platform.startswith("win"):
        candidate = root / "libvlc.dll"
    elif sys.platform == "darwin":
        candidate = root / "lib" / "libvlc.dylib"
    else:
        return
    if candidate.is_file():
        os.environ["PYTHON_VLC_LIB_PATH"] = str(candidate)


_root = _bundle_dir()
_setup_library(_root)
_setup_plugins(_root)
