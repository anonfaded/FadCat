# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for FadCat CLI on Windows
# This creates a CLI/MCP version with console=True for proper stdin/stdout
# Bundles ADB for ALL Windows architectures (x86_64 and ARM64)
# Build with: pyinstaller build/FadCat-Windows-CLI.spec

from PyInstaller.utils.hooks import collect_data_files, collect_all
from PyInstaller.building.api import EXE, COLLECT
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath('.'))
try:
    from src.version import __version__, __app_name__, __company__
except ImportError:
    __version__ = "1.0.0"
    __app_name__ = "FadCat"
    __company__ = "FadSec Lab"

# Collect all fastmcp data and binaries (CRITICAL for bundling MCP support)
datas_fastmcp, binaries_fastmcp, hiddenimports_fastmcp = collect_all('fastmcp')

# Collect jsonschema data files for MCP JSON schema validation
datas_jsonschema = collect_data_files('jsonschema_specifications')

# Bundle ADB for ALL Windows architectures
project_root = Path(os.getcwd())
platform_tools_dir = project_root / "build" / "platform-tools"

windows_binaries = []

def _collect_windows_platform_tools(arch_name: str):
    arch_dir = platform_tools_dir / arch_name
    if not arch_dir.exists():
        print(f"[!] Missing: {arch_name} folder")
        return

    payload_files = [
        path for path in arch_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".exe", ".dll"}
    ]
    if not payload_files:
        print(f"[!] Missing: {arch_name} ADB payload files")
        return

    for payload_file in payload_files:
        windows_binaries.append((str(payload_file), f'platform-tools/{arch_name}/'))

    print(f"[OK] Bundling ADB for {arch_name}")


_collect_windows_platform_tools("windows_x86_64")
_collect_windows_platform_tools("windows_arm64")

block_cipher = None

a = Analysis(
    ['../FadCat.py'],
    pathex=[],
    binaries=binaries_fastmcp + windows_binaries,
    datas=[
        ('../src', 'src'),
        ('../icon-assets', 'icon-assets'),
        ('../fadcat_cli.py', '.'),
        ('../FadCat.py', '.'),
        ('../build/windows/uninstall.bat', 'build/windows'),
    ] + datas_fastmcp + datas_jsonschema,
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
    name='FadCat-CLI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='../icon-assets/fadcat.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FadCat-CLI',
)
