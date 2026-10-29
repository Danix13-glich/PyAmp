from __future__ import annotations

import colorsys
import json
import logging
import re
import string
from dataclasses import dataclass
from pathlib import Path

from app.utils.paths import THEMES_DIR as USER_THEMES_DIR

logger = logging.getLogger(__name__)

#: Carpeta con los JSON de temas incluidos.
THEMES_DIR = Path(__file__).resolve().parent / "data"

#: Tema que reproduce el look histórico.
DEFAULT_THEME_ID = "winamp-oscuro"

#: Paleta mínima: reserva para colores ausentes y para el tema de
#: emergencia si el JSON por defecto desaparece.
_FALLBACK_COLORS: dict[str, str] = {
    # cabecera
    "header_bg": "#17171b",
    "header_title": "#f2f2f7",
    "header_label": "#9e9ea6",
    "header_format": "#7e7e88",
    "header_time": "#e8e8ee",
    "text_muted": "#9e9ea6",
    # espectro
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
QPushButton { background-color: $button_bg; color: $window_text; border: 1px solid $button_border; border-radius: 4px; padding: 4px 12px; }
QPushButton:hover { background-color: $button_hover; }
QPushButton:pressed { background-color: $accent; color: $accent_text; border-color: $accent; }
QPushButton:focus { border-color: $accent; }
QPushButton:disabled { color: $text_muted; }
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

    id: str
    name: str
    native: bool
    spectrum_hue: int
    colors: dict[str, str]

    def color(self, key: str) -> str:
        return self.colors.get(key, _FALLBACK_COLORS.get(key, "#000000"))

    @property
    def qss(self) -> str:
        if self.native:
            return ""
        identifiers = set(_QSS_TEMPLATE.get_identifiers())
        return _QSS_TEMPLATE.substitute({key: self.color(key) for key in identifiers})

    def header_stylesheet(self) -> str:
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
    return Theme(
        id=DEFAULT_THEME_ID,
        name="Winamp Oscuro",
        native=True,
        spectrum_hue=210,
        colors=dict(_FALLBACK_COLORS),
    )


def _read_themes() -> dict[str, Theme]:
    themes: dict[str, Theme] = {}
    for directory in (THEMES_DIR, USER_THEMES_DIR):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
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


def load_themes(force: bool = False) -> dict[str, Theme]:
    global _cache
    if _cache is None or force:
        _cache = _read_themes()
    return dict(_cache)


def reload_themes() -> dict[str, Theme]:
    return load_themes(force=True)


def get_theme(theme_id: str) -> Theme:
    themes = load_themes()
    return themes.get(str(theme_id), themes[DEFAULT_THEME_ID])


# ------------------------------------------------ temas personalizados (0.2.0)
def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    text = str(value).strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        raise ValueError(f"color no válido: {value!r}")
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, int(round(c)))) for c in rgb))


def _mix(first: str, second: str, amount: float) -> str:
    a = _hex_to_rgb(first)
    b = _hex_to_rgb(second)
    ratio = max(0.0, min(1.0, float(amount)))
    return _rgb_to_hex(tuple(round(a[i] + (b[i] - a[i]) * ratio) for i in range(3)))  # type: ignore[arg-type]


def _luminance(value: str) -> float:
    red, green, blue = (channel / 255 for channel in _hex_to_rgb(value))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _readable_on(background: str) -> str:
    return "#101014" if _luminance(background) > 0.55 else "#ffffff"


def _hue(value: str) -> int:
    red, green, blue = (channel / 255 for channel in _hex_to_rgb(value))
    hue, _, _ = colorsys.rgb_to_hsv(red, green, blue)
    return int(round(hue * 360)) % 360


