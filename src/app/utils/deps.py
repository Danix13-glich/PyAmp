from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.request import urlopen

#: Versión de VLC que se descarga en Windows si no hay ninguna instalada.
VLC_WINDOWS_URL = "https://download.videolan.org/pub/videolan/vlc/3.0.21/win64/vlc-3.0.21-win64.zip"

#: (módulo importable, paquete de pip) que necesita la aplicación.
_BASE_REQUIREMENTS = (
    ("PySide6", "PySide6"),
    ("vlc", "python-vlc"),
    ("mutagen", "mutagen"),
    ("numpy", "numpy"),
    ("requests", "requests"),
)


def _data_dir() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        return (Path(base) if base else Path.home() / "AppData" / "Local") / "PyAmp"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "PyAmp"
    base = os.environ.get("XDG_DATA_HOME")
    return (Path(base) if base else Path.home() / ".local" / "share") / "PyAmp"


def requirements() -> list[tuple[str, str]]:
    items = list(_BASE_REQUIREMENTS)
    if sys.platform.startswith("linux"):
        items.append(("dbus_next", "dbus-next"))
    elif sys.platform == "win32":
        items.extend((("plyer", "plyer"), ("windows_toasts", "windows-toasts")))
    elif sys.platform == "darwin":
        items.extend((("plyer", "plyer"), ("pync", "pync")))
    return items


def missing_modules() -> list[str]:
    return [
        module for module, _package in requirements() if importlib.util.find_spec(module) is None
    ]


def requirements_file() -> Path | None:
    candidate = Path(__file__).resolve().parents[3] / "requirements.txt"
    return candidate if candidate.is_file() else None


def venv_dir() -> Path:
    return _data_dir() / "runtime"


def venv_python() -> Path:
    if sys.platform == "win32":
        return venv_dir() / "Scripts" / "python.exe"
    return venv_dir() / "bin" / "python"


def _install_command(python: str, extra: list[str] | None = None) -> list[str]:
    command = [python, "-m", "pip", "install", "--disable-pip-version-check"]
    if extra:
        command.extend(extra)
    source = requirements_file()
    if source is not None:
        command.extend(["-r", str(source)])
    else:
        command.extend(package for _module, package in requirements())
    return command


def _run(command: list[str]) -> bool:
    print("PyAmp: instalando dependencias que faltan…", flush=True)
    print("  " + " ".join(command), flush=True)
    try:
        return subprocess.run(command, check=False).returncode == 0
    except OSError as exc:
        print(f"PyAmp: no se pudo ejecutar pip ({exc})", flush=True)
        return False


def _ensure_windows_vlc() -> None:
    # En Windows el paquete python-vlc no incluye libVLC: si no hay VLC
    # instalado se descarga una copia portátil junto a los datos de PyAmp.
    if sys.platform != "win32" or getattr(sys, "frozen", False):
        return
    if os.environ.get("PYTHON_VLC_LIB_PATH"):
        return
    installed = [
        Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "VideoLAN" / "VLC",
        Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "VideoLAN" / "VLC",
    ]
    if any((folder / "libvlc.dll").is_file() for folder in installed):
        return
    target = _data_dir() / "vlc"
    library = target / "libvlc.dll"
    if not library.is_file():
        archive = _data_dir() / "vlc.zip"
        try:
            _data_dir().mkdir(parents=True, exist_ok=True)
            print("PyAmp: descargando VLC para el análisis y la reproducción…", flush=True)
            with urlopen(VLC_WINDOWS_URL, timeout=120) as response:
                archive.write_bytes(response.read())
            with zipfile.ZipFile(archive) as bundle:
                root = next((n for n in bundle.namelist() if n.endswith("/libvlc.dll")), "")
                prefix = root[: -len("libvlc.dll")]
                for name in bundle.namelist():
                    if not name.startswith(prefix) or name.endswith("/"):
                        continue
                    relative = name[len(prefix) :]
                    destination = target / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.open(name) as source, destination.open("wb") as output:
                        output.write(source.read())
            archive.unlink(missing_ok=True)
        except Exception as exc:  # noqa: BLE001 - sin red o sin permisos
            print(f"PyAmp: no se pudo descargar VLC ({exc})", flush=True)
            return
    if library.is_file():
        os.environ.setdefault("PYTHON_VLC_LIB_PATH", str(library))
        plugins = target / "plugins"
        if plugins.is_dir():
            os.environ.setdefault("VLC_PLUGIN_PATH", str(plugins))


def ensure_dependencies(script: Path) -> None:
    # Se ejecuta ANTES de importar PySide6/vlc: si faltan paquetes se
    # instalan en un entorno propio (o con pip --user) y se reinicia la app.
    if getattr(sys, "frozen", False):
        return
    _ensure_windows_vlc()
    missing = missing_modules()
    if missing:
        if os.environ.get("PYAMP_BOOTSTRAP") == "1":
            print("PyAmp: siguen faltando dependencias: " + ", ".join(missing), flush=True)
            return
        os.environ["PYAMP_BOOTSTRAP"] = "1"
        print("PyAmp: faltan dependencias: " + ", ".join(missing), flush=True)
        inside_venv = sys.prefix != sys.base_prefix
        if inside_venv:
            _run(_install_command(sys.executable))
            return
        python = venv_python()
        if not python.is_file():
            print("PyAmp: creando entorno local en " + str(venv_dir()), flush=True)
            subprocess.run([sys.executable, "-m", "venv", str(venv_dir())], check=False)
        if python.is_file():
            if _run(_install_command(str(python))):
                print("PyAmp: reiniciando con las dependencias instaladas…", flush=True)
                os.execv(
                    str(python),
                    [str(python), str(script), *sys.argv[1:]],
                )
            else:
                print("PyAmp: la instalación automática falló.", flush=True)
        # Último recurso en distribuciones que bloquean pip del sistema.
        if _run(_install_command(sys.executable, ["--user", "--break-system-packages"])):
            import site

            user_site = site.getusersitepackages()
            if user_site not in sys.path:
                sys.path.append(user_site)
