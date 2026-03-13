import os
import subprocess
from src.utils.adb_path import get_adb_path


def get_adb_devices():
    """Returns a list of connected ADB device serials."""
    try:
        adb_path = get_adb_path()
        res = subprocess.run([adb_path, 'devices'], capture_output=True, text=True, check=False, timeout=10)
        lines = res.stdout.splitlines()[1:]
        devices = []
        for l in lines:
            l = l.strip()
            if not l:
                continue
            parts = l.split()
            if parts:
                devices.append(parts[0])
        return devices
    except Exception as e:
        # Log the error for debugging but return empty list
        # GUI will show "(no devices)" and user can troubleshoot
        print(f"[ADB] Error getting devices: {e}", file=__import__('sys').stderr)
        return []
