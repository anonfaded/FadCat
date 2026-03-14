import os
import subprocess
import sys
from src.utils.adb_path import get_adb_path


def get_adb_devices():
    """Returns a list of connected ADB device serials."""
    try:
        adb_path = get_adb_path()
        print(f"[ADB] Using ADB: {adb_path}", file=sys.stderr)
        
        res = subprocess.run(
            [adb_path, 'devices'], 
            capture_output=True, 
            text=True, 
            check=False, 
            timeout=10
        )
        
        print(f"[ADB] Return code: {res.returncode}", file=sys.stderr)
        print(f"[ADB] stdout: {res.stdout.strip()}", file=sys.stderr)
        if res.stderr:
            print(f"[ADB] stderr: {res.stderr.strip()}", file=sys.stderr)
        
        lines = res.stdout.splitlines()[1:]  # Skip header
        devices = []
        for l in lines:
            l = l.strip()
            if not l:
                continue
            parts = l.split()
            if len(parts) >= 2 and parts[1] == 'device':
                devices.append(parts[0])
            elif len(parts) >= 2:
                print(f"[ADB] Device {parts[0]} status: {parts[1]}", file=sys.stderr)
        
        print(f"[ADB] Found {len(devices)} device(s): {devices}", file=sys.stderr)
        return devices
        
    except FileNotFoundError as e:
        print(f"[ADB] ADB not found: {e}", file=sys.stderr)
        return []
    except subprocess.TimeoutExpired:
        print(f"[ADB] Timeout waiting for ADB devices", file=sys.stderr)
        return []
    except Exception as e:
        print(f"[ADB] Error getting devices: {e}", file=sys.stderr)
        return []
