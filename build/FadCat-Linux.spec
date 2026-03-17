# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for FadCat on Linux
# Bundles ADB for ALL Linux architectures (x86_64 and ARM64)
# Build with: pyinstaller build/FadCat-Linux.spec

import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_all

# Spec file is run from project root, use relative paths
project_root = Path('.').resolve()

sys.path.insert(0, str(project_root))
try:
    from src.version import __version__, __app_name__, __company__
except ImportError:
    __version__ = "1.0.0"
    __app_name__ = "FadCat"
    __company__ = "FadSec Lab"

# Collect all fastmcp data and binaries (CRITICAL for bundling MCP support)
# This properly collects fastmcp, mcp, and all their dependencies
datas_fastmcp, binaries_fastmcp, hiddenimports_fastmcp = collect_all('fastmcp')

# Bundle ADB for ALL Linux architectures
platform_tools_dir = project_root / "build" / "platform-tools"

linux_binaries = []

# Linux x86_64 - copy file to directory
adb_x86_64 = platform_tools_dir / "linux_x86_64" / "adb"
if adb_x86_64.exists():
    linux_binaries.append((str(adb_x86_64), 'platform-tools/linux_x86_64/'))
    print("✓ Bundling ADB for Linux x86_64")
else:
    print("✗ Missing: Linux x86_64 ADB")

# Linux ARM64 (aarch64) - copy file to directory
adb_arm64 = platform_tools_dir / "linux_aarch64" / "adb"
if adb_arm64.exists():
    linux_binaries.append((str(adb_arm64), 'platform-tools/linux_aarch64/'))
    print("✓ Bundling ADB for Linux ARM64")
else:
    print("✗ Missing: Linux ARM64 ADB")

block_cipher = None

a = Analysis(
    [str(project_root / 'FadCat.py')],
    pathex=[],
    binaries=binaries_fastmcp + linux_binaries,
    datas=[
        (str(project_root / 'src'), 'src'),
        (str(project_root / 'fadcat_cli.py'), '.'),
        (str(project_root / 'FadCat.py'), '.'),
        (str(project_root / 'icon-assets'), 'icon-assets'),
        (str(project_root / 'build/linux/uninstall.sh'), 'build/linux'),
    ] + datas_fastmcp,
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
        'pydantic',
        'pydantic_core',
        'pydantic_settings',
        'pyyaml',
        'rich',
        'starlette',
        'sse_starlette',
        'uvicorn',
        'watchfiles',
        'websockets',
        'anyio',
        'httpx',
        'httpx_sse',
        'jsonschema',
        'packaging',
        'platformdirs',
        'python_dotenv',
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
    icon=str(project_root / 'icon-assets/fadcat.ico'),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='fadcat',
)
