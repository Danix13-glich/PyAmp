"""Gestor de temas de PyAmp: JSON de colores + QSS generado.

Cada tema es un archivo JSON en ``data/`` con:

* ``name``: nombre visible (Ver → Temas y Ajustes → Apariencia).
* ``native``: ``true`` = no se aplica QSS global y la app conserva el
  estilo del sistema (el look de las Fases 0–5); ``false`` = se genera
  un QSS completo a partir de la paleta del JSON.
* ``spectrum_hue``: tono HSV de las barras del espectro.
* ``colors``: paleta (cabecera + app) usada por el QSS y por los
  widgets de la cabecera.

El gestor **nunca lanza**: un JSON ausente o roto se ignora con log y,
si faltara el tema por defecto, se reconstruye el look histórico
(«Winamp oscuro») desde :data:`_FALLBACK_COLORS`, de modo que un tema
mal escrito no puede tumbar la app.
"""

from __future__ import annotations

import json
import logging
import string
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

#: Carpeta con los JSON de temas.
THEMES_DIR = Path(__file__).resolve().parent / "data"

#: Tema que reproduce el look histórico (UI de las Fases 0–5).
DEFAULT_THEME_ID = "winamp-oscuro"

#: Paleta mínima: reserva para colores ausentes y para el tema de
#: emergencia si el JSON por defecto desaparece.
_FALLBACK_COLORS: dict[str, str] = {
    # cabecera (mismos valores en hardcode en la Fase 5)
    "header_bg": "#17171b",
    "header_title": "#f2f2f7",
    "header_label": "#9e9ea6",
    "header_format": "#7e7e88",
    "header_time": "#e8e8ee",
    "text_muted": "#9e9ea6",
    # espectro (mismos valores en hardcode en la Fase 4)
    "spectrum_bg": "#181818",
    "spectrum_line": "#464646",
    # iconos de los botones de transporte (contraste con el fondo)
    "icon": "#e8e8ee",
    # app (solo se usan si el tema no es «native»)
    "window_bg": "#17171b",
    "window_text": "#e8e8ee",
    "surface_bg": "#1f1f24",
    "surface_alt": "#26262c",
    "border": "#3a3a42",
    "accent": "#3d7bd9",
    "accent_text": "#ffffff",
    "button_bg": "#26262c",
    "button_hover": "#33333b",
    "button_border": "#3a3a42",
    "slider_groove": "#3a3a42",
    "slider_handle": "#e8e8ee",
}

#: Plantilla de QSS global para los temas no «native». Se usa
#: ``string.Template`` ($var) porque el QSS está lleno de llaves.
_QSS_TEMPLATE = string.Template("""
QMainWindow, QDialog { background-color: $window_bg; color: $window_text; }
QWidget { color: $window_text; }
QMenuBar { background-color: $surface_alt; color: $window_text; border-bottom: 1px solid $border; }
QMenuBar::item:selected { background-color: $button_hover; }
QMenu { background-color: $surface_bg; color: $window_text; border: 1px solid $border; }
QMenu::item { padding: 4px 24px 4px 12px; }
QMenu::item:selected { background-color: $accent; color: $accent_text; }
QMenu::separator { background-color: $border; height: 1px; }
QToolButton { background-color: $button_bg; color: $window_text; border: 1px solid $button_border; border-radius: 4px; padding: 3px 8px; }
QToolButton:hover { background-color: $button_hover; }
QToolButton:checked { background-color: $accent; color: $accent_text; border-color: $accent; }
QToolButton::menu-indicator { image: none; }
QSlider::groove:horizontal { height: 4px; background-color: $slider_groove; border-radius: 2px; }
QSlider::handle:horizontal { background-color: $slider_handle; width: 12px; margin: -5px 0; border-radius: 6px; }
QTableView, QTreeWidget, QListWidget { background-color: $surface_bg; alternate-background-color: $surface_alt; color: $window_text; border: 1px solid $border; gridline-color: $border; }
QTableView::item:selected, QTreeWidget::item:selected { background-color: $accent; color: $accent_text; }
QHeaderView::section { background-color: $surface_alt; color: $text_muted; border: none; border-bottom: 1px solid $border; padding: 4px; }
QLineEdit, QSpinBox, QComboBox, QKeySequenceEdit { background-color: $surface_bg; color: $window_text; border: 1px solid $border; border-radius: 4px; padding: 2px 6px; selection-background-color: $accent; selection-color: $accent_text; }
QCheckBox { color: $window_text; spacing: 6px; }
QScrollBar:vertical { background-color: $window_bg; width: 12px; }
QScrollBar::handle:vertical { background-color: $slider_groove; border-radius: 4px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; width: 0; }
QScrollBar:horizontal { background-color: $window_bg; height: 12px; }
QScrollBar::handle:horizontal { background-color: $slider_groove; border-radius: 4px; min-width: 24px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { height: 0; width: 0; }
QTabWidget::pane { border: 1px solid $border; border-radius: 4px; top: -1px; }
QTabBar::tab { background-color: $surface_alt; color: $text_muted; padding: 6px 14px; border: 1px solid $border; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; }
QTabBar::tab:selected { background-color: $surface_bg; color: $window_text; }
QGroupBox { border: 1px solid $border; border-radius: 6px; margin-top: 10px; padding-top: 8px; color: $window_text; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; color: $text_muted; }
QStatusBar { background-color: $surface_alt; color: $text_muted; }
QToolTip { background-color: $surface_bg; color: $window_text; border: 1px solid $border; padding: 4px; }
""")


