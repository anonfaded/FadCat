import os
import subprocess

def get_adb_devices():
    """Returns a list of connected ADB device serials."""
    try:
        res = subprocess.run(['adb', 'devices'], capture_output=True, text=True, check=False)
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
    except FileNotFoundError:
        return []
