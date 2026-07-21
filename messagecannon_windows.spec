# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for MessageCannon Pro — Windows (onefile EXE).

Modeled on messagecannon_unix.spec (the known-working Mac/Linux spec already
proven by CI) rather than any of the older, stale MessageCannon*.spec files in
the repo root — those predate several live features (drag-and-drop contact
import, HTML card preview, encrypted settings) and are missing the hidden
imports/data files those features need, plus they still reference dead
dependencies (pywhatkit, qrcode) that requirements.txt has since dropped.

Output: dist/MessageCannon.exe — onefile, matching installer/setup.iss's
`Source: "..\dist\MessageCannon.exe"` (that installer script is the one
CLAUDE.md documents as the real, in-use Windows packaging step).

Build:
  pyinstaller messagecannon_windows.spec --noconfirm
"""

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# ── Hidden imports ────────────────────────────────────────────────────────────
hiddenimports = [
    # UI framework
    "customtkinter",
    # Image handling (Card Creator, splash logo)
    "PIL",
    "PIL.Image",
    "PIL.ImageTk",
    # WhatsApp automation
    "selenium",
    "selenium.webdriver",
    "selenium.webdriver.chrome.service",
    "selenium.webdriver.chrome.options",
    "webdriver_manager",
    "webdriver_manager.chrome",
    # Data
    "pandas",
    "pandas.io.formats.style",
    "openpyxl",
    "xlrd",
    # Reports
    "reportlab",
    "reportlab.pdfgen",
    "reportlab.platypus",
    # Charts
    "matplotlib",
    "matplotlib.backends.backend_tkagg",
    "matplotlib.backends.backend_agg",
    # HTML card preview
    "tkinterweb",
    # Drag-and-drop contact import (Phase 2)
    "tkinterdnd2",
    # Scheduling
    "schedule",
    # License / settings encryption
    "cryptography",
    "cryptography.fernet",
    # App source
    "src",
]
hiddenimports += collect_submodules("src")
hiddenimports += collect_submodules("selenium")
hiddenimports += collect_submodules("reportlab")

# ── Bundled data ──────────────────────────────────────────────────────────────
datas = [
    # App assets (icons, themes, card templates)
    ("src/assets", "assets"),
    # Runtime schema loaded relative to the package at runtime (see
    # database/db_manager.py) — must ship alongside the frozen source tree.
    ("src/database/schema.sql", "src/database"),
]
datas += collect_data_files("customtkinter")   # theme JSON + fonts
datas += collect_data_files("tkinterweb")       # bundled Tcl/HTML scripts
datas += collect_data_files("tkinterdnd2")      # bundled tkdnd native binaries

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    ["src/main.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={
        # Pin matplotlib to the Tk backend explicitly rather than letting
        # PyInstaller's hook auto-discover whatever GUI toolkit happens to be
        # importable in the build environment (see excludes comment above).
        "matplotlib": {"backends": ["TkAgg"]},
    },
    runtime_hooks=[],
    # Qt bindings excluded deliberately: matplotlib's backend auto-detection
    # will happily bundle PySide6/PyQt if it happens to be importable in the
    # build environment (confirmed locally — a stray PySide6 install on this
    # dev machine, unrelated to this project, ballooned the EXE from ~40MB to
    # 146MB) even though this app only ever uses matplotlib's Tk backend
    # (reports_chart.py's FigureCanvasTkAgg). Excluding them makes the build
    # deterministic regardless of what else happens to be on a given machine.
    excludes=["pytest", "test", "tests", "unittest",
              "PySide6", "PySide2", "PyQt5", "PyQt6"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data)

# ── EXE (onefile — installer/setup.iss expects a single dist\MessageCannon.exe) ──
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="MessageCannon",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="src/assets/icons/app.ico",
)