@dataclass(frozen=True)
class Theme:
    """Un tema cargado desde su JSON (inmutable)."""

    id: str
    name: str
    native: bool
    spectrum_hue: int
    colors: dict[str, str]

    def color(self, key: str) -> str:
        """Color de la paleta (reserva al look histórico si falta)."""
        return self.colors.get(key, _FALLBACK_COLORS.get(key, "#000000"))

    @property
    def qss(self) -> str:
        """QSS global del tema (vacío si es «native»: conserva el sistema)."""
        if self.native:
            return ""
        identifiers = set(_QSS_TEMPLATE.get_identifiers())
        return _QSS_TEMPLATE.substitute({key: self.color(key) for key in identifiers})

    def header_stylesheet(self) -> str:
        """Estilos inline de la cabecera (mismas reglas que en Fase 5)."""
        return (
            f"QWidget#headerPanel {{ background-color: {self.color('header_bg')};"
            " border-radius: 6px; }"
            f"QWidget#headerPanel QLabel {{ color: {self.color('header_label')};"
            " background: transparent; }"
            f"QLabel#labelTitle {{ color: {self.color('header_title')}; }}"
            f"QLabel#labelFormat {{ color: {self.color('header_format')}; }}"
            f"QLabel#labelTime {{ color: {self.color('header_time')}; }}"
        )


def _parse_theme(path: Path) -> Theme:
    """Carga un tema desde su JSON (ValueError si el formato es malo)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("el JSON del tema no es un objeto")
    raw_colors = data.get("colors", {})
    if not isinstance(raw_colors, dict):
        raise ValueError("«colors» del tema no es un objeto")
    colors = {str(key): str(value) for key, value in raw_colors.items()}
    return Theme(
        id=str(data["id"]),
        name=str(data.get("name") or data["id"]),
        native=bool(data.get("native", False)),
        spectrum_hue=int(data.get("spectrum_hue", 210)),
        colors={**_FALLBACK_COLORS, **colors},
    )


def _fallback_theme() -> Theme:
    """Tema de emergencia = look histórico completo por si falta el JSON."""
    return Theme(
        id=DEFAULT_THEME_ID,
        name="Winamp oscuro (actual)",
        native=True,
        spectrum_hue=210,
        colors=dict(_FALLBACK_COLORS),
    )


def _read_themes() -> dict[str, Theme]:
    """Lee todos los JSON de ``THEMES_DIR`` (tolerante a archivos rotos)."""
    themes: dict[str, Theme] = {}
    for path in sorted(THEMES_DIR.glob("*.json")):
        try:
            theme = _parse_theme(path)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            logger.warning("Tema ignorado (%s): %s", path.name, exc)
            continue
        themes[theme.id] = theme
    if DEFAULT_THEME_ID not in themes:
        logger.warning("Falta el tema por defecto %r; se usa el de reserva", DEFAULT_THEME_ID)
        fallback = _fallback_theme()
        themes[fallback.id] = fallback
    return themes


_cache: dict[str, Theme] | None = None


def load_themes() -> dict[str, Theme]:
    """Tema por id (caché en el módulo; copia defensiva del dict)."""
    global _cache
    if _cache is None:
        _cache = _read_themes()
    return dict(_cache)


def get_theme(theme_id: str) -> Theme:
    """Tema por id; cualquier id desconocido cae en el por defecto."""
    themes = load_themes()
    return themes.get(str(theme_id), themes[DEFAULT_THEME_ID])
