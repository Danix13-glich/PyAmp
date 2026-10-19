from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication

from app.core.player import Player
from app.core.settings import (
    MAX_TIMEOUT_MS,
    MIN_TIMEOUT_MS,
    SHORTCUT_DEFAULTS,
    Settings,
    get_settings,
)
from app.library.database import LibraryDatabase
from app.library.models import Album, Track
from app.ui.cover_widget import CoverLabel
from app.ui.library_panel import (
    NO_ALBUM_LABEL,
    NO_ARTIST_LABEL,
    ROLE_TRACK,
    LibraryPanel,
)
from app.ui.lyrics_window import LyricsWindow, find_lrc_path, parse_lrc
from app.ui.settings_dialog import SettingsDialog
from app.ui.songs_table import (
    COLUMN_DURATION,
    COLUMN_FAVORITE,
    COLUMN_NAME,
    SongsTable,
)
from app.ui.spectrum_widget import BAR_COUNT, CHUNK_FRAMES, SpectrumWidget


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def db(tmp_path: Path) -> LibraryDatabase:
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


def test_duet_artist_splits_into_individual_artists(qapp: QApplication, tmp_path: Path) -> None:
    database = LibraryDatabase(tmp_path / "dueto.db")
    try:
        database.upsert_track(
            Track(path=str(tmp_path / "solo.wav"), title="Solo", artist="Bad Bunny", album="Solo")
        )
        database.upsert_track(
            Track(
                path=str(tmp_path / "dueto.wav"),
                title="Dueto",
                artist="Bad Bunny, Becky G",
                album="Dueto",
            )
        )
        panel = LibraryPanel(database)
        panel.refresh()

        bad = _top_item(panel, "Bad Bunny")
        _top_item(panel, "Becky G")  # el colaborador es su propio artista
        top_texts = [
            panel.tree.topLevelItem(index).text(0)
            for index in range(panel.tree.topLevelItemCount())
        ]
        assert "Bad Bunny, Becky G" not in top_texts

        bad.setExpanded(True)
        child_texts = [bad.child(index).text(0) for index in range(bad.childCount())]
        assert "Solo" in child_texts and "Dueto" in child_texts
    finally:
        database.close()


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


# ---------------------------------------------------- vista Canciones
@pytest.fixture()
def songs(qapp: QApplication, db: LibraryDatabase) -> SongsTable:
    widget = SongsTable(db)
    widget.refresh()
    return widget


def test_songs_table_columns_and_rows(songs: SongsTable) -> None:
    model = songs.model
    assert model.columnCount() == 4
    assert model.rowCount() == 3
    assert model.headerData(0, Qt.Orientation.Horizontal) == "Nombre"
    assert model.headerData(3, Qt.Orientation.Horizontal) == "★"
    # La vista usa el proxy (orden + filtro), no el modelo directamente.
    assert songs.view.model() is songs.proxy


def test_songs_table_sorts_duration_by_milliseconds(songs: SongsTable) -> None:
    songs.view.sortByColumn(COLUMN_DURATION, Qt.SortOrder.DescendingOrder)

    # Orden real: 2:00 > 1:30 > «—» (0) — no orden lexicográfico.
    titles = [track.title for track in songs.visible_tracks()]
    assert titles[:2] == ["Dos", "Uno"]
    assert titles[2] == "Suelta"


def test_songs_table_filter_narrows_rows(songs: SongsTable) -> None:
    songs.search("Dos")
    assert songs.proxy.rowCount() == 1
    assert [track.title for track in songs.visible_tracks()] == ["Dos"]

    songs.search("")
    assert songs.proxy.rowCount() == 3


def test_songs_activation_emits_track_with_visible_context(songs: SongsTable) -> None:
    received: list[tuple[Track, list[Track]]] = []
    songs.track_activated.connect(lambda t, c: received.append((t, c)))

    songs.view.activated.emit(songs.proxy.index(0, COLUMN_NAME))

    assert len(received) == 1
    track, context = received[0]
    assert isinstance(track, Track)
    assert context == songs.visible_tracks()
    assert track in context


