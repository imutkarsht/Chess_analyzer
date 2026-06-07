# -*- mode: python ; coding: utf-8 -*-

import sys
import os
import glob

# Dynamically locate the DLLs directory from the Python installation
dll_source_dir = os.path.join(sys.base_prefix, 'DLLs')

# Find libssl and libcrypto DLLs
ssl_dlls = glob.glob(os.path.join(dll_source_dir, 'libssl*.dll'))
crypto_dlls = glob.glob(os.path.join(dll_source_dir, 'libcrypto*.dll'))

# Prepare binaries list
my_binaries = []
for dll in ssl_dlls + crypto_dlls:
    my_binaries.append((dll, '.'))
    
block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=my_binaries,
    datas=[('assets', 'assets'), ('.env.sample', '.')],
    hiddenimports=['chess', 'PyQt6', 'groq', 'dotenv', 'PyQt6.QtSvg', 'qtawesome', 'packaging', 'packaging.version'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'xmlrpc', 'pydoc', 'pdb'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Determine executable icon based on platform (Windows requires .ico, macOS converts .png)
exe_icon = 'assets/images/logo.png'
if sys.platform == 'win32':
    ico_path = 'assets/images/logo.ico'
    exe_icon = ico_path if os.path.exists(ico_path) else None

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name='ChessAnalyzerPro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=exe_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ChessAnalyzerPro',
)

app = BUNDLE(
    coll,
    name='ChessAnalyzerPro.app',
    icon='assets/images/logo.png',
    bundle_identifier='com.imutkarsht.chessanalyzerpro'
)
