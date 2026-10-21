from __future__ import annotations

import contextlib
import os
import platform
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.i18n import tr

APP_NAME = "PyAmp"
APP_ID = "pyamp"

ProgressCallback = Callable[[int, str], None]


@dataclass
class InstallResult:

    ok: bool
    message: str = ""
    installed_path: str = ""
    installer_path: str = ""
    installer_removable: bool = False


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def distributable_path() -> Path | None:
    # Solo un binario empaquetado se puede instalar como aplicación.
    if is_frozen():
        try:
            return Path(sys.executable).resolve()
        except OSError:
            return None
    return None


def _home() -> Path:
    return Path.home()


def source_root() -> Path:
    # src/app/utils/installer.py → raíz del repositorio.
    return Path(__file__).resolve().parents[3]


def _asset_path() -> Path | None:
    base = getattr(sys, "_MEIPASS", None)
    candidates = []
    if base:
        candidates.append(Path(str(base)) / "assets" / "logo.svg")
    candidates.append(source_root() / "assets" / "logo.svg")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _copy_with_progress(
    source: Path, destination: Path, start: int, end: int, report: ProgressCallback
) -> None:
    total = source.stat().st_size or 1
    copied = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as origin, destination.open("wb") as target:
        while True:
            chunk = origin.read(1024 * 1024)
            if not chunk:
                break
            target.write(chunk)
            copied += len(chunk)
            report(start + int((end - start) * copied / total), tr("Copiando archivos…"))


def _write_desktop_entry(path: Path, exec_line: str, icon: str, workdir: str) -> None:
    content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Version=1.0\n"
        f"Name={APP_NAME}\n"
        "GenericName=Reproductor de música\n"
        "Comment=Escucha música local y radios online\n"
        f"Exec={exec_line}\n"
        f"Path={workdir}\n"
        f"Icon={icon}\n"
        "Terminal=false\n"
        "Categories=AudioVideo;Audio;Player;\n"
        "Keywords=musica;música;player;winamp;radio;\n"
        "StartupNotify=true\n"
        f"StartupWMClass={APP_NAME}\n"
    )
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _install_linux(report: ProgressCallback) -> InstallResult:
    home = _home()
    apps_dir = home / ".local" / "share" / "applications"
    icons_dir = home / ".local" / "share" / "icons" / "hicolor" / "scalable" / "apps"
    apps_dir.mkdir(parents=True, exist_ok=True)
    icons_dir.mkdir(parents=True, exist_ok=True)

    report(5, tr("Preparando la instalación…"))
    icon_value = APP_ID
    asset = _asset_path()
    if asset is not None:
        icon_file = icons_dir / f"{APP_ID}.svg"
        with contextlib.suppress(OSError):
            shutil.copyfile(asset, icon_file)
            icon_value = str(icon_file)

    report(15, tr("Creando el acceso directo…"))
    exe = distributable_path()
    if exe is not None:
        bin_dir = home / ".local" / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        suffix = exe.suffix or ".AppImage"
        target = bin_dir / f"{APP_ID}{suffix}"
        _copy_with_progress(exe, target, 20, 85, report)
        target.chmod(0o755)
        exec_line = f'"{target}"'
        installed = target
    else:
        root = source_root()
        exec_line = f'"{sys.executable}" "{root / "main.py"}"'
        installed = root

    _write_desktop_entry(apps_dir / f"{APP_ID}.desktop", exec_line, icon_value, str(source_root()))
    report(95, tr("Actualizando el menú de aplicaciones…"))
    for command in ("update-desktop-database", "gtk-update-icon-cache", "kbuildsycoca6"):
        if shutil.which(command):
            args = [command]
            if command == "update-desktop-database":
                args.append(str(apps_dir))
            elif command == "gtk-update-icon-cache":
                args += ["-f", "-t", str(icons_dir.parent.parent)]
            else:
                args.append("--noincremental")
            with contextlib.suppress(OSError, subprocess.SubprocessError):
                subprocess.run(args, check=False, capture_output=True, timeout=20)
    report(100, tr("Instalación completada."))
    return InstallResult(
        ok=True,
        message=tr("PyAmp se ha instalado correctamente."),
        installed_path=str(installed),
        installer_path=str(exe) if exe is not None else "",
        installer_removable=exe is not None,
    )