def test_songs_star_column_emits_favorite_toggled(songs: SongsTable) -> None:
    received: list[Track] = []
    songs.favorite_toggled.connect(received.append)

    songs.view.activated.emit(songs.proxy.index(0, COLUMN_FAVORITE))
    assert len(received) == 1

    # Activar otra columna NO emite el alternado de favorito.
    songs.view.activated.emit(songs.proxy.index(0, COLUMN_NAME))
    assert len(received) == 1


# ---------------------------------------------------- diálogo Ajustes
def test_settings_dialog_reads_settings_and_emits_apply(qapp: QApplication) -> None:
    settings = get_settings()
    original_enabled = settings.notifications_enabled
    dialog = SettingsDialog(
        settings,
        notifier_backend="test-backend",
        version="0.1.0",
        library_stats={"tracks": 3, "artists": 1, "albums": 1},
    )

    assert dialog._spin_timeout.minimum() == MIN_TIMEOUT_MS // 1000  # noqa: SLF001 - tests
    assert dialog._spin_timeout.maximum() == MAX_TIMEOUT_MS // 1000  # noqa: SLF001 - tests
    assert dialog._check_enabled.isChecked() == original_enabled  # noqa: SLF001 - tests

    applied: list[tuple[bool, int]] = []
    tested: list[int] = []
    dialog.apply_settings.connect(lambda enabled, ms: applied.append((enabled, ms)))
    dialog.test_notification.connect(lambda: tested.append(1))

    dialog._button_test.click()  # noqa: SLF001 - tests
    assert tested == [1]

    dialog._check_enabled.setChecked(not original_enabled)  # noqa: SLF001 - tests
    dialog._spin_timeout.setValue(12)  # noqa: SLF001 - tests
    dialog._on_accepted()  # noqa: SLF001 - tests

    assert applied == [(not original_enabled, 12000)]
    # El diálogo NO persiste por sí mismo: eso lo hace la ventana.
    assert settings.notifications_enabled == original_enabled


# ------------------------------------------- atajos personalizables (ajustes)
def test_settings_shortcuts_roundtrip_isolated(tmp_path: Path) -> None:
    settings = Settings(tmp_path / "PyAmp-test.conf")

    assert settings.shortcuts == {}  # sin personalización: vacío

    settings.shortcuts = {"next": "Ctrl+9", "play_pause": "F5"}
    assert settings.shortcuts == {"next": "Ctrl+9", "play_pause": "F5"}

    settings.shortcuts = {}
    assert settings.shortcuts == {}


def test_settings_shortcuts_ignores_corrupt_json(tmp_path: Path) -> None:
    settings = Settings(tmp_path / "PyAmp-test.conf")
    settings.set_value("shortcuts/custom", "{no es json")

    assert settings.shortcuts == {}


def test_settings_dialog_shortcut_edits_match_catalog(qapp: QApplication, tmp_path: Path) -> None:
    dialog = SettingsDialog(
        Settings(tmp_path / "PyAmp-test.conf"),
        notifier_backend="test-backend",
        version="0.1.0",
    )

    assert set(dialog._shortcut_edits) == set(SHORTCUT_DEFAULTS)  # noqa: SLF001 - tests
    edit = dialog._shortcut_edits["next"]  # noqa: SLF001 - tests
    assert edit.keySequence().toString() == SHORTCUT_DEFAULTS["next"]


def test_settings_dialog_collects_only_custom_shortcuts(qapp: QApplication, tmp_path: Path) -> None:
    dialog = SettingsDialog(
        Settings(tmp_path / "PyAmp-test.conf"),
        notifier_backend="test-backend",
        version="0.1.0",
    )

    collected: list[dict[str, str]] = []
    dialog.apply_shortcuts.connect(lambda mapping: collected.append(dict(mapping)))

    dialog._shortcut_edits["next"].setKeySequence(QKeySequence("Ctrl+9"))  # noqa: SLF001 - tests
    dialog._on_accepted()  # noqa: SLF001 - tests

    assert collected == [{"next": "Ctrl+9"}]


