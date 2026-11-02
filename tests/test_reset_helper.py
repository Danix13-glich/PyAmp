from __future__ import annotations

import sys

import pytest

from app.notifications import reset_helper


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="solo Linux")
def test_spawn_reset_notification_relanza_la_appimage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    class FakePopen:
        def __init__(self, command: list[str], **kwargs: object) -> None:
            calls.append((command, kwargs))

    monkeypatch.setenv("APPIMAGE", "/opt/PyAmp.AppImage")
    monkeypatch.setattr(reset_helper.subprocess, "Popen", FakePopen)

    assert reset_helper.spawn_reset_notification("Título", "Cuerpo", "Abrir PyAmp")
    assert calls
    command, kwargs = calls[0]
    assert command[:2] == ["/opt/PyAmp.AppImage", "--notify-reset-helper"]
    assert command[-2:] == ["--reset-action", "Abrir PyAmp"]
    assert kwargs["start_new_session"] is True
