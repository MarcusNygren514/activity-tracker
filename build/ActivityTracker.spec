# -*- mode: python ; coding: utf-8 -*-
"""
ActivityTracker – PyInstaller spec
Bygger en enkel .exe (tray_app.py som entry point)
"""

import sys
from pathlib import Path

APP_DIR = Path(r"C:\activity_tracker")

a = Analysis(
    [str(APP_DIR / "tray_app.py")],
    pathex=[str(APP_DIR)],
    binaries=[],
    datas=[
        (str(APP_DIR / "activity_tracker.ico"), "."),
    ],
    hiddenimports=[
        "pystray._win32",
        "PIL._tkinter_finder",
        "flask",
        "werkzeug",
        "werkzeug.serving",
        "werkzeug.debug",
        "jinja2",
        "click",
        "psutil",
        "sqlite3",
        "ctypes",
        "ctypes.wintypes",
        "msvcrt",
        "tracker",
        "web_app",
        "updater",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ActivityTracker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(APP_DIR / "activity_tracker.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ActivityTracker",
)