# ------------------------------------------------ espectrograma
def test_spectrum_widget_paints_and_computes_levels(qapp: QApplication) -> None:
    widget = SpectrumWidget()
    widget.resize(320, 56)

    assert widget.available is None  # aún no se probó la captura

    # Pintar sin señal ni reproducción no debe fallar (grab fuerza paintEvent).
    pixmap = widget.grab()
    assert not pixmap.isNull()

    # FFT de un chunk sintético → BAR_COUNT niveles normalizados 0..1.
    chunk = np.full(CHUNK_FRAMES, 0.2, dtype=np.float32)
    levels = widget._compute(chunk)  # noqa: SLF001 - tests
    assert levels is not None
    assert levels.shape == (BAR_COUNT,)
    assert float(levels.min()) >= 0.0
    assert float(levels.max()) <= 1.0


def test_spectrum_widget_start_stop_and_shutdown_are_safe(qapp: QApplication) -> None:
    widget = SpectrumWidget()
    widget.set_playing(True)  # intenta parec/pactl; si faltan → reposo
    assert widget.available in (True, False, None)
    widget.set_playing(False)

    widget.shutdown()
    widget.shutdown()  # idempotente (closeEvent puede repetirse en tests)
    assert widget.available is not None  # ya quedó resuelto


def test_spectrum_widget_is_compact_and_blue_bars(qapp: QApplication) -> None:
    widget = SpectrumWidget()
    assert BAR_COUNT == 12
    assert widget.minimumHeight() == 64
    assert widget.width() == 120  # ancho fijo (no colapsa en filas horizontales)


# ------------------------------------------------------------- letras
def test_parse_lrc_extracts_and_sorts_entries() -> None:
    text = "\n".join(
        [
            "[ti:Canción]",
            "[ar:Artista]",
            "[00:12.50]Segunda línea",
            "[00:01]Primera línea",
            "[00:01.5]Otra marca de la misma línea",
            "Sin marca de tiempo",
        ]
    )

    entries = parse_lrc(text)

    assert entries == [
        (1000, "Primera línea"),
        (1500, "Otra marca de la misma línea"),
        (12500, "Segunda línea"),
    ]


def test_find_lrc_path_prefers_sidecar(tmp_path: Path) -> None:
    audio = tmp_path / "tema-sidecar-test.mp3"
    audio.write_bytes(b"")
    assert find_lrc_path(str(audio)) is None

    sidecar = tmp_path / "tema-sidecar-test.lrc"
    sidecar.write_text("[00:01]Hola", encoding="utf-8")
    assert find_lrc_path(str(audio)) == sidecar


def test_lyrics_window_shows_lrc_and_syncs(qapp: QApplication, tmp_path: Path) -> None:
    audio = tmp_path / "tema-sync-test.mp3"
    audio.write_bytes(b"")
    (tmp_path / "tema-sync-test.lrc").write_text(
        "[00:00]Intro\n[00:10]Estrofa\n[01:00]Final\n", encoding="utf-8"
    )
    window = LyricsWindow()

    window.show_track(Track(path=str(audio), title="Tema"))

    assert window.entries == [(0, "Intro"), (10000, "Estrofa"), (60000, "Final")]
    assert window.active_row == -1

    window.sync_position(500)
    assert window.active_row == 0
    window.sync_position(12000)
    assert window.active_row == 1
    window.sync_position(90000)  # tras el final → última línea
    assert window.active_row == 2
    window.sync_position(12000)  # retroceso (seek atrás) también sigue
    assert window.active_row == 1

    window.reset()
    assert window.entries == []


def test_lyrics_window_without_lrc_is_harmless(qapp: QApplication, tmp_path: Path) -> None:
    audio = tmp_path / "tema-sinletra-test.mp3"
    audio.write_bytes(b"")
    window = LyricsWindow()

    window.show_track(Track(path=str(audio), title="Sin letra"))

    assert window.entries == []
    assert window.showing_placeholder  # «Letra no disponible :(» centrado
    window.sync_position(1000)  # sin entradas: no-op sin crash
    assert window.active_row == -1
    window.show_track(None)  # sin pista
    assert window.entries == []
    assert window.showing_placeholder


def test_lyrics_window_hides_placeholder_when_lrc_exists(
    qapp: QApplication, tmp_path: Path
) -> None:
    audio = tmp_path / "tema-conletra-test.mp3"
    audio.write_bytes(b"")
    (tmp_path / "tema-conletra-test.lrc").write_text("[00:05]Hola\n", encoding="utf-8")
    window = LyricsWindow()

    window.show_track(Track(path=str(audio), title="Con letra"))

    assert window.entries == [(5000, "Hola")]
    assert not window.showing_placeholder  # hay letra: la lista se ve, sin aviso


