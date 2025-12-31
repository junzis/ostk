# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for OSTK.

Build with: uv run pyinstaller OSTK.spec
"""

import sys
from pathlib import Path

# Platform-specific icon
project_root = Path(SPECPATH)
if sys.platform == 'win32':
    ICON = str(project_root / 'assets' / 'icons' / 'ostk.ico')
elif sys.platform == 'darwin':
    ICON = str(project_root / 'assets' / 'icons' / 'ostk.png')  # Will be converted to icns
else:
    ICON = str(project_root / 'assets' / 'icons' / 'ostk.png')

# Modules to exclude (not needed for desktop GUI)
EXCLUDES = [
    # Web-only flet (60MB savings)
    "flet_web",
    # Dev dependencies
    "IPython",
    "ipykernel",
    "ipywidgets",
    "jupyter",
    "notebook",
    "matplotlib",
    "pytest",
    # Unused heavy packages
    "PIL",
    "cv2",
    "scipy",
    # Test modules
    "pandas.tests",
    "numpy.tests",
    "numpy.f2py",
]

a = Analysis(
    [str(project_root / 'src' / 'ostk' / 'main.py')],
    pathex=[str(project_root / 'src')],
    binaries=[],
    datas=[
        (str(project_root / 'src' / 'ostk' / 'agent' / 'agent.md'), 'ostk/agent'),
        (str(project_root / 'assets' / 'fonts'), 'assets/fonts'),
        (str(project_root / 'assets' / 'icons'), 'assets/icons'),
    ],
    hiddenimports=[
        'flet',
        'flet_desktop',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
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
    name='OSTK',
    icon=ICON,
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,  # Strip debug symbols
    upx=True,    # Compress with UPX
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
