"""Utility to get the correct ADB binary path (bundled only)."""
import sys
import platform
import os
import subprocess
from pathlib import Path


def get_current_arch():
    """Detect current machine architecture."""
    machine = platform.machine().lower()
    
    if machine in ("aarch64", "arm64", "armv8l"):
        return "arm64"
    elif machine in ("x86_64", "amd64"):
        return "x86_64"
    elif machine in ("i386", "i686"):
        return "x86"
    elif machine in ("armv7l", "armv7"):
        return "armv7"
    return machine


def get_arch_suffix():
    """Get architecture-specific suffix for ADB directory."""
    arch = get_current_arch()
    system = platform.system().lower()
    
    if system == "darwin":
        if arch == "arm64":
            return "macos_arm64"
        else:
            return "macos_x86_64"
    elif system == "linux":
        if arch == "arm64":
            return "linux_aarch64"
        elif arch == "x86_64":
            return "linux_x86_64"
        else:
            return None
    elif system == "windows":
        if arch == "arm64":
            return "windows_arm64"
        elif arch == "x86_64":
            return "windows_x86_64"
        else:
            return None
    
    return None


def is_binary_compatible(adb_path):
    """Check if a binary is compatible with current architecture."""
    try:
        result = subprocess.run(
            [adb_path, "version"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError, FileNotFoundError):
        return False


def get_adb_path():
    """
    Get the path to the ADB binary (bundled only - no system fallback).
    
    FadCat bundles ADB for all supported architectures:
    - Linux: x86_64, ARM64 (aarch64)
    - macOS: x86_64 (Intel), ARM64 (Apple Silicon)
    - Windows: x86_64, ARM64
    
    Priority:
    1. Environment variable FADCAT_ADB_PATH (set by ProcessReader for bundled mode)
    2. Bundled ADB for current architecture
    
    Returns:
        str: Full path to adb executable
    
    Raises:
        RuntimeError: If ADB cannot be found
    """
    # Check for environment variable override (set by ProcessReader in bundled mode)
    if 'FADCAT_ADB_PATH' in os.environ:
        adb_path = os.environ['FADCAT_ADB_PATH']
        if os.path.exists(adb_path) and is_binary_compatible(adb_path):
            return adb_path
        raise RuntimeError(
            f"FADCAT_ADB_PATH points to invalid binary: {adb_path}\n"
            f"Please ensure the path is correct and the binary is executable."
        )
    
    system = platform.system()
    is_bundled = getattr(sys, 'frozen', False)
    arch_suffix = get_arch_suffix()
    
    if arch_suffix is None:
        raise RuntimeError(
            f"Unsupported architecture: {get_current_arch()} on {system}\n"
            f"FadCat supports x86_64 and ARM64 on Linux, macOS, and Windows."
        )
    
    # Determine path based on bundled vs development mode
    if is_bundled:
        # Running as bundled app (PyInstaller)
        if system == "Darwin":
            base_path = Path(sys.executable).parent.parent / "Resources" / "platform-tools" / arch_suffix
        elif system == "Linux":
            base_path = Path(sys.executable).parent / "platform-tools" / arch_suffix
        elif system == "Windows":
            base_path = Path(sys.executable).parent / "platform-tools" / arch_suffix
        else:
            raise RuntimeError(f"Unsupported platform: {system}")
        
        adb_binary = "adb.exe" if system == "Windows" else "adb"
        adb_path = base_path / adb_binary
        
        if adb_path.exists() and is_binary_compatible(adb_path):
            return str(adb_path)
        
        raise RuntimeError(
            f"Bundled ADB not found or incompatible.\n"
            f"Architecture: {get_current_arch()} ({arch_suffix})\n"
            f"Expected: {adb_path}\n"
            f"This is a build error. Please report to the developers."
        )
    else:
        # Development mode: use bundled ADB from build/platform-tools
        project_root = Path(__file__).parent.parent.parent
        
        if system == "Darwin":
            adb_path = project_root / "build" / "platform-tools" / arch_suffix / "adb"
        elif system == "Linux":
            adb_path = project_root / "build" / "platform-tools" / arch_suffix / "adb"
        elif system == "Windows":
            adb_path = project_root / "build" / "platform-tools" / arch_suffix / "adb.exe"
        else:
            raise RuntimeError(f"Unsupported platform: {system}")
        
        if adb_path.exists() and is_binary_compatible(adb_path):
            return str(adb_path)
        
        raise RuntimeError(
            f"Bundled ADB not found or incompatible.\n"
            f"Architecture: {get_current_arch()} ({arch_suffix})\n"
            f"Expected: {adb_path}\n"
            f"\nRun 'python build/download_adb.py' to download all ADB binaries,\n"
            f"or ensure build/platform-tools/ contains ADB for your architecture."
        )


def get_adb_command():
    """Get ADB binary name with .exe suffix on Windows."""
    return "adb.exe" if platform.system() == "Windows" else "adb"