# ------------------------------------------------------- temas (0.1.6)
def test_themes_load_three_including_current() -> None:
    from app.themes import DEFAULT_THEME_ID, get_theme, load_themes

    themes = load_themes()
    assert len(themes) == 3
    assert DEFAULT_THEME_ID in themes

    current = get_theme(DEFAULT_THEME_ID)
    assert current.native  # el look histórico = estilo del sistema
    assert current.qss == ""

    for theme_id in ("verde-terminal", "arena-clara"):
        theme = get_theme(theme_id)
        assert not theme.native
        assert "QMainWindow" in theme.qss
        assert theme.spectrum_hue >= 0


def test_get_theme_unknown_id_falls_back_to_default() -> None:
    from app.themes import DEFAULT_THEME_ID, get_theme

    assert get_theme("no-existe").id == DEFAULT_THEME_ID


# ------------------------------------------- diálogo Ajustes en pestañas
def test_settings_dialog_has_tabs_and_appearance(qapp: QApplication) -> None:
    from PySide6.QtWidgets import QTabWidget

    dialog = SettingsDialog(
        get_settings(),
        notifier_backend="test-backend",
        version="0.1.8",
    )
    tabs = dialog.findChild(QTabWidget)
    assert tabs is not None
    labels = [tabs.tabText(i) for i in range(tabs.count())]
    assert labels == ["General", "Apariencia", "Atajos"]
    # Notificaciones e Información viven dentro de la pestaña General.
    from PySide6.QtWidgets import QGroupBox

    general = tabs.widget(0)
    groups = {box.title() for box in general.findChildren(QGroupBox)}
    assert {"Idioma", "Notificaciones", "Información"} <= groups
    # La combo de temas enumera los 3 temas cargados.
    assert dialog._combo_theme.count() == 3  # noqa: SLF001 - tests


def test_settings_dialog_emits_appearance(qapp: QApplication) -> None:
    dialog = SettingsDialog(
        get_settings(),
        notifier_backend="test-backend",
        version="0.1.6",
    )
    received: list[tuple[str, bool, bool]] = []
    dialog.apply_appearance.connect(lambda t, s, c: received.append((t, s, c)))

    dialog._combo_theme.setCurrentIndex(1)  # noqa: SLF001 - tests
    dialog._check_spectrum.setChecked(False)  # noqa: SLF001 - tests
    dialog._on_accepted()  # noqa: SLF001 - tests

    assert len(received) == 1
    theme_id, spectrum, _cover = received[0]
    assert theme_id == dialog._combo_theme.currentData()  # noqa: SLF001 - tests
    assert spectrum is False


# ------------------------------------------- vista Favoritos (Ctrl+3)
def test_songs_table_favorites_only_mode(songs: SongsTable, db: LibraryDatabase) -> None:
    assert songs.favorites_only is False
    db.toggle_favorite(str(Path(db.path).parent / "dos.wav"))

    songs.set_favorites_only(True)

    assert songs.favorites_only is True
    titles = [track.title for track in songs.visible_tracks()]
    assert titles == ["Dos"]


def test_songs_table_refresh_requested_signal(songs: SongsTable) -> None:
    received: list[int] = []
    songs.refresh_requested.connect(lambda: received.append(1))

    songs._button_refresh.click()  # noqa: SLF001 - tests

    assert received == [1]


def test_settings_library_folders_roundtrip(tmp_path: Path) -> None:
    settings = Settings(tmp_path / "PyAmp-test.conf")

    assert settings.library_folders == []
    settings.library_folders = ["/música/a", "/música/a", " /música/b ", ""]
    assert settings.library_folders == ["/música/a", "/música/b"]
    settings.library_folders = []
    assert settings.library_folders == []


