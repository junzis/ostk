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

# Exclude system SSL libraries that cause version conflicts on Linux
EXCLUDE_BINARIES = ['libssl.so', 'libcrypto.so']
a.binaries = [b for b in a.binaries if not any(excl in b[0] for excl in EXCLUDE_BINARIES)]

pyz = PYZ(a.pure)

if sys.platform == 'darwin':
    # macOS: Use onedir mode with .app bundle for instant startup
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='OSTK',
        icon=ICON,
        debug=False,
        bootloader_ignore_signals=False,
        strip=True,
        upx=False,  # UPX not needed for onedir
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=True,
        upx=False,
        name='OSTK',
    )
    app = BUNDLE(
        coll,
        name='OSTK.app',
        icon=ICON,
        bundle_identifier='io.github.junzis.ostk',
        info_plist={
            'CFBundleShortVersionString': '0.1.0',
            'NSHighResolutionCapable': True,
        },
    )
else:
    # Windows/Linux: Single file executable
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
        strip=True,
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
