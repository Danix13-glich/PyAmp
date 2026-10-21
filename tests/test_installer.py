from __future__ import annotations

import sys
from pathlib import Path

import pytest

from app.utils import installer
from app.utils.installer import InstallResult


def _fake_executable(tmp_path: Path, name: str = "pyamp_0.2.1-beta14.AppImage") -> Path:
    exe = tmp_path / "descargas" / name
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_bytes(b"BIN" * 1024)
    return exe


def test_install_linux_appimage_copies_and_creates_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(installer.platform, "system", lambda: "Linux")
    monkeypatch.setattr(installer, "_home", lambda: tmp_path)
    monkeypatch.setattr(installer, "_asset_path", lambda: None)
    monkeypatch.setattr(installer.shutil, "which", lambda _name: None)
    exe = _fake_executable(tmp_path)
    monkeypatch.setattr(installer, "distributable_path", lambda: exe)

    progress: list[tuple[int, str]] = []
    result = installer.install_application(lambda value, text: progress.append((value, text)))

    assert result.ok is True
    target = tmp_path / ".local" / "bin" / "pyamp.AppImage"
    assert target.is_file()
    assert target.read_bytes() == exe.read_bytes()
    if sys.platform != "win32":
        # Windows no conserva los bits de ejecución al copiar.
        assert target.stat().st_mode & 0o111

    desktop = tmp_path / ".local" / "share" / "applications" / "pyamp.desktop"
    content = desktop.read_text(encoding="utf-8")
    assert f'Exec="{target}"' in content
    assert "StartupWMClass=PyAmp" in content

    assert result.installer_path == str(exe)
    assert result.installer_removable is True
    assert progress[-1][0] == 100


def test_install_windows_copies_exe_and_creates_shortcut(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(installer.platform, "system", lambda: "Windows")
    local = tmp_path / "LocalAppData"
    roaming = tmp_path / "AppData"
    local.mkdir()
    roaming.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("APPDATA", str(roaming))

    exe = _fake_executable(tmp_path, "pyamp_0.2.1-beta14.exe")
    monkeypatch.setattr(installer, "distributable_path", lambda: exe)
    calls: list[list[str]] = []
    monkeypatch.setattr(installer.subprocess, "run", lambda args, **kwargs: calls.append(args))

    result = installer.install_application()

    assert result.ok is True
    target = local / "Programs" / "PyAmp" / exe.name
    assert target.is_file()
    assert target.read_bytes() == exe.read_bytes()
    assert calls and calls[0][0] == "powershell"
    assert "PyAmp.lnk" in calls[0][-1]
    assert result.installer_path == str(exe)
    assert result.installer_removable is True


def test_install_windows_without_appdata_still_copies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(installer.platform, "system", lambda: "Windows")
    local = tmp_path / "LocalAppData"
    local.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.delenv("APPDATA", raising=False)

    exe = _fake_executable(tmp_path, "pyamp_0.2.1-beta14.exe")
    monkeypatch.setattr(installer, "distributable_path", lambda: exe)
    monkeypatch.setattr(installer.subprocess, "run", lambda args, **kwargs: None)

    result = installer.install_application()

    assert result.ok is True
    assert (local / "Programs" / "PyAmp" / exe.name).is_file()


def test_install_macos_copies_app_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(installer.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(installer, "_home", lambda: tmp_path)

    exe = tmp_path / "PyAmp.app" / "Contents" / "MacOS" / "pyamp"
    exe.parent.mkdir(parents=True)
    exe.write_text("binario", encoding="utf-8")
    monkeypatch.setattr(installer, "distributable_path", lambda: exe)

    result = installer.install_application()

    assert result.ok is True
    target = tmp_path / "Applications" / "PyAmp.app" / "Contents" / "MacOS" / "pyamp"
    assert target.is_file()
    assert result.installer_removable is False


def test_install_macos_from_source_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(installer.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(installer, "_home", lambda: tmp_path)
    monkeypatch.setattr(installer, "distributable_path", lambda: None)

    result = installer.install_application()

    assert result.ok is False
    assert result.message


def test_install_unsupported_operating_system(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(installer.platform, "system", lambda: "Plan9")
    result = installer.install_application()
    assert result.ok is False


def test_remove_installer_handles_missing_path(tmp_path: Path) -> None:
    assert installer.remove_installer("") is False
    assert installer.remove_installer(str(tmp_path / "no-existe.AppImage")) is False


def test_install_dialog_holds_ninety_percent(qapp: object, qtbot: object) -> None:
    from app.ui.install_dialog import InstallDialog

    dialog = InstallDialog()
    dialog._on_progress(50, "Copiando")  # noqa: SLF001 - tests
    assert dialog._bar.value() == 50  # noqa: SLF001

    dialog._on_progress(100, "Listo")  # noqa: SLF001
    assert dialog._bar.value() == 90  # noqa: SLF001
    result = InstallResult(ok=True, message="ok")
    dialog._on_ok(result)  # noqa: SLF001
    assert dialog.install_result is None  # aún no ha pasado el segundo

    qtbot.wait(1100)  # type: ignore[attr-defined]
    assert dialog.install_result is result
