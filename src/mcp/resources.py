"""MCP Resources Implementation.

Resources provide AI agents with direct access to Android device data.
Each resource URI maps to real device information via ADB.
"""

import json
import re
from typing import Optional
from src.utils.adb_utils import get_adb_devices
from src.utils.adb_path import get_adb_path
import subprocess


def _run_adb_command(device: str, cmd: list) -> str:
    """Helper to run ADB commands."""
    try:
        adb_path = get_adb_path()
        full_cmd = [adb_path, '-s', device] + cmd
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False
        )
        return result.stdout
    except Exception as e:
        return f"Error: {str(e)}"


async def read_logcat_device_resource(device_serial: str) -> str:
    """
    Read current logcat stream from a specific device.
    
    URI: logcat://device/{device_serial}
    """
    try:
        output = _run_adb_command(device_serial, ['logcat', '-d', '-v', 'threadtime', '-n', '50'])
        
        lines = []
        for line in output.split('\n'):
            if line.strip():
                lines.append(line)
        
        return json.dumps({
            "resource": f"logcat://device/{device_serial}",
            "device": device_serial,
            "type": "logcat_stream",
            "line_count": len(lines),
            "lines": lines
        }, ensure_ascii=False)
    except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)


async def read_android_devices_resource() -> str:
    """
    Read list of all connected Android devices.
    
    URI: android://devices
    """
    try:
        serials = get_adb_devices()
        
        devices = []
        for serial in serials:
            try:
                model_output = _run_adb_command(serial, ['shell', 'getprop', 'ro.product.model'])
                model = model_output.strip() if model_output and not model_output.startswith('Error') else 'Unknown'
                
                android_version_output = _run_adb_command(serial, ['shell', 'getprop', 'ro.build.version.release'])
                android_version = android_version_output.strip() if android_version_output and not android_version_output.startswith('Error') else 'Unknown'
                
                devices.append({
                    "serial": serial,
                    "model": model,
                    "android_version": android_version,
                    "status": "device"
                })
            except Exception:
                devices.append({
                    "serial": serial,
                    "model": "Unknown",
                    "android_version": "Unknown",
                    "status": "device"
                })
        
        return json.dumps({
            "resource": "android://devices",
            "type": "device_list",
            "count": len(devices),
            "devices": devices
        }, ensure_ascii=False)
    except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)


async def read_android_packages_resource(device_serial: str) -> str:
    """
    Read list of installed packages on a device.
    
    URI: android://packages/{device_serial}
    """
    try:
        pm_output = _run_adb_command(device_serial, ['shell', 'pm', 'list', 'packages', '-3'])
        
        packages = []
        for line in pm_output.split('\n'):
            if line.startswith('package:'):
                package_name = line.replace('package:', '').strip()
                packages.append(package_name)
        
        return json.dumps({
            "resource": f"android://packages/{device_serial}",
            "device": device_serial,
            "type": "package_list",
            "count": len(packages),
            "packages": packages
        }, ensure_ascii=False)
    except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)


async def read_android_processes_resource(device_serial: str) -> str:
    """
    Read list of running processes on a device.
    
    URI: android://processes/{device_serial}
    """
    try:
        ps_output = _run_adb_command(device_serial, ['shell', 'ps'])
        
        processes = []
        lines = ps_output.split('\n')
        
        for line in lines[1:]:
            if not line.strip():
                continue
            
            parts = line.split()
            if len(parts) >= 9:
                try:
                    processes.append({
                        "user": parts[0],
                        "pid": int(parts[1]),
                        "ppid": int(parts[2]),
                        "name": ' '.join(parts[8:])
                    })
                except (ValueError, IndexError):
                    continue
        
        return json.dumps({
            "resource": f"android://processes/{device_serial}",
            "device": device_serial,
            "type": "process_list",
            "count": len(processes),
            "processes": processes
        }, ensure_ascii=False)
    except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
