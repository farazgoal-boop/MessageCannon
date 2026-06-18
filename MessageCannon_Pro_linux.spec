# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for MessageCannon Pro — Linux onefile binary."""

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

hiddenimports = [
    "customtkinter",
    "PIL",
    "PIL.Image",
    "selenium",
    "webdriver_manager",
    "pandas",
    "openpyxl",
    "xlrd",
    "reportlab",
    "schedule",
    "cryptography",
    "matplotlib",
    "matplotlib.backends.backend_tkagg",
    "tkinterweb",
    "src",
]
hiddenimports += collect_submodules("src")
hiddenimports += collect_submodules("selenium")

datas = [
    ("src/assets", "assets"),
    ("src/assets/templates", "assets/templates"),
    ("src/assets/themes", "assets/themes"),
]
datas += collect_data_files("customtkinter")

a = Analysis(
    ["src/main.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "test", "tests"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="messagecannon-pro",
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
)
