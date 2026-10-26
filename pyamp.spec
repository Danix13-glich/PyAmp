# -*- mode: python ; coding: utf-8 -*-
# Empaquetado de PyAmp con PyInstaller (AppImage, .exe y .app/.dmg).
import sys
from pathlib import Path

ROOT = Path(SPECPATH)

datas = []
assets = ROOT / "assets"
if assets.is_dir():
    datas.append((str(assets), "assets"))
themes = ROOT / "src" / "app" / "themes" / "data"
if themes.is_dir():
    datas.append((str(themes), "app/themes/data"))

hiddenimports = [
    "vlc",
    "app.notifications.linux_notifier",
    "app.notifications.windows_notifier",
    "app.notifications.macos_notifier",
]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(ROOT / "packaging" / "runtime_hook_vlc.py")],
    excludes=["tkinter", "tests"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="pyamp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="PyAmp.app",
        icon=None,
        bundle_identifier="com.danix13-glich.pyamp",
        info_plist={
            "CFBundleName": "PyAmp",
            "CFBundleDisplayName": "PyAmp",
            "CFBundleShortVersionString": "0.2.1",
            "CFBundleVersion": "0.2.1b18",
            "NSHighResolutionCapable": True,
        },
    )