def derive_theme_colors(window_bg: str, window_text: str, accent: str) -> dict[str, str]:
    dark = _luminance(window_bg) < 0.5
    surface_bg = _mix(window_bg, window_text, 0.08 if dark else 0.05)
    surface_alt = _mix(window_bg, window_text, 0.16 if dark else 0.11)
    border = _mix(window_bg, window_text, 0.28 if dark else 0.24)
    text_muted = _mix(window_text, window_bg, 0.45)
    header_bg = _mix(surface_alt, accent, 0.12)
    return {
        "header_bg": header_bg,
        "header_title": window_text,
        "header_label": _mix(window_text, window_bg, 0.35),
        "header_format": _mix(window_text, window_bg, 0.5),
        "header_time": accent,
        "text_muted": text_muted,
        "spectrum_bg": window_bg,
        "spectrum_line": _mix(accent, window_text, 0.35),
        "icon": window_text,
        "window_bg": window_bg,
        "window_text": window_text,
        "surface_bg": surface_bg,
        "surface_alt": surface_alt,
        "border": border,
        "accent": accent,
        "accent_text": _readable_on(accent),
        "button_bg": surface_alt,
        "button_hover": _mix(window_bg, window_text, 0.26 if dark else 0.2),
        "button_border": border,
        "slider_groove": border,
        "slider_handle": accent,
    }


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower()).strip("-")
    return text or "tema"


def custom_theme_count() -> int:
    if not USER_THEMES_DIR.is_dir():
        return 0
    return len(list(USER_THEMES_DIR.glob("*.json")))


def create_custom_theme(
    window_bg: str,
    window_text: str,
    accent: str,
    name: str | None = None,
) -> Theme:
    colors = derive_theme_colors(window_bg, window_text, accent)
    base_name = (name or "").strip() or f"Personalizado {custom_theme_count() + 1}"
    theme_id = f"custom-{_slug(base_name)}"
    data = {
        "id": theme_id,
        "name": base_name,
        "native": False,
        "spectrum_hue": _hue(accent),
        "colors": colors,
    }
    USER_THEMES_DIR.mkdir(parents=True, exist_ok=True)
    path = USER_THEMES_DIR / f"{theme_id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Tema personalizado creado: %s (%s)", base_name, path)
    reload_themes()
    return _parse_theme(path)


def find_custom_theme_path(theme_id: str) -> Path | None:
    # Solo los temas del usuario viven en USER_THEMES_DIR.
    if not USER_THEMES_DIR.is_dir():
        return None
    for path in USER_THEMES_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and str(data.get("id")) == str(theme_id):
            return path
    return None


def is_custom_theme(theme_id: str) -> bool:
    return find_custom_theme_path(theme_id) is not None


def delete_custom_theme(theme_id: str) -> bool:
    path = find_custom_theme_path(theme_id)
    if path is None:
        return False
    try:
        path.unlink()
    except OSError as exc:
        logger.warning("No se pudo borrar el tema %s: %s", path, exc)
        return False
    logger.info("Tema personalizado eliminado: %s", path)
    reload_themes()
    return True


def delete_all_custom_themes() -> int:
    global _cache
    if not USER_THEMES_DIR.is_dir():
        _cache = None
        return 0
    removed = 0
    for path in sorted(USER_THEMES_DIR.glob("*.json")):
        try:
            path.unlink()
            removed += 1
        except OSError as exc:
            logger.warning("No se pudo borrar el tema %s: %s", path, exc)
    _cache = None
    logger.info("Temas personalizados eliminados: %d", removed)
    return removed


def rename_custom_theme(theme_id: str, name: str) -> Theme | None:
    path = find_custom_theme_path(theme_id)
    if path is None:
        return None
    clean = str(name).strip()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("No se pudo leer el tema %s: %s", path, exc)
        return None
    if not isinstance(data, dict):
        return None
    if clean:
        data["name"] = clean
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning("No se pudo renombrar el tema %s: %s", path, exc)
        return None
    logger.info("Tema personalizado renombrado: %s", data.get("name"))
    reload_themes()
    return _parse_theme(path)
