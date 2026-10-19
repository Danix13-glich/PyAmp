#!/usr/bin/env python3
# Genera los PNG de PyAmp en varios tamaños a partir del logo SVG.
# Uso: make_icons.py <logo.svg> <destino/hicolor>
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtSvg import QSvgRenderer  # noqa: E402

SIZES = (16, 22, 24, 32, 48, 64, 128, 256, 512)


def main() -> int:
    if len(sys.argv) < 3:
        print("uso: make_icons.py <logo.svg> <destino/hicolor>", file=sys.stderr)
        return 2
    source = Path(sys.argv[1])
    destination = Path(sys.argv[2])
    if not source.is_file():
        print(f"no encuentro {source}", file=sys.stderr)
        return 1

    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841 - debe vivir
    renderer = QSvgRenderer(str(source))
    if not renderer.isValid():
        print(f"SVG no válido: {source}", file=sys.stderr)
        return 1

    for size in SIZES:
        image = QImage(QSize(size, size), QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        folder = destination / f"{size}x{size}" / "apps"
        folder.mkdir(parents=True, exist_ok=True)
        image.save(str(folder / "pyamp.png"))

    scalable = destination / "scalable" / "apps"
    scalable.mkdir(parents=True, exist_ok=True)
    (scalable / "pyamp.svg").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"iconos generados en {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
