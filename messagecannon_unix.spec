# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for MessageCannon Pro — Mac (.app + DMG) and Linux (onedir + .deb/.AppImage).

Mac output:   dist/MessageCannonPro.app   (via BUNDLE)
Linux output: dist/MessageCannonPro/      (onedir — packaged into .deb and AppImage by CI)

Build:
  pyinstaller messagecannon_unix.spec --noconfirm
"""

import sys
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
    # Scheduling
    "schedule",
    # License
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
]
datas += collect_data_files("customtkinter")   # theme JSON + fonts
datas += collect_data_files("tkinterweb")       # bundled Tcl/HTML scripts

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    ["src/main.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "test", "tests", "unittest"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data)

# ── EXE (shared base — binaries excluded so COLLECT can gather them) ──────────
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MessageCannonPro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # No .icns in repo — icon omitted on Mac/Linux
)

# ── COLLECT (onedir bundle used by both platforms) ────────────────────────────
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MessageCannonPro",
)

# ── BUNDLE (Mac only — wraps COLLECT into a .app) ────────────────────────────
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="MessageCannonPro.app",
        icon=None,             # No .icns in repo; add src/assets/icons/app.icns to enable
        bundle_identifier="com.farazautomation.messagecannonpro",
        info_plist={
            "CFBundleName": "MessageCannon Pro",
            "CFBundleDisplayName": "MessageCannon Pro",
            "CFBundleVersion": "1.0.0",
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,   # supports dark mode
        },
    )