# ------------------------------------------------ letras: salto y editor
def test_lyrics_window_seek_requested_on_double_click(qapp: QApplication, tmp_path: Path) -> None:
    audio = tmp_path / "tema-seekclick-test.mp3"
    audio.write_bytes(b"")
    (tmp_path / "tema-seekclick-test.lrc").write_text(
        "[00:00]Intro\n[00:10]Estrofa\n", encoding="utf-8"
    )
    window = LyricsWindow()
    window.show_track(Track(path=str(audio), title="Tema"))

    received: list[int] = []
    window.seek_requested.connect(received.append)

    window._list.itemActivated.emit(window._list.item(1))  # noqa: SLF001 - tests
    assert received == [10000]

    window._list.itemActivated.emit(window._list.item(0))  # noqa: SLF001 - tests
    assert received == [10000, 0]


def test_lyrics_editor_saves_new_file_with_song_name(
    qapp: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.ui.lyrics_editor as editor_module

    # LYRICS_DIR es una constante de módulo: se inyecta una carpeta temporal
    # (aislado; nunca la biblioteca real de letras del usuario).
    lyrics_dir = tmp_path / "lyrics"
    monkeypatch.setattr(editor_module, "LYRICS_DIR", lyrics_dir)

    audio = tmp_path / "cancion-nueva-test.mp3"
    audio.write_bytes(b"")
    dialog = editor_module.LyricsEditorDialog(Track(path=str(audio), title="Canción nueva"))
    assert dialog.target_path == lyrics_dir / "cancion-nueva-test.lrc"
    assert not dialog.target_path.is_file()  # aún no guardada

    dialog._editor.setPlainText("[00:01]Hola\n[00:05]Adiós")  # noqa: SLF001 - tests
    dialog._on_save()  # noqa: SLF001 - tests

    assert dialog.target_path.is_file()
    text = dialog.target_path.read_text(encoding="utf-8")
    assert "[00:01]Hola" in text and "[00:05]Adiós" in text


def test_lyrics_editor_edits_existing_sidecar(qapp: QApplication, tmp_path: Path) -> None:
    from app.ui.lyrics_editor import LyricsEditorDialog

    audio = tmp_path / "tema-editar-test.mp3"
    audio.write_bytes(b"")
    sidecar = tmp_path / "tema-editar-test.lrc"
    sidecar.write_text("[00:03]Original", encoding="utf-8")

    dialog = LyricsEditorDialog(Track(path=str(audio), title="Tema"))

    assert dialog.target_path == sidecar
    assert "[00:03]Original" in dialog._editor.toPlainText()  # noqa: SLF001 - tests


# ------------------------------------------- espectro: captura y privacidad
def test_spectrum_stop_capture_keeps_availability(qapp: QApplication) -> None:
    widget = SpectrumWidget()
    widget.set_playing(True)
    widget.stop_capture()
    assert widget._process is None  # noqa: SLF001 - tests (parec terminado)
    # Sigue pudiendo relanzarse (set_playing(True) de nuevo).
    widget.set_playing(False)
    widget.set_playing(True)
    widget.shutdown()


def test_spectrum_set_hue_changes_bar_color(qapp: QApplication) -> None:
    widget = SpectrumWidget()
    assert widget._hue == 210  # noqa: SLF001 - tests (azul por defecto)
    widget.set_hue(140)
    assert widget._hue == 140  # noqa: SLF001 - tests
    widget.set_hue(9999)
    assert widget._hue == 359  # noqa: SLF001 - tests (recortado)


def test_spectrum_set_colors_follow_theme(qapp: QApplication) -> None:
    widget = SpectrumWidget()
    assert widget._bg_color.name() == "#181818"  # noqa: SLF001 - tests
    widget.set_spectrum_colors("#e3d7c3", "#bfae90")
    assert widget._bg_color.name() == "#e3d7c3"  # noqa: SLF001 - tests
    assert widget._line_color.name() == "#bfae90"  # noqa: SLF001 - tests
    widget.set_spectrum_colors("no-es-color", "#000000")  # inválido: se ignora
    assert widget._bg_color.name() == "#e3d7c3"  # noqa: SLF001 - tests


def test_format_album_label_hides_placeholder_year() -> None:
    from app.ui.library_panel import format_album_label

    assert format_album_label("Disco", "0000") == "Disco"
    assert format_album_label("Disco", "0") == "Disco"
    assert format_album_label("Disco", None) == "Disco"
    assert format_album_label("Disco", "2020") == "Disco (2020)"
