# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for FadCat on macOS
# Bundles ADB for ALL macOS architectures (Intel x86_64 and Apple Silicon ARM64)
# Build with: pyinstaller build/FadCat-macOS.spec

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_all

sys.path.insert(0, os.path.abspath('.'))
try:
    from src.version import __version__, __app_name__, __company__, __author__
except ImportError:
    __version__ = "1.0.0"
    __app_name__ = "FadCat"
    __company__ = "FadSec Lab"
    __author__ = "Faded"

# Collect all fastmcp data and binaries (CRITICAL for bundling MCP support)
datas_fastmcp, binaries_fastmcp, hiddenimports_fastmcp = collect_all('fastmcp')

# Bundle ADB for ALL macOS architectures
project_root = Path(__file__).parent.parent
platform_tools_dir = project_root / "build" / "platform-tools"

macos_datas = []

# macOS x86_64 (Intel) - copy file to directory
adb_x86_64 = platform_tools_dir / "macos_x86_64" / "adb"
if adb_x86_64.exists():
    macos_datas.append((str(adb_x86_64), 'platform-tools/macos_x86_64/'))
    print("✓ Bundling ADB for macOS x86_64 (Intel)")
else:
    print("✗ Missing: macOS x86_64 ADB")

# macOS ARM64 (Apple Silicon) - copy file to directory
adb_arm64 = platform_tools_dir / "macos_arm64" / "adb"
if adb_arm64.exists():
    macos_datas.append((str(adb_arm64), 'platform-tools/macos_arm64/'))
    print("✓ Bundling ADB for macOS ARM64 (Apple Silicon)")
else:
    print("✗ Missing: macOS ARM64 ADB")

block_cipher = None

a = Analysis(
    ['../FadCat.py'],
    pathex=[],
    binaries=binaries_fastmcp,
    datas=[
        ('../src', 'src'),
        ('../fadcat_cli.py', '.'),
        ('../FadCat.py', '.'),
        ('../icon-assets', 'icon-assets'),
        ('../build/macos/uninstall.sh', 'build/macos'),
    ] + macos_datas + datas_fastmcp,
    hiddenimports=[
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtSvg',
        'PyQt6.sip',
        'rapidfuzz',
        'rapidfuzz.fuzz',
        'colorama',
        # FastMCP and MCP (collected via collect_all)
        'fastmcp',
        'mcp',
        'mcp.server',
        'mcp.server.stdio',
        'mcp.types',
        # Additional dependencies
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
    excludedimports=[
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.sip',
    ],
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
    name='FadCat',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    codesign_identity=None,
    entitlements_file=None,
    icon='../icon-assets/fadcat.icns',
)

coll = ((
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
),
    'FadCat',
    'FadCat.app',
)

app = BUNDLE(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='FadCat.app',
    icon='../icon-assets/fadcat.icns',
    bundle_identifier='com.fadseclab.fadcat',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSHighResolutionCapable': 'True',
        'NSRequiresIPhoneOS': False,
        'CFBundleShortVersionString': __version__,
        'CFBundleVersion': __version__,
        'CFBundleGetInfoString': f'{__app_name__} {__version__} - {__author__}',
    },
)
