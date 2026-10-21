from __future__ import annotations

import sys
from pathlib import Path

import pytest

from app.utils import deps


def test_missing_modules_is_empty_in_dev_environment() -> None:
    assert deps.missing_modules() == []


def test_ensure_dependencies_does_nothing_when_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(deps, "missing_modules", lambda: ["PySide6"])
    deps.ensure_dependencies(Path("main.py"))


def test_ensure_dependencies_only_checks_vlc_when_all_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[bool] = []
    monkeypatch.setattr(deps, "missing_modules", lambda: [])
    monkeypatch.setattr(deps, "_ensure_windows_vlc", lambda: called.append(True))
    deps.ensure_dependencies(Path("main.py"))
    assert called == [True]


@pytest.mark.skipif(sys.platform != "linux", reason="ruta XDG solo en Linux")
def test_data_dir_uses_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert deps.venv_dir() == tmp_path / "PyAmp" / "runtime"


def test_requirements_file_exists_in_source_tree() -> None:
    assert deps.requirements_file() is not None
