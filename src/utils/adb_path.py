"""Utility to get the correct ADB binary path (bundled or system)."""
import sys
import platform
import os
from pathlib import Path


def get_adb_path():
    """
    Get the path to the ADB binary.
    
    Priority:
    1. Environment variable FADCAT_ADB_PATH (set by ProcessReader for bundled mode)
    2. Bundled ADB for PyInstaller apps
    3. Development ADB from build/platform-tools
    
    For bundled apps (PyInstaller):
    - macOS: bundle/Contents/Resources/adb
    - Linux: dist/adb
    - Windows: dist/adb.exe
    
    Returns:
        str: Full path to adb executable
        
    Raises:
        RuntimeError: If ADB cannot be found
    """
    # Check for environment variable override (set by ProcessReader in bundled mode)
    if 'FADCAT_ADB_PATH' in os.environ:
        adb_path = os.environ['FADCAT_ADB_PATH']
        if os.path.exists(adb_path):
            return adb_path
        # Fall through to normal detection if env var path doesn't exist
    
    system = platform.system()
    is_bundled = getattr(sys, 'frozen', False)
    
    # Determine if running from bundled app or development
    if is_bundled:
        # Running as bundled app (PyInstaller)
        if system == "Darwin":  # macOS
            # For macOS .app bundle: @executable_path/../Resources/
            base_path = Path(sys.executable).parent.parent / "Resources" / "platform-tools" / "macos"
        elif system == "Linux":
            # For Linux: _internal directory (PyInstaller Linux)
            base_path = Path(sys.executable).parent / "platform-tools" / "linux"
        elif system == "Windows":
            # For Windows: _internal directory (PyInstaller Windows)
            base_path = Path(sys.executable).parent / "platform-tools" / "windows"
        else:
            raise RuntimeError(f"Unsupported platform: {system}")
        
        adb_binary = "adb.exe" if system == "Windows" else "adb"
        adb_path = base_path / adb_binary
        
        if not adb_path.exists():
            raise RuntimeError(
                f"Bundled ADB not found at: {adb_path}\n"
                f"This is a critical error. Please reinstall FadCat."
            )
        
        return str(adb_path)
    else:
        # Development mode: use bundled ADB from build/platform-tools
        project_root = Path(__file__).parent.parent.parent
        
        if system == "Darwin":  # macOS
            adb_path = project_root / "build" / "platform-tools" / "macos" / "adb"
        elif system == "Linux":
            adb_path = project_root / "build" / "platform-tools" / "linux" / "adb"
        elif system == "Windows":
            adb_path = project_root / "build" / "platform-tools" / "windows" / "adb.exe"
        else:
            raise RuntimeError(f"Unsupported platform: {system}")
        
        if not adb_path.exists():
            raise RuntimeError(
                f"Bundled ADB not found at: {adb_path}\n"
                f"Run 'python build/download_adb.py' to download platform-specific ADB binaries."
            )
        
        return str(adb_path)


def get_adb_command():
    """
    Get ADB binary name with .exe suffix on Windows if needed.
    
    Returns:
        str: 'adb' or 'adb.exe' depending on platform
    """
    return "adb.exe" if platform.system() == "Windows" else "adb"
