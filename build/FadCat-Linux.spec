# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for FadCat on Linux
# Creates a folder-based distribution
# Build with: pyinstaller FadCat-Linux.spec

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_all

# Import version info from single source of truth
sys.path.insert(0, os.path.abspath('.'))
try:
    from src.version import __version__, __app_name__, __company__
except ImportError:
    __version__ = "1.0.0"
    __app_name__ = "FadCat"
    __company__ = "FadSec Lab"

# Collect all fastmcp data and binaries (CRITICAL for bundling)
datas_fastmcp, binaries_fastmcp, hiddenimports_fastmcp = collect_all('fastmcp')

block_cipher = None

a = Analysis(
    ['../FadCat.py'],
    pathex=[],
    binaries=binaries_fastmcp,
    datas=[
        ('../src', 'src'),
        ('../fadcat_cli.py', '.'),
        ('../FadCat.py', '.'),
        ('../build/platform-tools/linux/adb', 'platform-tools/linux'),
        ('../build/linux/uninstall.sh', 'build/linux'),
    ] + datas_fastmcp,
    hiddenimports=[
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtSvg',
        'PyQt6.QtSvgWidgets',
        'PyQt6.sip',
        'rapidfuzz',
        'rapidfuzz.fuzz',
        'colorama',
        # FastMCP and its bundled dependencies (3.1.0)
        'fastmcp',
        'mcp',
        'mcp.server',
        'mcp.server.stdio',
        'mcp.types',
        'authlib',
        'cyclopts',
        'exceptiongroup',
        'httpx',
        'httpx_sse',
        'jsonschema',
        'jsonref',
        'jsonschema_path',
        'openapi_pydantic',
        'opentelemetry',
        'packaging',
        'platformdirs',
        'pydantic',
        'pydantic_core',
        'pydantic_settings',
        'pyperclip',
        'python_dotenv',
        'pyyaml',
        'rich',
        'starlette',
        'sse_starlette',
        'uvicorn',
        'watchfiles',
        'websockets',
        'anyio',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='fadcat',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='../icon-assets/fadcat.ico',
)

coll = Collection(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='fadcat',
)
