from __future__ import annotations

from PySide6.QtWidgets import QApplication, QFrame, QLabel

from app.ui.history_window import MEDAL_COLORS, NOT_READY_TEXT, HistoryWindow


def _qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_history_window_shows_placeholder_when_not_ready() -> None:
    _qapp()
    window = HistoryWindow([{"path": "/m/a.mp3", "count": 4, "title": "A", "artist": "B"}])
    texts = [label.text() for label in window.findChildren(QLabel)]
    assert NOT_READY_TEXT in texts
    assert window.findChildren(QFrame, "historyRow") == []


def test_history_window_paints_medals_for_top_three() -> None:
    _qapp()
    entries = [
        {"path": "/m/1.mp3", "count": 9, "title": "Uno", "artist": "A"},
        {"path": "/m/2.mp3", "count": 5, "title": "Dos", "artist": "B"},
        {"path": "/m/3.mp3", "count": 3, "title": "Tres", "artist": "C"},
        {"path": "/m/4.mp3", "count": 1, "title": "Cuatro", "artist": "D"},
    ]
    window = HistoryWindow(entries, ready=True)

    rows = window.findChildren(QFrame, "historyRow")
    assert len(rows) == 4
    styles = [row.styleSheet() for row in rows]
    assert MEDAL_COLORS[0] in styles[0]
    assert MEDAL_COLORS[1] in styles[1]
    assert MEDAL_COLORS[2] in styles[2]
    assert MEDAL_COLORS[0] not in styles[3]


def test_history_window_title_falls_back_to_filename() -> None:
    _qapp()
    window = HistoryWindow(
        [{"path": "/m/mi-tema.mp3", "count": 2, "title": None, "artist": None}], ready=True
    )
    texts = " ".join(label.text() for label in window.findChildren(QLabel))
    assert "mi-tema" in texts
    assert "Artista desconocido" in texts
