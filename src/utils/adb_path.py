"""Utility to get the correct ADB binary path (bundled only)."""
import platform
import subprocess
import sys
from pathlib import Path


def get_current_arch():
    """Detect current machine architecture."""
    machine = platform.machine().lower()

    if machine in ("aarch64", "arm64", "armv8l"):
        return "arm64"
    if machine in ("x86_64", "amd64"):
        return "x86_64"
    if machine in ("i386", "i686"):
        return "x86"
    if machine in ("armv7l", "armv7"):
        return "armv7"
    return machine


def get_arch_suffix():
    """Get architecture-specific suffix for ADB directory."""
    arch = get_current_arch()
    system = platform.system().lower()

    if system == "darwin":
        return "macos_arm64" if arch == "arm64" else "macos_x86_64"
    if system == "linux":
        if arch == "arm64":
            return "linux_aarch64"
        if arch == "x86_64":
            return "linux_x86_64"
        return None
    if system == "windows":
        if arch == "arm64":
            return "windows_arm64"
        if arch == "x86_64":
            return "windows_x86_64"
        return None

    return None


def is_binary_compatible(adb_path):
    """Check if a binary is compatible with current architecture."""
    try:
        result = subprocess.run(
            [adb_path, "version"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError, FileNotFoundError):
        return False


def _windows_adb_companion_dlls_present(adb_path: Path) -> bool:
    """Windows adb needs companion DLLs in the same directory to start."""
    if platform.system() != "Windows":
        return True
    required = ("AdbWinApi.dll", "AdbWinUsbApi.dll")
    return all((adb_path.parent / dll_name).exists() for dll_name in required)


def _bundled_adb_path(base_dir: Path, system: str, arch_suffix: str) -> Path:
    adb_binary = "adb.exe" if system == "Windows" else "adb"
    return base_dir / "platform-tools" / arch_suffix / adb_binary


def get_adb_path():
    """
    Get the path to the ADB binary.

    FadCat uses bundled ADB only:
    - Linux: x86_64, ARM64 (aarch64)
    - macOS: x86_64 (Intel), ARM64 (Apple Silicon)
    - Windows: x86_64, ARM64

    The Windows bundle must also include AdbWinApi.dll and AdbWinUsbApi.dll.
    """
    system = platform.system()
    arch_suffix = get_arch_suffix()
    if arch_suffix is None:
        raise RuntimeError(
            f"Unsupported architecture: {get_current_arch()} on {system}\n"
            f"FadCat supports x86_64 and ARM64 on Linux, macOS, and Windows."
        )

    if getattr(sys, "frozen", False):
        if system == "Darwin":
            base_dir = Path(sys.executable).parent.parent / "Resources"
        elif system in ("Linux", "Windows"):
            base_dir = Path(sys.executable).parent / "_internal"
        else:
            raise RuntimeError(f"Unsupported platform: {system}")
    else:
        base_dir = Path(__file__).parent.parent.parent / "build"

    adb_path = _bundled_adb_path(base_dir, system, arch_suffix)

    if not adb_path.exists():
        raise RuntimeError(
            f"ADB not found for architecture {get_current_arch()}.\n"
            f"Tried: {adb_path}\n"
            f"Windows builds must include AdbWinApi.dll and AdbWinUsbApi.dll in the same folder.\n"
            f"Rebuild the Windows ADB bundle so build/platform-tools/windows_* contains adb.exe and the required DLLs."
        )

    if system == "Windows" and not _windows_adb_companion_dlls_present(adb_path):
        raise RuntimeError(
            f"Windows ADB bundle is incomplete.\n"
            f"Missing AdbWinApi.dll and/or AdbWinUsbApi.dll next to: {adb_path}\n"
            f"Rebuild the Windows ADB bundle so the DLLs are copied beside adb.exe."
        )

    if not is_binary_compatible(adb_path):
        raise RuntimeError(
            f"Bundled ADB failed to start for architecture {get_current_arch()}.\n"
            f"Tried: {adb_path}"
        )

    return str(adb_path)


def get_adb_command():
    """Get ADB binary name with .exe suffix on Windows."""
    return "adb.exe" if platform.system() == "Windows" else "adb"
