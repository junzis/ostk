# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['/home/junzi/arc/code/1-public/ostk/src/ostk/main.py'],
    pathex=[],
    binaries=[],
    datas=[('/home/junzi/arc/code/1-public/ostk/src/ostk/agent/agent.md', 'ostk/agent'), ('/home/junzi/arc/code/1-public/ostk/assets/fonts', 'assets/fonts')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
