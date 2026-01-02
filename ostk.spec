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
    # Dev dependencies
    "IPython",
    "ipykernel",
    "ipywidgets",
    "jupyter",
    "notebook",
    "matplotlib",
    "pytest",
    # Unused heavy packages
    "cv2",
    "scipy",
    # Test modules
    "pandas.tests",
    "numpy.tests",
    "numpy.f2py",
]

a = Analysis(
    [str(project_root / 'src' / 'ostk' / 'gui' / 'main.py')],
    pathex=[str(project_root / 'src')],
    binaries=[],
    datas=[
        (str(project_root / 'src' / 'ostk' / 'agent' / 'agent.md'), 'ostk/agent'),
        (str(project_root / 'src' / 'ostk' / 'gui' / 'web'), 'ostk/gui/web'),
        (str(project_root / 'assets' / 'icons'), 'assets/icons'),
    ],
    hiddenimports=[
        'webview',
        'bottle',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=0,
)

# Exclude unused pyarrow components (cloud storage backends, flight RPC)
EXCLUDE_BINARIES = [
    'libssl.so',
    'libcrypto.so',
    # Unused pyarrow cloud storage and RPC (~25MB)
    'libarrow_flight',
    'libarrow_substrait',
    '_azurefs',
    '_gcsfs',
    '_hdfs',
    '_s3fs',
    '_flight',
    '_substrait',
    '_orc',  # ORC format (we use parquet)
]

# On Linux, exclude system GTK/GLib libraries - users must install them anyway
# This saves ~80MB since these come with the system GTK installation
if sys.platform == 'linux':
    EXCLUDE_BINARIES.extend([
        # GTK and GLib stack (users install via apt/dnf/pacman)
        'libgtk-3.so',
        'libgdk-3.so',
        'libgio-2.0.so',
        'libglib-2.0.so',
        'libgobject-2.0.so',
        'libgmodule-2.0.so',
        'libgthread-2.0.so',
        # Cairo/Pango graphics
        'libcairo.so',
        'libpango',
        'libpixman',
        'libharfbuzz.so',
        'libfreetype.so',
        'libfontconfig.so',
        # ICU (internationalization) - comes with system
        'libicudata.so',
        'libicuuc.so',
        'libicui18n.so',
        # X11/Wayland - system provided
        'libX11.so',
        'libxcb',
        'libwayland',
        # Other system libs
        'libxml2.so',
        'libsqlite3.so',
        'libsystemd.so',
        'libdbus',
        'libepoxy.so',
        'libatk',
        'libgnutls.so',
        'libunistring.so',
        'libp11-kit.so',
        'libzstd.so',
        'libwebp.so',
        # Misc system libs pulled in by GTK
        'libtinysparql',
        'libglycin',
        'libleancrypto',
        'libopenraw',
    ])

a.binaries = [b for b in a.binaries if not any(excl in b[0] for excl in EXCLUDE_BINARIES)]

# Exclude unnecessary large data files to reduce bundle size
# These are GTK/Qt theme icons and locale files that aren't needed
EXCLUDE_DATAS = [
    'share/icons',      # GTK/KDE icon themes (~150MB)
    'share/locale',     # Translation files (~22MB)
    'share/themes',     # GTK themes
]

# On Linux, also exclude GTK typelibs and modules - provided by system
if sys.platform == 'linux':
    EXCLUDE_DATAS.extend([
        'gi_typelibs',   # GObject introspection typelibs
        'gio_modules',   # GIO modules
        'share/glib-2.0',
        'share/fontconfig',
        'share/mime',
    ])

a.datas = [d for d in a.datas if not any(excl in d[0] for excl in EXCLUDE_DATAS)]

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
elif sys.platform == 'linux':
    # Linux: Use onedir mode for AppImage (allows linuxdeploy to bundle GTK)
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
        upx=False,
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
else:
    # Windows: Use onedir mode for fast startup (distribute as zip)
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='OSTK',
        icon=ICON,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,  # Don't strip on Windows
        upx=False,
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
        strip=False,
        upx=False,
        name='OSTK',
    )
