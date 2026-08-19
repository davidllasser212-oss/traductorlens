# -*- mode: python ; coding: utf-8 -*-

import glob
import os

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

_base = os.path.abspath(SPECPATH and os.path.join(SPECPATH, "..") or os.getcwd())

tess_bin_dir = os.path.join(_base, "vendor", "tesseract", "bin")
tess_binaries = [
    (os.path.join(tess_bin_dir, f), "tesseract")
    for f in os.listdir(tess_bin_dir)
    if os.path.isfile(os.path.join(tess_bin_dir, f))
]

tess_datas = [
    (f, "tessdata")
    for f in glob.glob(os.path.join(_base, "assets", "tessdata", "*.traineddata"))
]

a = Analysis(
    ["../app/main.py"],
    pathex=[".."],
    binaries=tess_binaries,
    datas=[
        ("../assets/languages.json", "assets"),
        ("../assets/icon.ico", "assets"),
    ]
    + tess_datas,
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