def _install_windows(report: ProgressCallback) -> InstallResult:
    local = os.environ.get("LOCALAPPDATA")
    appdata = os.environ.get("APPDATA")
    if not local:
        return InstallResult(ok=False, message=tr("No se encontró la carpeta de aplicaciones."))
    target_dir = Path(local) / "Programs" / APP_NAME
    target_dir.mkdir(parents=True, exist_ok=True)

    report(10, tr("Copiando archivos…"))
    exe = distributable_path()
    if exe is not None:
        target = target_dir / exe.name
        _copy_with_progress(exe, target, 10, 80, report)
    else:
        target = target_dir / f"{APP_NAME}.bat"
        root = source_root()
        target.write_text(
            f'@echo off\r\n"{sys.executable}" "{root / "main.py"}"\r\n', encoding="utf-8"
        )
        exe = None

    report(85, tr("Creando el acceso directo…"))
    if appdata:
        shortcut = (
            Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / f"{APP_NAME}.lnk"
        )
        script = (
            "$ws = New-Object -ComObject WScript.Shell; "
            f"$s = $ws.CreateShortcut('{shortcut}'); "
            f"$s.TargetPath = '{target}'; "
            f"$s.WorkingDirectory = '{target.parent}'; "
            f"$s.IconLocation = '{target}'; "
            "$s.Save()"
        )
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                check=False,
                capture_output=True,
                timeout=30,
            )

    report(100, tr("Instalación completada."))
    return InstallResult(
        ok=True,
        message=tr("PyAmp se ha instalado correctamente."),
        installed_path=str(target),
        installer_path=str(exe) if exe is not None else "",
        installer_removable=exe is not None,
    )


def _mac_bundle(executable: Path) -> Path | None:
    for parent in executable.parents:
        if parent.suffix == ".app":
            return parent
    return None


def _install_macos(report: ProgressCallback) -> InstallResult:
    exe = distributable_path()
    bundle = _mac_bundle(exe) if exe is not None else None
    if bundle is None:
        return InstallResult(
            ok=False,
            message=tr("La instalación automática solo está disponible en la app empaquetada."),
        )
    report(10, tr("Copiando la aplicación…"))
    applications = _home() / "Applications"
    applications.mkdir(parents=True, exist_ok=True)
    target = applications / bundle.name
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(bundle, target)
    report(100, tr("Instalación completada."))
    return InstallResult(
        ok=True,
        message=tr("PyAmp se ha instalado correctamente."),
        installed_path=str(target),
        installer_path="",
        installer_removable=False,
    )


def install_application(report: ProgressCallback | None = None) -> InstallResult:
    callback = report or (lambda _value, _text: None)
    system = platform.system()
    if system == "Linux":
        return _install_linux(callback)
    if system == "Windows":
        return _install_windows(callback)
    if system == "Darwin":
        return _install_macos(callback)
    return InstallResult(ok=False, message=tr("Sistema operativo no compatible."))


def remove_installer(path: str) -> bool:
    if not path:
        return False
    try:
        Path(path).unlink()
    except OSError:
        return False
    return True


class InstallWorker(QThread):

    progress = Signal(int, str)
    finished_ok = Signal(object)
    failed = Signal(str)

    def run(self) -> None:
        try:
            result = install_application(lambda value, text: self.progress.emit(value, text))
        except Exception as exc:  # noqa: BLE001 - la instalación nunca debe tumbar la UI
            self.failed.emit(str(exc))
            return
        if result.ok:
            self.finished_ok.emit(result)
        else:
            self.failed.emit(result.message)
