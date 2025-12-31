# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for OSTK.

Build with: uv run pyinstaller OSTK.spec
"""

from pathlib import Path

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

project_root = Path(SPECPATH)

a = Analysis(
    [str(project_root / 'src' / 'ostk' / 'main.py')],
    pathex=[str(project_root / 'src')],
    binaries=[],
    datas=[
        (str(project_root / 'src' / 'ostk' / 'agent' / 'agent.md'), 'ostk/agent'),
        (str(project_root / 'assets' / 'fonts'), 'assets/fonts'),
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
