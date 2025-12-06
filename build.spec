# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[
        (r'C:\Users\Utkarsh Tiwari\AppData\Roaming\uv\python\cpython-3.13.9-windows-x86_64-none\DLLs\libssl-3-x64.dll', '.'),
        (r'C:\Users\Utkarsh Tiwari\AppData\Roaming\uv\python\cpython-3.13.9-windows-x86_64-none\DLLs\libcrypto-3-x64.dll', '.')
    ],
    datas=[('assets', 'assets'), ('.env.sample', '.')],
    hiddenimports=['chess', 'PyQt6', 'google.generativeai', 'dotenv', 'PyQt6.QtSvg'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'xmlrpc', 'pydoc', 'pdb'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ChessAnalyzerPro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/images/logo.png',
)
