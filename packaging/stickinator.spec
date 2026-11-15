# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the unsigned macOS app bundle.

Build with ``make build`` (see scripts/build_macos.sh).
"""

import os

from PyInstaller.utils.hooks import collect_all, collect_submodules

SPEC_DIR = SPECPATH  # noqa: F821 - injected by PyInstaller
PROJECT_ROOT = os.path.dirname(SPEC_DIR)

datas = []
binaries = []
hiddenimports = []

# rembg pulls in pymatting -> numba/llvmlite, plus onnxruntime. None of these
# are discovered reliably from imports alone.
for package in ("rembg", "pymatting", "onnxruntime", "numba", "llvmlite"):
    package_datas, package_binaries, package_hiddenimports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports

# rembg resolves models by name at runtime, so the session modules are invisible
# to static analysis.
hiddenimports += collect_submodules("rembg.sessions")

a = Analysis(
    [os.path.join(PROJECT_ROOT, "src", "stickinator", "__main__.py")],
    pathex=[os.path.join(PROJECT_ROOT, "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Stickinator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Stickinator",
)

app = BUNDLE(
    coll,
    name="Stickinator.app",
    icon=None,
    bundle_identifier="app.stickinator.desktop",
    info_plist={
        "CFBundleName": "Stickinator",
        "CFBundleDisplayName": "Stickinator",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "0.1.0",
        "LSMinimumSystemVersion": "14.0",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
    },
)
