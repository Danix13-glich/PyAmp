"""Tests de la UI de biblioteca (Fase 3): panel, carátulas y replace_playlist.

Usan ``QApplication`` offscreen (CI define ``QT_QPA_PLATFORM=offscreen``);
el árbol se rellena con un SQLite temporal construido con la misma fachada
que usa la app.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from app.core.player import Player
from app.core.settings import get_settings
from app.library.database import LibraryDatabase
from app.library.models import Album, Track
from app.ui.cover_widget import CoverLabel
from app.ui.library_panel import (
    NO_ALBUM_LABEL,
    NO_ARTIST_LABEL,
    ROLE_TRACK,
    LibraryPanel,
)


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    """QApplication única offscreen para los widgets."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def db(tmp_path: Path) -> LibraryDatabase:
    """Biblioteca: «Alfa» con álbum «Disco» (2 pistas) + 1 pista huérfana."""
    database = LibraryDatabase(tmp_path / "library.db")
    database.upsert_track(
        Track(
            path=str(tmp_path / "uno.wav"),
            title="Uno",
            artist="Alfa",
            album="Disco",
            year="2024",
            duration_ms=90_000,
            track_no=1,
        )
    )
    database.upsert_track(
        Track(
            path=str(tmp_path / "dos.wav"),
            title="Dos",
            artist="Alfa",
            album="Disco",
            duration_ms=120_000,
            track_no=2,
        )
    )
    database.upsert_track(Track(path=str(tmp_path / "suelta.wav"), title="Suelta"))
    yield database
    database.close()


@pytest.fixture()
def panel(qapp: QApplication, db: LibraryDatabase) -> LibraryPanel:
    widget = LibraryPanel(db)
    widget.refresh()
    return widget


def _top_item(panel: LibraryPanel, text: str):
    tree = panel.tree
    for index in range(tree.topLevelItemCount()):
        item = tree.topLevelItem(index)
        if item is not None and item.text(0) == text:
            return item
    raise AssertionError(f"nodo superior no encontrado: {text!r}")


def _child_item(parent, text: str):
    for index in range(parent.childCount()):
        child = parent.child(index)
        if child is not None and child.text(0) == text:
            return child
    raise AssertionError(f"hijo no encontrado: {text!r}")


# ------------------------------------------------------------------- árbol
def test_refresh_populates_artists_and_bucket(panel: LibraryPanel) -> None:
    _top_item(panel, "Alfa")
    _top_item(panel, NO_ARTIST_LABEL)
    assert "3 pistas" in panel._stats_label.text()  # noqa: SLF001 - tests


def test_artist_is_lazy_until_expanded(panel: LibraryPanel) -> None:
    artist = _top_item(panel, "Alfa")
    # Antes de expandir: solo el marcador perezoso.
    assert artist.childCount() == 1
    dummy = artist.child(0)
    assert dummy is not None and dummy.isDisabled()

    artist.setExpanded(True)

    # Tras expandir: álbum + bucket «(Sin álbum)» no aparece (todo con álbum).
    _child_item(artist, "Disco (2024)")
    texts = [artist.child(i).text(0) for i in range(artist.childCount())]
    assert NO_ALBUM_LABEL not in texts


def test_album_expand_lists_tracks_with_duration(panel: LibraryPanel) -> None:
    artist = _top_item(panel, "Alfa")
    artist.setExpanded(True)
    album = _child_item(artist, "Disco (2024)")
    assert album.childCount() == 1  # perezoso

    album.setExpanded(True)

    first = album.child(0)
    second = album.child(1)
    assert first is not None and second is not None
    assert first.text(0) == "1. Uno"
    assert first.text(1) == "1:30"
    assert second.text(0) == "2. Dos"
    assert second.text(1) == "2:00"
    track = first.data(0, ROLE_TRACK)
    assert isinstance(track, Track) and track.title == "Uno"


def test_artistless_bucket_shows_orphan_tracks(panel: LibraryPanel) -> None:
    bucket = _top_item(panel, NO_ARTIST_LABEL)
    bucket.setExpanded(True)
    no_album = _child_item(bucket, NO_ALBUM_LABEL)
    no_album.setExpanded(True)
    assert no_album.childCount() == 1
    assert no_album.child(0).text(0) == "Suelta"


