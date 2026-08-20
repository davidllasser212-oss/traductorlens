# -*- mode: python ; coding: utf-8 -*-

winrt_hidden = [
    "winrt.runtime",
    "winrt.system",
    "winrt._winrt",
    "winrt.windows.foundation",
    "winrt.windows.foundation.collections",
    "winrt.windows.globalization",
    "winrt.windows.graphics.imaging",
    "winrt.windows.media.ocr",
    "winrt.windows.storage.streams",
]

a = Analysis(
    ["../app/main.py"],
    pathex=[".."],
    binaries=[],
    datas=[
        ("../assets/languages.json", "assets"),
        ("../assets/icon.ico", "assets"),
    ],
    hiddenimports=winrt_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["winocr", "tkinter", "numpy", "pytest", "PyInstaller"],
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
    name="TraductorLens",
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
    icon=["../assets/icon.ico"],
    version="version_info.txt",
)