# ----------------------------------------------------------------- búsqueda
def test_search_shows_flat_results(panel: LibraryPanel) -> None:
    panel.search("Dos")
    tree = panel.tree
    assert tree.topLevelItemCount() == 1
    item = tree.topLevelItem(0)
    assert item is not None
    assert item.text(0) == "Dos — Alfa"
    assert isinstance(item.data(0, ROLE_TRACK), Track)

    panel.search("")  # limpiar vuelve al árbol
    assert tree.topLevelItemCount() == 2


# ------------------------------------------------------------------ acciones
def test_track_activation_emits_album_context(panel: LibraryPanel, db: LibraryDatabase) -> None:
    artist = _top_item(panel, "Alfa")
    artist.setExpanded(True)
    album = _child_item(artist, "Disco (2024)")
    album.setExpanded(True)
    first = album.child(0)

    received: list[tuple[Track, list[Track]]] = []
    panel.track_activated.connect(lambda t, c: received.append((t, c)))

    panel.tree.itemActivated.emit(first, 0)

    assert len(received) == 1
    track, context = received[0]
    assert track.title == "Uno"
    assert [t.title for t in context] == ["Uno", "Dos"]


def test_activating_non_track_emits_nothing(panel: LibraryPanel) -> None:
    artist = _top_item(panel, "Alfa")
    received: list[tuple[Track, list[Track]]] = []
    panel.track_activated.connect(lambda t, c: received.append((t, c)))

    panel.tree.itemActivated.emit(artist, 0)

    assert received == []


def test_selection_emits_track_album_and_none(panel: LibraryPanel) -> None:
    selections: list[object] = []
    panel.selection_changed.connect(selections.append)

    artist = _top_item(panel, "Alfa")
    artist.setExpanded(True)
    album = _child_item(artist, "Disco (2024)")

    album.setSelected(True)
    assert isinstance(selections[-1], Album)
    assert selections[-1].title == "Disco"  # type: ignore[union-attr]

    panel.tree.clearSelection()  # selección simple: como en el uso real
    album.setExpanded(True)
    track_item = album.child(0)
    track_item.setSelected(True)
    assert isinstance(selections[-1], Track)
    assert selections[-1].title == "Uno"  # type: ignore[union-attr]

    panel.tree.clearSelection()
    assert selections[-1] is None


# ------------------------------------------------------------------ carátula
def test_cover_label_placeholder_and_load(qapp: QApplication, tmp_path: Path) -> None:
    label = CoverLabel()
    assert label.width() == 64 and label.height() == 64
    assert label.pixmap().isNull()  # placeholder = texto, sin pixmap
    assert label.text() == "♪"

    from PySide6.QtGui import QPixmap

    image = QPixmap(32, 32)
    image.fill()
    cover_path = tmp_path / "cover.png"
    assert image.save(str(cover_path))

    label.set_cover(cover_path)
    assert label.text() == ""
    assert not label.pixmap().isNull()

    label.set_cover(None)
    assert label.text() == "♪"
    label.set_cover(tmp_path / "no-existe.png")  # ilegible → placeholder
    assert label.text() == "♪"


# ---------------------------------------------------------- replace_playlist
def test_replace_playlist_swaps_context(qapp: QApplication) -> None:
    player = Player(settings=get_settings())
    try:
        tracks = [Track(path=f"/m/{index}.wav") for index in range(1, 4)]

        result = player.replace_playlist(tracks, 1)

        assert isinstance(result, bool)
        assert len(player.playlist) == 3
        assert player.playlist.current_index == 1
        current = player.playlist.current()
        assert current is not None and current.path == "/m/2.wav"

        # Índice fuera de rango → recortado al último.
        player.replace_playlist(tracks, 99)
        assert player.playlist.current_index == 2

        # Lista vacía → False (y no toca la playlist anterior).
        assert player.replace_playlist([]) is False
        assert len(player.playlist) == 3
    finally:
        player.shutdown()
