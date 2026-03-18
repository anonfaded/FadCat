"""
FadCat MCP Tools - Implementation of all 20 MCP tools.

These tools connect directly to Android Debug Bridge (ADB) and logcat to provide
AI agents with real-time access to device debugging information.

Cross-platform support: Works on macOS, Linux, and Windows.
"""

import subprocess
import json
import re
import tempfile
import shlex
import urllib.parse
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastmcp import Context

from src.utils.adb_utils import get_adb_devices
from src.utils.adb_path import get_adb_path
from src.mcp.models import (
    LogLine, DeviceInfo, ProcessInfo, PackageInfo,
    ErrorAnalysis, StackTraceInfo, PerformanceReport,
    PerformanceMetrics,
    MemoryAllocation
)


def _run_adb_command(device: str, cmd: List[str]) -> str:
    """
    Run an ADB command on a specific device and return output.
    
    Cross-platform: Uses get_adb_path() for correct ADB binary location
    
    Args:
        device: Device serial
        cmd: Command list (without 'adb' and device selector)
    
    Returns:
        Command output as string
    """
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
    except subprocess.TimeoutExpired:
        return f"Error: ADB command timeout on device {device}"
    except Exception as e:
        return f"Error: {str(e)}"


async def _ctx_info(ctx: Optional[Context], message: str) -> None:
    try:
        if ctx:
            await ctx.info(message)
    except Exception:
        pass


async def _ctx_warning(ctx: Optional[Context], message: str) -> None:
    try:
        if ctx:
            await ctx.warning(message)
    except Exception:
        pass


async def _ctx_error(ctx: Optional[Context], message: str) -> None:
    try:
        if ctx:
            await ctx.error(message)
    except Exception:
        pass


def _run_adb_shell(device: str, command: str) -> str:
    """Run an ADB shell command via sh -c to allow pipes and globbing."""
    return _run_adb_command(device, ['shell', 'sh', '-c', command])


def _shell_quote(value: str) -> str:
    return shlex.quote(value)


def _parse_logcat_line(line: str) -> Optional[LogLine]:
    """
    Parse a logcat line into a LogLine model.
    
    Logcat format: timestamp level tag[pid]: message
    """
    if not line or not line.strip():
        return None
    
    # Try to parse logcat format
    # E.g.: 03-13 10:42:15.123  1234  1234 E ActivityManager: Error message
    # Or long format: 03-13 10:42:15.123  1234  1234 WARNING ActivityManager: Error message
    pattern = r'^(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})\s+(\d+)\s+(\d+)\s+([VDIWEF]|VERBOSE|DEBUG|INFO|WARNING|ERROR|FATAL)\s+([^:]+):\s*(.*)$'
    
    match = re.match(pattern, line)
    if not match:
        return None
    
    timestamp, pid, tid, level, tag, message = match.groups()
    
    # Map log levels to single letters (handle both full words and letters)
    level_map = {
        'VERBOSE': 'V', 'DEBUG': 'D', 'INFO': 'I', 'WARNING': 'W', 'ERROR': 'E', 'FATAL': 'F',
        'V': 'V', 'D': 'D', 'I': 'I', 'W': 'W', 'E': 'E', 'F': 'F'
    }
    level = level_map.get(level, level)
    
    return LogLine(
        timestamp=timestamp,
        level=level,
        tag=tag.strip(),
        pid=int(pid),
        tid=int(tid),
        message=message.strip()
    )


FADCAM_KNOWN_PACKAGES = [
    "com.fadcam",
    "com.fadcam.beta",
    "com.fadcam.proplus",
    "com.fadcam.notes",
    "com.fadcam.calc",
    "com.fadcam.weather",
]

FADCAM_FILE_PREFIXES = (
    "FadCam_",
    "FadShot_",
    "Faditor_",
    "DualCam_",
    "Stream_",
    "Screen_",
    "FadRec_",
)


def _list_storage_volumes(device: str) -> List[str]:
    volumes_output = _run_adb_command(device, ['shell', 'ls', '/storage'])
    volumes = []
    for line in volumes_output.split('\n'):
        name = line.strip()
        if not name or name in {"emulated", "self"}:
            continue
        volumes.append(name)
    return volumes


def _list_fadcam_packages(device: str) -> List[str]:
    packages_output = _run_adb_command(device, ['shell', 'pm', 'list', 'packages'])
    found = []
    for line in packages_output.split('\n'):
        line = line.strip()
        if line.startswith('package:'):
            pkg = line.split(':', 1)[1].strip()
            if pkg.startswith('com.fadcam'):
                found.append(pkg)
    # Ensure known variants are included if installed but not listed for any reason
    for pkg in FADCAM_KNOWN_PACKAGES:
        if pkg not in found:
            # Check existence
            check = _run_adb_command(device, ['shell', 'pm', 'list', 'packages', pkg])
            if f"package:{pkg}" in check:
                found.append(pkg)
    return found


def _normalize_package_list(device: str, package: str) -> List[str]:
    if not package or package in {"all", "*", "auto"}:
        return _list_fadcam_packages(device)
    return [package]


def _path_exists(device: str, path: str) -> bool:
    ls_cmd = _run_adb_command(device, ['shell', 'ls', '-la', path])
    return "No such file or directory" not in ls_cmd and "Permission denied" not in ls_cmd


def _saf_uri_to_path(uri: Optional[str]) -> Optional[str]:
    if not uri:
        return None
    try:
        parsed = urllib.parse.urlparse(uri)
        if "/tree/" not in parsed.path:
            return None
        tree_part = parsed.path.split("/tree/")[1]
        decoded = urllib.parse.unquote(tree_part)
        if ":" not in decoded:
            return None
        volume, rel_path = decoded.split(":", 1)
        rel_path = rel_path.lstrip("/")
        if volume == "primary":
            root = "/storage/emulated/0"
        else:
            root = f"/storage/{volume}"
        return f"{root}/{rel_path}" if rel_path else root
    except Exception:
        return None


def _is_fadcam_layout(device: str, base_path: str) -> bool:
    for name in ("Camera", "FadShot", "Screen", "Stream", "Faditor", "Dual", "Forensics"):
        if _path_exists(device, f"{base_path}/{name}"):
            return True
    return False


def _count_media_files(device: str, path: str, maxdepth: Optional[int] = None,
                       fadcam_only: bool = False) -> int:
    qpath = _shell_quote(path)
    if fadcam_only and maxdepth == 1:
        return len(_list_fadcam_files_shallow(device, path))
    if maxdepth == 1:
        return len(_list_media_files_shallow(device, path, fadcam_only=fadcam_only))

    cmd = f"find {qpath} "
    if maxdepth is not None:
        cmd += f"-maxdepth {maxdepth} "
    cmd += "-type f \\( -name '*.mp4' -o -name '*.jpg' \\)"
    if fadcam_only:
        cmd += " | grep -E '/(FadCam_|FadShot_|Faditor_|DualCam_|Stream_|Screen_|FadRec_)[^/]*\\.(mp4|jpg)$'"
    cmd += " | wc -l"
    output = _run_adb_shell(device, cmd)
    try:
        return int(output.strip())
    except Exception:
        if fadcam_only:
            fallback = _run_adb_shell(
                device,
                f"find {qpath} -type f \\( -name '*.mp4' -o -name '*.jpg' \\) | wc -l"
            )
            try:
                return int(fallback.strip())
            except Exception:
                return 0
        return 0


def _find_media_files(device: str, path: str, fadcam_only: bool = False,
                      maxdepth: Optional[int] = None) -> List[str]:
    qpath = _shell_quote(path)
    if fadcam_only and maxdepth == 1:
        return _list_fadcam_files_shallow(device, path)
    if maxdepth == 1:
        return _list_media_files_shallow(device, path, fadcam_only=fadcam_only)

    cmd = f"find {qpath} "
    if maxdepth is not None:
        cmd += f"-maxdepth {maxdepth} "
    cmd += "-type f \\( -name '*.mp4' -o -name '*.jpg' \\)"
    if fadcam_only:
        cmd += " | grep -E '/(FadCam_|FadShot_|Faditor_|DualCam_|Stream_|Screen_|FadRec_)[^/]*\\.(mp4|jpg)$'"
    output = _run_adb_shell(device, cmd)
    if "No such file" in output or "Permission denied" in output:
        return []
    return [line.strip() for line in output.split('\n') if line.strip()]


def _is_fadcam_filename(filename: str) -> bool:
    return filename.startswith(FADCAM_FILE_PREFIXES)


def _list_fadcam_files_shallow(device: str, path: str) -> List[str]:
    qpath = _shell_quote(path)
    output = _run_adb_shell(device, f"ls -1p {qpath}")
    if "No such file" in output or "Permission denied" in output:
        return []
    files = []
    for line in output.split('\n'):
        name = line.strip()
        if not name or name.endswith('/'):
            continue
        if not (name.endswith('.mp4') or name.endswith('.jpg')):
            continue
        if not _is_fadcam_filename(name):
            continue
        files.append(f"{path.rstrip('/')}/{name}")
    return files


def _list_media_files_shallow(device: str, path: str,
                              fadcam_only: bool = False) -> List[str]:
    qpath = _shell_quote(path)
    output = _run_adb_shell(device, f"ls -1p {qpath}")
    if "No such file" in output or "Permission denied" in output:
        return []
    files = []
    for line in output.split('\n'):
        name = line.strip()
        if not name or name.endswith('/'):
            continue
        if not (name.endswith('.mp4') or name.endswith('.jpg')):
            continue
        if fadcam_only and not _is_fadcam_filename(name):
            continue
        files.append(f"{path.rstrip('/')}/{name}")
    return files


def _list_media_files_from_ls(device: str, path: str) -> List[str]:
    ls_cmd = _run_adb_command(device, ['shell', 'ls', '-la', path])
    if "No such file" in ls_cmd or "Permission denied" in ls_cmd:
        return []
    files = []
    for line in ls_cmd.split('\n'):
        line = line.strip()
        if not line or line.startswith('total') or line.startswith('d'):
            continue
        parts = line.split()
        if len(parts) < 8:
            continue
        filename = parts[-1]
        if not (filename.endswith('.mp4') or filename.endswith('.jpg')):
            continue
        files.append(f"{path.rstrip('/')}/{filename}")
    return files


def _list_media_entries_from_ls(device: str, path: str,
                                fadcam_only: bool = False) -> List[Dict[str, Optional[object]]]:
    ls_cmd = _run_adb_command(device, ['shell', 'ls', '-l', path])
    if "No such file" in ls_cmd or "Permission denied" in ls_cmd:
        return []
    entries: List[Dict[str, Optional[object]]] = []
    for line in ls_cmd.split('\n'):
        line = line.strip()
        if not line or line.startswith('total') or line.startswith('d'):
            continue
        parts = line.split()
        if len(parts) < 7:
            continue
        filename = parts[-1]
        if not (filename.endswith('.mp4') or filename.endswith('.jpg')):
            continue
        if fadcam_only and not _is_fadcam_filename(filename):
            continue
        size_bytes = None
        if len(parts) >= 5 and parts[4].isdigit():
            try:
                size_bytes = int(parts[4])
            except Exception:
                size_bytes = None
        entries.append({
            "filename": filename,
            "path": f"{path.rstrip('/')}/{filename}",
            "size_bytes": size_bytes
        })
    return entries


def _build_metadata_from_filename(file_path: str, size_bytes: Optional[int]) -> Dict[str, object]:
    filename = file_path.split('/')[-1]
    metadata = {
        "file_path": file_path,
        "filename": filename,
        "size_bytes": size_bytes or 0,
        "modified_timestamp": 0,
        "created_date": None,
        "file_type": "unknown"
    }
    if filename.endswith('.mp4'):
        metadata["file_type"] = "video"
    elif filename.endswith('.jpg'):
        metadata["file_type"] = "image"

    if filename.startswith('FadCam_') and len(filename) >= 19:
        date_str = filename[7:7+15]  # YYYYMMDD_HHMMSS
        try:
            from datetime import datetime
            dt = datetime.strptime(date_str, '%Y%m%d_%H%M%S')
            metadata["created_date"] = dt.isoformat()
        except Exception:
            pass
    elif filename.startswith('FadShot_') and len(filename) >= 23:
        date_str = filename[14:14+15]  # YYYYMMDD_HHMMSS
        try:
            from datetime import datetime
            dt = datetime.strptime(date_str, '%Y%m%d_%H%M%S')
            metadata["created_date"] = dt.isoformat()
        except Exception:
            pass
    elif "/Forensics/Snapshots/" in file_path and filename.endswith(".jpg"):
        metadata.update(_parse_forensics_filename(file_path))

    return metadata


def _find_fadcam_file_matches(device: str, base_path: str, filename: str) -> List[str]:
    candidates = [
        f"{base_path}/Camera/Back",
        f"{base_path}/Camera/Front",
        f"{base_path}/Camera/Dual",
        f"{base_path}/Dual",
        f"{base_path}/Screen",
        f"{base_path}/Stream",
        f"{base_path}/Faditor/Converted",
        f"{base_path}/Faditor/Merge",
        f"{base_path}/FadShot/Back",
        f"{base_path}/FadShot/Selfie",
        f"{base_path}/FadShot/FadRec",
        base_path
    ]
    matches: List[str] = []
    for directory in candidates:
        if not _path_exists(device, directory):
            continue
        candidate = f"{directory.rstrip('/')}/{filename}"
        if _path_exists(device, candidate):
            matches.append(candidate)

    if not matches and filename.endswith(".jpg"):
        forensics_root = f"{base_path}/Forensics/Snapshots"
        if _path_exists(device, forensics_root):
            qpath = _shell_quote(forensics_root)
            qname = _shell_quote(filename)
            find_cmd = f"find {qpath} -maxdepth 4 -type f -name {qname} | head -n 5"
            output = _run_adb_shell(device, find_cmd)
            if "No such file" not in output and "Permission denied" not in output:
                matches.extend([line.strip() for line in output.split('\n') if line.strip()])

    return matches


def _resolve_output_dir(path_str: str) -> str:
    from pathlib import Path
    raw = Path(path_str)
    if raw.is_absolute():
        return str(raw)
    repo_root = Path(__file__).resolve().parents[2]
    return str((repo_root / raw).resolve())


def _resolve_preserved_local_path(output_dir: str,
                                  file_path: str,
                                  base_path: Optional[str]) -> str:
    from pathlib import Path
    output_root = Path(output_dir)
    rel_path: Optional[str] = None
    if base_path and file_path.startswith(base_path.rstrip('/') + '/'):
        rel_path = file_path[len(base_path.rstrip('/') + '/'):]
    else:
        marker = "/FadCam/"
        if marker in file_path:
            rel_path = file_path.split(marker, 1)[1]
    if not rel_path:
        rel_path = file_path.split('/')[-1]
    return str((output_root / rel_path).resolve())


def _find_media_files_limited(device: str, path: str, limit: int,
                              fadcam_only: bool = False,
                              maxdepth: Optional[int] = None) -> List[str]:
    if limit <= 0:
        return []
    if fadcam_only and maxdepth == 1:
        return _list_fadcam_files_shallow(device, path)[:limit]
    if maxdepth == 1:
        return _list_media_files_shallow(device, path, fadcam_only=fadcam_only)[:limit]

    qpath = _shell_quote(path)
    cmd = f"find {qpath} "
    if maxdepth is not None:
        cmd += f"-maxdepth {maxdepth} "
    cmd += "-type f \\( -name '*.mp4' -o -name '*.jpg' \\)"
    if fadcam_only:
        cmd += " | grep -E '/(FadCam_|FadShot_|Faditor_|DualCam_|Stream_|Screen_|FadRec_)[^/]*\\.(mp4|jpg)$'"
    cmd += f" | head -n {int(limit)}"
    output = _run_adb_shell(device, cmd)
    if "No such file" in output or "Permission denied" in output:
        return []
    return [line.strip() for line in output.split('\n') if line.strip()]

def _read_fadcam_prefs(device: str, package: str) -> Dict[str, Optional[str]]:
    storage_mode = None
    custom_storage_uri = None
    try:
        prefs_cmd = _run_adb_command(device, ['shell', 'run-as', package, 'cat', 'shared_prefs/app_prefs.xml'])
        if "Permission denied" in prefs_cmd or "No such file" in prefs_cmd:
            return {"storage_mode": None, "custom_storage_uri": None}
        mode_match = re.search(r'name=\"storage_mode\"[^>]*>([^<]+)<', prefs_cmd)
        if mode_match:
            storage_mode = mode_match.group(1).strip()
        uri_match = re.search(r'name=\"custom_storage_uri\"[^>]*>([^<]+)<', prefs_cmd)
        if uri_match:
            custom_storage_uri = uri_match.group(1).strip()
    except Exception:
        pass
    return {"storage_mode": storage_mode, "custom_storage_uri": custom_storage_uri}


def _check_path_stats(device: str, path: str, fadcam_only: bool = False,
                      maxdepth: Optional[int] = None,
                      include_counts: bool = True,
                      include_size: bool = False) -> Dict[str, Any]:
    stats = {"exists": False, "file_count": None, "total_size_bytes": None}
    ls_cmd = _run_adb_command(device, ['shell', 'ls', '-la', path])
    if "No such file or directory" in ls_cmd or "Permission denied" in ls_cmd:
        return stats
    stats["exists"] = True
    if include_counts:
        stats["file_count"] = _count_media_files(device, path, maxdepth=maxdepth, fadcam_only=fadcam_only)
    if include_size:
        du_cmd = _run_adb_command(device, ['shell', 'du', '-sk', path])
        try:
            size_kb = int(du_cmd.strip().split()[0])
            stats["total_size_bytes"] = size_kb * 1024
        except Exception:
            pass
    return stats


def _parse_forensics_filename(path: str) -> Dict[str, Optional[str]]:
    result = {"forensics_date": None, "media_uid": None, "event_uid": None, "timeline_ms": None, "snapshot_uid": None}
    parts = path.split('/')
    try:
        idx = parts.index('Snapshots')
        date_part = parts[idx + 1]
        media_uid = parts[idx + 2]
        filename = parts[idx + 3]
        name = filename.rsplit('.', 1)[0]
        if '_' in name:
            event_uid, timeline_ms, snapshot_uid = name.split('_', 2)
        else:
            event_uid = name
            timeline_ms = None
            snapshot_uid = None
        result.update({
            "forensics_date": date_part,
            "media_uid": media_uid,
            "event_uid": event_uid,
            "timeline_ms": timeline_ms,
            "snapshot_uid": snapshot_uid
        })
    except Exception:
        pass
    return result


def _resolve_base_path_from_hint(storage_info: Dict[str, Any],
                                 storage_hint: Optional[str]) -> Dict[str, Any]:
    if not storage_hint:
        return {"base_path": None, "matches": []}
    hint = storage_hint.strip()
    if hint.startswith("/"):
        return {"base_path": hint, "matches": [hint]}

    hint_key = hint.lower().replace(" ", "_")
    type_targets = {
        "internal": ["default_internal"],
        "default_internal": ["default_internal"],
        "internal_default": ["default_internal"],
        "sd_internal": ["sd_internal"],
        "shared_download": ["shared_default"],
        "download": ["shared_default", "shared_sd"],
        "shared_dcim": ["shared_default"],
        "dcim": ["shared_default", "shared_sd"],
        "sd_download": ["shared_sd"],
        "sd_dcim": ["shared_sd"],
        "custom": ["custom_root"],
        "custom_root": ["custom_root"],
        "custom_fadcam": ["custom_fadcam_subdir"],
    }
    allowed_types = type_targets.get(hint_key)
    if not allowed_types:
        return {"base_path": None, "matches": []}

    matches = []
    for pkg_info in storage_info.get("packages", []):
        for entry in pkg_info.get("storage_entries", []):
            if entry.get("type") not in allowed_types:
                continue
            base = entry.get("base_path")
            if not base:
                continue
            # Refine download/dcim hints by suffix
            if hint_key in {"download", "shared_download", "sd_download"} and "/Download/" not in base:
                continue
            if hint_key in {"dcim", "shared_dcim", "sd_dcim"} and "/DCIM/" not in base:
                continue
            matches.append(base)

    if len(matches) == 1:
        return {"base_path": matches[0], "matches": matches}
    return {"base_path": None, "matches": matches}


async def _resolve_or_elicit_base_path(
    ctx: Optional[Context],
    storage_info: Dict[str, Any],
    storage_hint: Optional[str],
    base_path: Optional[str],
    prompt_prefix: str
) -> Dict[str, Any]:
    if base_path:
        return {"base_path": base_path, "response": None}

    if storage_hint:
        resolved = _resolve_base_path_from_hint(storage_info, storage_hint)
        if resolved["base_path"]:
            return {"base_path": resolved["base_path"], "response": None}
        if resolved["matches"]:
            if ctx and hasattr(ctx, "elicit"):
                try:
                    choice = await ctx.elicit(
                        f"{prompt_prefix} Multiple locations match '{storage_hint}'. Choose one base_path.",
                        response_type=resolved["matches"]
                    )
                    if getattr(choice, "action", None) == "accept":
                        return {"base_path": choice.data, "response": None}
                except Exception:
                    pass
            await _ctx_warning(ctx, "Multiple locations match storage_hint. Asking user to choose.")
            return {
                "base_path": None,
                "response": {
                    "message": "Multiple locations match storage_hint. Choose one base_path.",
                    "storage_hint": storage_hint,
                    "available_base_paths": resolved["matches"],
                    "requires_selection": True
                }
            }

    return {"base_path": None, "response": None}


async def _elicit_base_path(
    ctx: Optional[Context],
    base_paths: List[str],
    prompt_prefix: str
) -> Optional[str]:
    if not (ctx and hasattr(ctx, "elicit") and base_paths):
        return None
    try:
        choice = await ctx.elicit(
            f"{prompt_prefix} Select a base_path to continue.",
            response_type=base_paths
        )
        if getattr(choice, "action", None) == "accept":
            return choice.data
    except Exception:
        return None
    return None

# ============================================================================
# Tool Implementations - All 20 Tools
# ============================================================================

async def impl_get_devices(ctx: Optional[Context]) -> str:
    """
    Get list of connected Android devices with intelligent selection.
    
    Returns JSON list of DeviceInfo objects, ordered by priority:
    1. Connected real devices
    2. Connected emulators
    3. If multiple of same type, returns all with 'primary' flag on first
    """
    try:
        serials = get_adb_devices()
        
        devices = []
        real_devices = []
        emulators = []
        
        for serial in serials:
            try:
                # Get device properties
                model_output = _run_adb_command(serial, ['shell', 'getprop', 'ro.product.model'])
                model = model_output.strip() if model_output and not model_output.startswith('Error') else 'Unknown'
                
                manufacturer_output = _run_adb_command(serial, ['shell', 'getprop', 'ro.product.manufacturer'])
                manufacturer = manufacturer_output.strip() if manufacturer_output and not manufacturer_output.startswith('Error') else 'Unknown'
                
                product_output = _run_adb_command(serial, ['shell', 'getprop', 'ro.product.device'])
                product = product_output.strip() if product_output and not product_output.startswith('Error') else None
                
                is_emulator = "emulator" in serial.lower()
                
                device_dict = {
                    "serial": serial,
                    "name": f"{manufacturer} {model}",
                    "status": "device",
                    "model": model,
                    "product": product,
                    "device": product,
                    "usb_port": None,
                    "is_emulator": is_emulator,
                    "is_primary": False  # Will be set below
                }
                
                if is_emulator:
                    emulators.append(device_dict)
                else:
                    real_devices.append(device_dict)
                    
            except Exception as e:
                # Still add device even if we can't get properties
                device_dict = {
                    "serial": serial,
                    "name": "Unknown",
                    "status": "offline",
                    "model": None,
                    "product": None,
                    "device": None,
                    "usb_port": None,
                    "is_emulator": "emulator" in serial.lower(),
                    "is_primary": False
                }
                if device_dict["is_emulator"]:
                    emulators.append(device_dict)
                else:
                    real_devices.append(device_dict)
        
        # Intelligent ordering: real devices first, then emulators
        # Mark first device as primary
        ordered_devices = real_devices + emulators
        if ordered_devices:
            ordered_devices[0]["is_primary"] = True
        
        devices = ordered_devices
        
        selected_device = devices[0]["serial"] if devices else None
        if ctx and hasattr(ctx, "elicit") and len(devices) > 1:
            try:
                options = [d["serial"] for d in devices]
                choice = await ctx.elicit(
                    "Multiple devices detected. Select one device to use for this session.",
                    response_type=options
                )
                if getattr(choice, "action", None) == "accept":
                    selected_device = choice.data
            except Exception:
                pass

        return json.dumps({
            "devices": devices, 
            "count": len(devices),
            "primary_device": devices[0]["serial"] if devices else None,
            "selected_device": selected_device,
            "has_real_devices": len(real_devices) > 0,
            "has_emulators": len(emulators) > 0
        })
    except Exception as e:
        return json.dumps({"error": str(e), "devices": []})


async def impl_get_logcat_stream(ctx: Optional[Context], device: str, package: Optional[str] = None, 
                                  level: str = "I", lines: int = 100) -> str:
    """
    Get logcat stream from a device with optional filters.
    
    Args:
        device: Device serial
        package: Optional package name to filter by
        level: Minimum log level (V/D/I/W/E/F)
        lines: Number of lines to retrieve
    
    Returns:
        JSON with LogLine objects
    """
    try:
        # Get logcat output
        logcat_output = _run_adb_command(device, ['logcat', '-d', '-v', 'threadtime', '-n', str(lines)])
        
        log_lines = []
        for line in logcat_output.split('\n'):
            if not line.strip():
                continue
            
            log_obj = _parse_logcat_line(line)
            if log_obj:
                # Filter by package if specified
                if package and package.lower() not in line.lower():
                    continue
                log_lines.append(log_obj.model_dump())
        
        return json.dumps({
            "device": device,
            "package": package,
            "level": level,
            "count": len(log_lines),
            "logs": log_lines
        })
    except Exception as e:
        return json.dumps({"error": str(e), "logs": []})


async def impl_search_logs(ctx: Optional[Context], query: str, tag_filter: Optional[str] = None,
                           level_filter: Optional[str] = None, limit: int = 50) -> str:
    """
    Search in logcat history across all devices.
    
    Args:
        query: Search query string
        tag_filter: Optional tag to filter by
        level_filter: Optional log level to filter by  
        limit: Maximum number of results
    
    Returns:
        JSON with matched LogLine objects
    """
    try:
        results = []
        serials = get_adb_devices()
        
        for device in serials:
            logcat_output = _run_adb_command(device, ['logcat', '-d', '-v', 'threadtime'])
            
            for line in logcat_output.split('\n'):
                if not line.strip() or len(results) >= limit:
                    continue
                
                if query.lower() not in line.lower():
                    continue
                
                log_obj = _parse_logcat_line(line)
                if log_obj:
                    if tag_filter and tag_filter not in log_obj.tag:
                        continue
                    if level_filter and level_filter.upper() != log_obj.level[0]:
                        continue
                    results.append(log_obj.model_dump())
        
        return json.dumps({
            "query": query,
            "tag_filter": tag_filter,
            "level_filter": level_filter,
            "count": len(results),
            "results": results[:limit]
        })
    except Exception as e:
        return json.dumps({"error": str(e), "results": []})


async def impl_filter_by_level(ctx: Optional[Context], device: str, level: str) -> str:
    """
    Filter current logcat by severity level.
    
    Args:
        device: Device serial
        level: Log level (V/D/I/W/E/F)
    
    Returns:
        JSON with filtered LogLine objects
    """
    try:
        logcat_output = _run_adb_command(device, ['logcat', '-d', '-v', 'threadtime'])
        
        level_priority = {'V': 0, 'D': 1, 'I': 2, 'W': 3, 'E': 4, 'F': 5}
        min_priority = level_priority.get(level[0].upper(), 2)
        
        log_lines = []
        for line in logcat_output.split('\n'):
            if not line.strip():
                continue
            
            log_obj = _parse_logcat_line(line)
            if log_obj:
                obj_priority = level_priority.get(log_obj.level[0].upper(), 2)
                if obj_priority >= min_priority:
                    log_lines.append(log_obj.model_dump())
        
        return json.dumps({
            "device": device,
            "filter_level": level,
            "count": len(log_lines),
            "logs": log_lines
        })
    except Exception as e:
        return json.dumps({"error": str(e), "logs": []})


async def impl_get_app_processes(ctx: Optional[Context], device: str, package: str) -> str:
    """
    Get running processes for an app.
    
    Args:
        device: Device serial
        package: Package name to filter by
    
    Returns:
        JSON with ProcessInfo objects
    """
    try:
        ps_output = _run_adb_command(device, ['shell', 'ps'])
        
        processes = []
        lines = ps_output.split('\n')
        
        # Skip header line
        for line in lines[1:]:
            if not line.strip():
                continue
            
            parts = line.split()
            if len(parts) < 9:
                continue
            
            user, pid_str, ppid_str, vsize_str, rss_str = parts[0], parts[1], parts[2], parts[3], parts[4]
            proc_name = ' '.join(parts[8:])
            
            if package not in proc_name:
                continue
            
            try:
                process = ProcessInfo(
                    pid=int(pid_str),
                    uid=int(ppid_str),
                    name=proc_name,
                    package=package
                )
                processes.append(process.model_dump())
            except (ValueError, IndexError):
                continue
        
        return json.dumps({
            "device": device,
            "package": package,
            "count": len(processes),
            "processes": processes
        })
    except Exception as e:
        return json.dumps({"error": str(e), "processes": []})


async def impl_get_connected_packages(ctx: Optional[Context], device: str) -> str:
    """
    Get list of installed packages on a device.
    Returns only third-party packages (user-installed).
    
    Args:
        device: Device serial
    
    Returns:
        JSON with PackageInfo objects
    """
    try:
        pm_output = _run_adb_command(device, ['shell', 'pm', 'list', 'packages', '-3'])
        
        packages = []
        for line in pm_output.split('\n'):
            if line.startswith('package:'):
                package_name = line.replace('package:', '').strip()
                package_dict = {
                    "package_name": package_name,
                    "version_name": None,
                    "version_code": None,
                    "is_system": False,
                    "is_running": False
                }
                packages.append(package_dict)
        
        return json.dumps({
            "device": device,
            "count": len(packages),
            "packages": packages
        })
    except Exception as e:
        return json.dumps({"error": str(e), "packages": []})


async def impl_parse_stacktrace(ctx: Optional[Context], trace: str) -> str:
    """
    Parse Java/Kotlin stack trace and extract key information.
    
    Args:
        trace: Stack trace text
    
    Returns:
        JSON with StackTraceInfo object
    """
    try:
        lines = trace.split('\n')
        exception_type = "Unknown Exception"
        message = ""
        file_info = None
        line_number = None
        method_name = None
        
        # Find exception line (usually first line or line with "Exception")
        for line in lines:
            if 'Exception' in line or 'Error' in line:
                exception_type = line.strip()
                if ':' in exception_type:
                    exception_type, message = exception_type.split(':', 1)
                    exception_type = exception_type.strip()
                    message = message.strip()
                break
        
        # Extract stack frames with details
        frames = []
        for line in lines:
            if 'at ' in line:
                # Parse frame: at com.example.Class.method(File.java:123)
                frame_text = line.strip()
                frames.append({"frame": frame_text})
                
                # Extract file and line from first frame
                if not file_info and '(' in frame_text and ')' in frame_text:
                    paren_content = frame_text[frame_text.rfind('(')+1:frame_text.rfind(')')]
                    if ':' in paren_content:
                        file_info, line_str = paren_content.rsplit(':', 1)
                        try:
                            line_number = int(line_str)
                        except:
                            pass
                
                # Extract method name
                if not method_name and '(' in frame_text:
                    method_part = frame_text[:frame_text.rfind('(')]
                    if '.' in method_part:
                        method_name = method_part.split('.')[-1]
        
        stack_trace = StackTraceInfo(
            exception_type=exception_type,
            message=message,
            file=file_info,
            line=line_number,
            method=method_name,
            stack_frames=frames
        )
        
        return json.dumps(stack_trace.model_dump())
    except Exception as e:
        return json.dumps({"error": str(e)})


async def impl_detect_error_type(ctx: Optional[Context], logcat: str) -> str:
    """
    Detect error type from logcat output (Crash, ANR, OOM, etc).
    
    Args:
        logcat: Logcat text
    
    Returns:
        JSON with ErrorAnalysis object
    """
    try:
        error_type = "UNKNOWN"
        severity = "LOW"
        root_cause = "Unable to determine root cause"
        affected_package = None
        
        if 'ANR in ' in logcat or 'Application Not Responding' in logcat:
            error_type = "ANR"
            severity = "HIGH"
            root_cause = "Application is not responding - likely blocked by long operation or deadlock"
        elif 'OutOfMemoryError' in logcat or 'Native crash' in logcat:
            error_type = "OOM"
            severity = "CRITICAL"
            root_cause = "Application ran out of memory - heap exhausted or memory leak"
        elif 'FATAL EXCEPTION' in logcat or 'AndroidRuntime' in logcat:
            error_type = "CRASH"
            severity = "CRITICAL"
            root_cause = "Uncaught exception causing app crash"
        elif 'NullPointerException' in logcat:
            error_type = "NPE"
            severity = "HIGH"
            root_cause = "Null pointer exception - attempting to use null reference"
        elif 'SecurityException' in logcat:
            error_type = "SECURITY"
            severity = "HIGH"
            root_cause = "Security permission violation or attempted access denied"
        elif 'IOException' in logcat:
            error_type = "IO"
            severity = "MEDIUM"
            root_cause = "Input/output error - file, network, or disk operation failed"
        elif 'Timeout' in logcat or 'TIMEOUT' in logcat:
            error_type = "TIMEOUT"
            severity = "MEDIUM"
            root_cause = "Operation exceeded time limit - network or blocking operation"
        
        # Extract package name from Process: line
        for line in logcat.split('\n'):
            if 'Process:' in line or 'package=' in line:
                # Extract package name
                if 'Process:' in line:
                    parts = line.split('Process:')
                    if len(parts) > 1:
                        affected_package = parts[1].split(',')[0].strip()
        
        error_analysis = ErrorAnalysis(
            error_type=error_type,
            severity=severity,
            root_cause=root_cause,
            affected_package=affected_package,
            suggested_fix=f"Review logcat output for {error_type} details and check recent code changes"
        )
        
        return json.dumps(error_analysis.model_dump())
    except Exception as e:
        return json.dumps({"error": str(e)})


async def impl_analyze_performance(ctx: Optional[Context], device: str, package: str, duration: int = 10) -> str:
    """
    Analyze app performance (memory only) for specific package.
    
    Args:
        device: Device serial
        package: Package name to profile
        duration: Duration to monitor in seconds
    
    Returns:
        JSON with PerformanceReport object
    """
    try:
        dumpsys_output = _run_adb_command(device, ['shell', 'dumpsys', 'meminfo', package])

        total_pss_kb = None
        for line in dumpsys_output.split('\n'):
            if line.strip().startswith("TOTAL"):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        total_pss_kb = int(parts[1])
                    except Exception:
                        pass
                break

        metric = PerformanceMetrics(
            timestamp="",
            memory_used=total_pss_kb,
            memory_total=None,
            fps=None,
            jank_count=None
        )

        total_pss_mb = None
        if total_pss_kb is not None:
            total_pss_mb = round(total_pss_kb / 1024.0, 2)

        report = PerformanceReport(
            device=device,
            duration_seconds=duration,
            metrics=[metric],
            peak_memory=total_pss_kb,
            min_fps=None,
            avg_fps=None,
            jank_frames=None,
            analysis=(
                f"Profiled {package} for {duration}s using dumpsys meminfo. "
                f"TOTAL PSS: {total_pss_kb} KB"
                + (f" ({total_pss_mb} MB)" if total_pss_mb is not None else "")
                + ". CPU/FPS are not available via adb in this mode."
            )
        )
        
        return json.dumps(report.model_dump())
    except Exception as e:
        return json.dumps({"error": str(e)})

async def impl_clear_logcat(ctx: Optional[Context], device: str) -> str:
    """
    Clear logcat on a device.
    
    Args:
        device: Device serial
    
    Returns:
        JSON with success status
    """
    try:
        output = _run_adb_command(device, ['logcat', '-c'])
        
        if output.startswith('Error'):
            return json.dumps({"success": False, "error": output})
        
        return json.dumps({
            "success": True,
            "device": device,
            "message": "Logcat cleared successfully"
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


async def impl_export_logs(ctx: Optional[Context], device: str, format: str = "json", lines: int = 1000) -> str:
    """
    Export logcat to file (JSON, CSV, HTML).
    
    Supports all platforms: Works on macOS, Linux, Windows.
    
    Args:
        device: Device serial
        format: Export format (json, csv, html)
        lines: Number of lines to export
    
    Returns:
        JSON with export details and file path
    """
    try:
        logcat_output = _run_adb_command(device, ['logcat', '-d', '-v', 'threadtime', '-n', str(lines)])
        
        log_lines = []
        for line in logcat_output.split('\n'):
            if line.strip():
                log_obj = _parse_logcat_line(line)
                if log_obj:
                    log_lines.append(log_obj.model_dump())
        
        # Create temp file (cross-platform)
        suffix_map = {'json': '.json', 'csv': '.csv', 'html': '.html'}
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix=suffix_map.get(format, '.txt'),
            delete=False
        ) as f:
            if format == 'json':
                json.dump(log_lines, f, indent=2)
            elif format == 'csv':
                import csv
                if log_lines:
                    writer = csv.DictWriter(f, fieldnames=log_lines[0].keys())
                    writer.writeheader()
                    writer.writerows(log_lines)
            elif format == 'html':
                f.write('<html><body><table border="1">')
                if log_lines:
                    f.write('<tr>' + ''.join(f'<th>{k}</th>' for k in log_lines[0].keys()) + '</tr>')
                    for row in log_lines:
                        f.write('<tr>' + ''.join(f'<td>{v}</td>' for v in row.values()) + '</tr>')
                f.write('</table></body></html>')
            
            filepath = f.name
        
        return json.dumps({
            "success": True,
            "device": device,
            "format": format,
            "count": len(log_lines),
            "filepath": filepath,
            "message": f"Exported {len(log_lines)} log lines to {filepath}"
        })
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


async def impl_get_system_info(ctx: Optional[Context], device: str) -> str:
    """
    Get comprehensive system information from device.
    
    Args:
        device: Device serial
    
    Returns:
        JSON with SystemInfo object containing battery, memory, and other system data
    """
    try:
        # Get battery info
        dumpsys_output = _run_adb_command(device, ['shell', 'dumpsys', 'battery'])
        
        battery_info = {
            "level": 0,
            "status": "UNKNOWN",
            "voltage": None,
            "temperature": None,
            "technology": None,
            "health": None
        }
        
        for line in dumpsys_output.split('\n'):
            line = line.strip()
            if ': ' in line:
                key, value = line.split(': ', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key == 'level':
                    battery_info["level"] = int(value)
                elif key == 'status':
                    status_map = {
                        '1': 'UNKNOWN',
                        '2': 'CHARGING',
                        '3': 'DISCHARGING',
                        '4': 'NOT_CHARGING',
                        '5': 'FULL'
                    }
                    battery_info["status"] = status_map.get(value, value)
                elif key == 'voltage':
                    battery_info["voltage"] = int(value)
                elif key == 'temperature':
                    battery_info["temperature"] = int(value) / 10.0  # Convert to Celsius
                elif key == 'technology':
                    battery_info["technology"] = value
                elif key == 'health':
                    health_map = {
                        '1': 'UNKNOWN',
                        '2': 'GOOD',
                        '3': 'OVERHEAT',
                        '4': 'DEAD',
                        '5': 'OVER_VOLTAGE',
                        '6': 'UNSPECIFIED_FAILURE',
                        '7': 'COLD'
                    }
                    battery_info["health"] = health_map.get(value, value)
        
        # Get memory info
        meminfo_output = _run_adb_command(device, ['shell', 'cat', '/proc/meminfo'])
        
        total_memory = 0
        available_memory = 0
        cached_memory = 0
        buffers_memory = 0
        
        for line in meminfo_output.split('\n'):
            if line.startswith('MemTotal:'):
                total_memory = int(line.split()[1]) // 1024  # Convert to MB
            elif line.startswith('MemAvailable:'):
                available_memory = int(line.split()[1]) // 1024
            elif line.startswith('Cached:'):
                cached_memory = int(line.split()[1]) // 1024
            elif line.startswith('Buffers:'):
                buffers_memory = int(line.split()[1]) // 1024
        
        used_memory = total_memory - available_memory
        memory_usage_percent = (used_memory / total_memory) * 100 if total_memory > 0 else 0
        
        # Check for low memory
        low_memory = memory_usage_percent > 90
        
        memory_info = {
            "total_memory": total_memory,
            "available_memory": available_memory,
            "used_memory": used_memory,
            "memory_usage_percent": round(memory_usage_percent, 1),
            "cached_memory": cached_memory,
            "buffers_memory": buffers_memory,
            "low_memory": low_memory
        }
        
        # Get additional system info
        system_info = {
            "volume_level": None,
            "screen_brightness": None,
            "airplane_mode": None,
            "uptime_seconds": None,
            "cpu_cores": None,
            "cpu_frequency": None
        }
        
        # Try to get volume level
        try:
            volume_output = _run_adb_command(device, ['shell', 'settings', 'get', 'system', 'volume_music_speaker'])
            if volume_output.strip().isdigit():
                system_info["volume_level"] = int(volume_output.strip())
        except:
            pass
        
        # Try to get screen brightness
        try:
            brightness_output = _run_adb_command(device, ['shell', 'settings', 'get', 'system', 'screen_brightness'])
            if brightness_output.strip().isdigit():
                system_info["screen_brightness"] = int(brightness_output.strip())
        except:
            pass
        
        # Try to get airplane mode
        try:
            airplane_output = _run_adb_command(device, ['shell', 'settings', 'get', 'global', 'airplane_mode_on'])
            system_info["airplane_mode"] = airplane_output.strip() == '1'
        except:
            pass
        
        # Screen state removed (inaccurate across OEMs); leave as None.
        
        # Try to get uptime
        try:
            uptime_output = _run_adb_command(device, ['shell', 'cat', '/proc/uptime'])
            uptime_seconds = float(uptime_output.split()[0])
            system_info["uptime_seconds"] = int(uptime_seconds)
        except:
            pass
        
        # Try to get CPU info
        try:
            cpu_output = _run_adb_command(device, ['shell', 'cat', '/proc/cpuinfo', '|', 'grep', 'processor', '|', 'wc', '-l'])
            system_info["cpu_cores"] = int(cpu_output.strip())
        except:
            pass
        
        # Try to get storage info
        try:
            storage_output = _run_adb_command(device, ['shell', 'df', '/data'])
            # Parse df output for /data partition
            lines = storage_output.split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                if len(parts) >= 4:
                    total_storage = int(parts[1]) * 1024  # Convert to bytes
                    used_storage = int(parts[2]) * 1024
                    available_storage = int(parts[3]) * 1024
                    system_info["total_storage"] = total_storage
                    system_info["used_storage"] = used_storage
                    system_info["available_storage"] = available_storage
        except:
            pass
        
        from src.mcp.models import SystemInfo, BatteryInfo, MemoryInfo
        battery = BatteryInfo(**battery_info)
        memory = MemoryInfo(**memory_info)
        
        system = SystemInfo(
            device=device,
            battery=battery,
            memory=memory,
            **system_info
        )
        return json.dumps(system.model_dump())
    except Exception as e:
        return json.dumps({"error": str(e)})


async def impl_pull_fadcam_media(ctx: Optional[Context], device: str, package: str, media_type: str = "all",
                                output_dir: str = "./fadcam_media", limit: Optional[int] = None,
                                base_path: Optional[str] = None, confirm: bool = False,
                                storage_hint: Optional[str] = None) -> str:
    """
    Pull FadCam media files from device with comprehensive storage support.
    
    Supports all FadCam storage modes and app variants:
    - com.fadcam (Free version)
    - com.fadcam.beta (Beta version)
    - com.fadcam.proplus (Paid Pro+ version with custom app naming)
    - com.fadcam.notes (Standalone Notes app - Paid Pro version)
    - com.fadcam.calc (Standalone Calculator app - Paid Pro version)
    - com.fadcam.weather (Standalone Weather app - Paid Pro version)
    - Internal storage: /storage/emulated/0/Android/data/{package}/files/FadCam/
    - Custom SAF storage: User-selected locations (SD card, custom folders)

    Directory structure:
    FadCam/
    ├── Camera/ (videos: Back/, Front/, Dual/)
    ├── FadShot/ (photos: Back/, Selfie/, FadRec/)
    ├── Screen/ (screen recordings)
    ├── Stream/ (live streams)
    └── Faditor/ (edited videos: Converted/, Merge/)

    Args:
        device: Device serial number
        package: App package (auto-detects all com.fadcam.* variants)
        media_type: "videos", "screenshots", or "all"
        output_dir: Local directory to save files
        limit: Maximum number of files to pull (optional)

    Returns:
        JSON result with comprehensive file metadata
    """
    try:
        from src.mcp.models import FadCamMediaPullResult, MediaFile
        import json
        import os
        from pathlib import Path

        # Validate device connection
        devices_output = _run_adb_command(device, ['shell', 'echo', 'connected'])
        if "connected" not in devices_output:
            return json.dumps({"error": f"Device {device} not connected"})

        # Resolve package
        if package in {"", "all", "*", "auto"}:
            available_packages = _list_fadcam_packages(device)
            if not available_packages:
                return json.dumps({"error": "No FadCam packages found on device"})
            package = available_packages[0]
        elif not package.startswith("com.fadcam"):
            available_packages = _list_fadcam_packages(device)
            if package not in available_packages:
                return json.dumps({
                    "error": f"Package {package} not found. Available: {available_packages}",
                    "available_packages": available_packages
                })

        # Create output directory
        resolved_output_dir = _resolve_output_dir(output_dir)
        if resolved_output_dir != output_dir:
            await _ctx_info(ctx, f"Resolved output_dir to {resolved_output_dir}")
        output_path = Path(resolved_output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        files_pulled = []
        errors = []
        total_size = 0
        if not base_path and storage_hint:
            storage_result = await impl_fadcam_detect_storage(ctx, device, package, include_counts=False)
            storage_info = json.loads(storage_result)
            if "error" in storage_info:
                return storage_result
            resolved = await _resolve_or_elicit_base_path(
                ctx,
                storage_info,
                storage_hint,
                base_path,
                "Pull requires base_path."
            )
            if resolved.get("response"):
                return json.dumps({
                    "device": device,
                    "package": package,
                    **resolved["response"]
                })
            base_path = resolved.get("base_path")

        if not base_path:
            await _ctx_info(ctx, "Need a base_path (or storage_hint) before pulling. Returning available locations.")
            storage_result = await impl_fadcam_detect_storage(ctx, device, package, include_counts=False)
            storage_info = json.loads(storage_result)
            if "error" in storage_info:
                return storage_result
            base_paths = [
                entry.get("base_path")
                for pkg_info in storage_info.get("packages", [])
                for entry in pkg_info.get("storage_entries", [])
                if entry.get("base_path")
            ]
            chosen = await _elicit_base_path(ctx, base_paths, "Pull requires base_path.")
            if chosen:
                base_path = chosen
            else:
                return json.dumps({
                    "device": device,
                    "package": package,
                    "message": "Pull requires an explicit base_path. Choose one from available locations.",
                    "available_locations": [
                        {
                            "package": pkg_info.get("package"),
                            "base_path": entry.get("base_path"),
                            "storage_type": entry.get("type"),
                            "storage_root": entry.get("storage_root"),
                            "custom_storage_uri": entry.get("custom_storage_uri"),
                        }
                        for pkg_info in storage_info.get("packages", [])
                        for entry in pkg_info.get("storage_entries", [])
                        if entry.get("base_path")
                    ],
                    "requires_selection": True
                })

        internal_base = base_path
        if package in {"", "all", "*", "auto"}:
            match = re.search(r"/Android/data/([^/]+)/files/FadCam", internal_base)
            if match:
                package = match.group(1)

        # If base_path is not in standard FadCam layout, treat it as a flat custom root.
        if not _is_fadcam_layout(device, internal_base):
            max_files = limit or 100000
            files = _find_media_files_limited(
                device,
                internal_base,
                max_files,
                fadcam_only=True,
                maxdepth=1
            )
            if media_type == "videos":
                files = [f for f in files if f.endswith(".mp4")]
            elif media_type == "screenshots":
                files = [f for f in files if f.endswith(".jpg")]
            if not confirm:
                await _ctx_info(ctx, "Preview only. Set confirm=true to pull.")
                return json.dumps({
                    "device": device,
                    "package": package,
                    "message": "Preview only. Re-run with confirm=true to pull.",
                    "base_path": internal_base,
                    "media_type": media_type,
                    "preview_files": files[: min(len(files), limit or 20)],
                    "requires_confirmation": True
                })
            for file_path in files:
                if limit and len(files_pulled) >= limit:
                    break
                local_path = Path(
                    _resolve_preserved_local_path(str(output_path), file_path, internal_base)
                )
                local_path.parent.mkdir(parents=True, exist_ok=True)
                pull_cmd = _run_adb_command(device, ['pull', file_path, str(local_path)])
                if "error" in pull_cmd.lower() and "1 file pulled" not in pull_cmd:
                    errors.append(f"Failed to pull {local_path.name}: {pull_cmd}")
                    continue
                metadata_result = await impl_fadcam_get_metadata(ctx, device, package, file_path)
                metadata = json.loads(metadata_result) if isinstance(metadata_result, str) else metadata_result
                files_pulled.append(MediaFile(
                    filename=Path(file_path).name,
                    size_bytes=metadata.get("size_bytes", 0),
                    timestamp=metadata.get("created_date") or metadata.get("modified_timestamp", "unknown"),
                    local_path=str(local_path),
                    media_type="video" if file_path.endswith(".mp4") else "screenshot",
                    camera_type=None
                ))
                total_size += metadata.get("size_bytes", 0)
            result = FadCamMediaPullResult(
                device=device,
                package=package,
                media_type=media_type,
                output_dir=str(output_path.absolute()),
                files_pulled=files_pulled,
                total_files=len(files_pulled),
                total_size_bytes=total_size,
                errors=errors,
                storage_mode=None,
                custom_storage_uri=None
            )
            return json.dumps(result.model_dump())

        # Define media sources based on FadCam standard structure
        media_sources = []

        if media_type in ["videos", "all"]:
            media_sources.extend([
                ("video", "back", f"{internal_base}/Camera/Back/*.mp4"),
                ("video", "front", f"{internal_base}/Camera/Front/*.mp4"),
                ("video", "dual", f"{internal_base}/Camera/Dual/*.mp4"),
                ("video", "dual_legacy", f"{internal_base}/Dual/*.mp4"),
            ])

        if media_type in ["screenshots", "all"]:
            media_sources.extend([
                ("screenshot", "back", f"{internal_base}/FadShot/Back/*.jpg"),
                ("screenshot", "selfie", f"{internal_base}/FadShot/Selfie/*.jpg"),
                ("screenshot", "fadrec", f"{internal_base}/FadShot/FadRec/*.jpg"),
            ])

        if media_type in ["videos", "all"]:
            media_sources.append(("screen_recording", None, f"{internal_base}/Screen/*.mp4"))

        if media_type in ["videos", "all"]:
            media_sources.append(("stream", None, f"{internal_base}/Stream/*.mp4"))

        if media_type in ["videos", "all"]:
            media_sources.extend([
                ("faditor_converted", None, f"{internal_base}/Faditor/Converted/*.mp4"),
                ("faditor_merge", None, f"{internal_base}/Faditor/Merge/*.mp4"),
            ])

        forensics_base = f"{internal_base}/Forensics/Snapshots"

        # Process each media source
        # If not confirmed, return a preview list without pulling.
        if not confirm:
            await _ctx_info(ctx, "Preview only. Set confirm=true to pull.")
            preview = []
            remaining = limit or 20
            for media_type_name, camera_type, pattern in media_sources:
                if remaining <= 0:
                    break
                dir_path = pattern.replace('/*.mp4', '').replace('/*.jpg', '')
                files = _find_media_files_limited(
                    device,
                    dir_path,
                    remaining,
                    fadcam_only=False,
                    maxdepth=1
                )
                for file_path in files:
                    if remaining <= 0:
                        break
                    preview.append({
                        "path": file_path,
                        "media_type": media_type_name,
                        "camera_type": camera_type
                    })
                    remaining -= 1
            return json.dumps({
                "device": device,
                "package": package,
                "message": "Preview only. Re-run with confirm=true to pull.",
                "base_path": internal_base,
                "media_type": media_type,
                "preview_files": preview,
                "requires_confirmation": True
            })

        for media_type_name, camera_type, pattern in media_sources:
            try:
                # Extract directory path from pattern
                dir_path = pattern.replace('/*.mp4', '').replace('/*.jpg', '')

                # Check if directory exists
                ls_cmd = _run_adb_command(device, ['shell', 'ls', '-la', dir_path])
                if "No such file or directory" in ls_cmd:
                    continue  # No files of this type

                # Parse ls output to get files
                lines = ls_cmd.strip().split('\n')
                files_in_dir = []

                for line in lines:
                    if not line.strip() or line.startswith('total') or line.startswith('d'):
                        continue

                    parts = line.split()
                    if len(parts) < 8:
                        continue

                    filename = parts[-1]
                    size_str = parts[4]

                    # Filter by file extension
                    if media_type_name in ["video", "screen_recording", "stream", "faditor_converted", "faditor_merge"]:
                        if not filename.endswith('.mp4'):
                            continue
                    elif media_type_name == "screenshot":
                        if not filename.endswith('.jpg'):
                            continue
                    else:
                        continue

                    try:
                        size_bytes = int(size_str)
                        files_in_dir.append((filename, size_bytes))
                    except (ValueError, IndexError):
                        continue

                # Sort files by modification time (newest first) - would need stat command
                # For now, just process in ls order

                for filename, size_bytes in files_in_dir:
                    if limit and len(files_pulled) >= limit:
                        break

                    # Extract timestamp from filename
                    timestamp = "unknown"
                    if filename.startswith('FadCam_') and len(filename) >= 19:
                        timestamp = filename[7:7+15]  # YYYYMMDD_HHMMSS
                    elif filename.startswith('FadShot_') and len(filename) >= 23:
                        timestamp = filename[14:14+15]  # YYYYMMDD_HHMMSS

                    # Pull file from device
                    device_file_path = f"{dir_path}/{filename}"
                    local_path = Path(
                        _resolve_preserved_local_path(str(output_path), device_file_path, internal_base)
                    )
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    pull_cmd = ['pull', device_file_path, str(local_path)]
                    pull_output = _run_adb_command(device, pull_cmd)

                    if "error" in pull_output.lower() and "1 file pulled" not in pull_output:
                        errors.append(f"Failed to pull {filename}: {pull_output}")
                        continue

                    # Create MediaFile object
                    media_file = MediaFile(
                        filename=filename,
                        size_bytes=size_bytes,
                        timestamp=timestamp,
                        local_path=str(local_path),
                        media_type=media_type_name,
                        camera_type=camera_type
                    )

                    files_pulled.append(media_file)
                    total_size += size_bytes

            except Exception as e:
                errors.append(f"Error processing {media_type_name} files: {str(e)}")

        # Forensics snapshots (minimal support)
        if media_type in ["screenshots", "all"]:
            try:
                find_cmd = _run_adb_command(device, [
                    'shell', 'find', forensics_base,
                    '-type', 'f', '-name', '*.jpg'
                ])
                if "No such file" not in find_cmd and "Permission denied" not in find_cmd:
                    files = [f.strip() for f in find_cmd.split('\n') if f.strip()]
                    for remote_path in files:
                        if limit and len(files_pulled) >= limit:
                            break
                        filename = remote_path.split('/')[-1]
                        local_path = Path(
                            _resolve_preserved_local_path(str(output_path), remote_path, internal_base)
                        )
                        local_path.parent.mkdir(parents=True, exist_ok=True)
                        pull_cmd = ['pull', remote_path, str(local_path)]
                        pull_output = _run_adb_command(device, pull_cmd)
                        if "error" in pull_output.lower() and "1 file pulled" not in pull_output:
                            errors.append(f"Failed to pull {filename}: {pull_output}")
                            continue
                        metadata_result = await impl_fadcam_get_metadata(ctx, device, package, remote_path)
                        metadata = json.loads(metadata_result) if isinstance(metadata_result, str) else metadata_result
                        files_pulled.append(MediaFile(
                            filename=filename,
                            size_bytes=metadata.get("size_bytes", 0),
                            timestamp=metadata.get("modified_timestamp", "unknown"),
                            local_path=str(local_path),
                            media_type="forensics_snapshot",
                            camera_type=None
                        ))
                        total_size += metadata.get("size_bytes", 0)
            except Exception as e:
                errors.append(f"Error processing forensics snapshots: {str(e)}")

        # Create result
        result = FadCamMediaPullResult(
            device=device,
            package=package,
            media_type=media_type,
            output_dir=str(output_path.absolute()),
            files_pulled=files_pulled,
            total_files=len(files_pulled),
            total_size_bytes=total_size,
            errors=errors,
            storage_mode=None,
            custom_storage_uri=None
        )

        return json.dumps(result.model_dump())

    except Exception as e:
        return json.dumps({"error": str(e)})


async def impl_fadcam_list_packages(ctx: Optional[Context], device: str) -> str:
    """List all FadCam packages installed on a device"""
    try:
        # Check device connection
        devices_output = _run_adb_command(device, ['shell', 'echo', 'connected'])
        if "connected" not in devices_output:
            return json.dumps({"error": f"Device {device} not connected"})

        # Get all packages and filter for FadCam
        packages_output = _run_adb_command(device, ['shell', 'pm', 'list', 'packages'])
        fadcam_packages = []

        for line in packages_output.split('\n'):
            line = line.strip()
            if line.startswith('package:'):
                package_name = line.split(':', 1)[1].strip()
                if package_name.startswith('com.fadcam'):
                    fadcam_packages.append(package_name)

        return json.dumps({
            "device": device,
            "fadcam_packages": fadcam_packages,
            "total_found": len(fadcam_packages)
        })

    except Exception as e:
        return json.dumps({"error": str(e)})


async def impl_fadcam_detect_storage(ctx: Optional[Context], device: str, package: str,
                                     include_counts: bool = False) -> str:
    """Detect FadCam storage configuration for a package"""
    try:
        # Check device connection
        devices_output = _run_adb_command(device, ['shell', 'echo', 'connected'])
        if "connected" not in devices_output:
            return json.dumps({"error": f"Device {device} not connected"})

        packages = _normalize_package_list(device, package)
        if not packages:
            return json.dumps({"error": "No FadCam packages found on device"})

        volumes = _list_storage_volumes(device)
        results = []

        for pkg in packages:
            # Validate package exists if explicitly provided
            if package not in {"", "all", "*", "auto"}:
                packages_output = _run_adb_command(device, ['shell', 'pm', 'list', 'packages', pkg])
                if f"package:{pkg}" not in packages_output:
                    results.append({
                        "package": pkg,
                        "error": f"Package {pkg} not found on device"
                    })
                    continue

            prefs = _read_fadcam_prefs(device, pkg)
            storage_mode = prefs.get("storage_mode") or "internal"
            custom_storage_uri = prefs.get("custom_storage_uri")

            storage_entries = []

            # Default internal (primary)
            internal_base = f"/storage/emulated/0/Android/data/{pkg}/files/FadCam"
            stats = _check_path_stats(device, internal_base, include_counts=include_counts)
            storage_entries.append({
                "type": "default_internal",
                "base_path": internal_base,
                "storage_root": "/storage/emulated/0",
                **stats
            })

            # SD card internal
            for vol in volumes:
                sd_base = f"/storage/{vol}/Android/data/{pkg}/files/FadCam"
                stats = _check_path_stats(device, sd_base, include_counts=include_counts)
                storage_entries.append({
                    "type": "sd_internal",
                    "base_path": sd_base,
                    "storage_root": f"/storage/{vol}",
                    **stats
                })

            # Shared default (internal)
            shared_defaults = [
                "/storage/emulated/0/Download/FadCam",
                "/storage/emulated/0/DCIM/FadCam"
            ]
            for shared_path in shared_defaults:
                stats = _check_path_stats(device, shared_path, include_counts=include_counts)
                storage_entries.append({
                    "type": "shared_default",
                    "base_path": shared_path,
                    "storage_root": "/storage/emulated/0",
                    **stats
                })

            # Shared SD
            for vol in volumes:
                for shared_path in [f"/storage/{vol}/Download/FadCam", f"/storage/{vol}/DCIM/FadCam"]:
                    stats = _check_path_stats(device, shared_path, include_counts=include_counts)
                    storage_entries.append({
                        "type": "shared_sd",
                        "base_path": shared_path,
                        "storage_root": f"/storage/{vol}",
                        **stats
                    })

            # Custom SAF (resolve to actual path if possible)
            if storage_mode == "custom" and custom_storage_uri:
                custom_path = _saf_uri_to_path(custom_storage_uri)
                if custom_path:
                    custom_stats = _check_path_stats(
                        device,
                        custom_path,
                        fadcam_only=True,
                        maxdepth=1,
                        include_counts=include_counts
                    )
                    storage_entries.append({
                        "type": "custom_root",
                        "base_path": custom_path,
                        "storage_root": custom_path,
                        "custom_storage_uri": custom_storage_uri,
                        **custom_stats
                    })
                    custom_fadcam = f"{custom_path}/FadCam"
                    if _path_exists(device, custom_fadcam):
                        fadcam_stats = _check_path_stats(
                            device,
                            custom_fadcam,
                            include_counts=include_counts
                        )
                        storage_entries.append({
                            "type": "custom_fadcam_subdir",
                            "base_path": custom_fadcam,
                            "storage_root": custom_path,
                            "custom_storage_uri": custom_storage_uri,
                            **fadcam_stats
                        })
                else:
                    storage_entries.append({
                        "type": "custom_saf",
                        "base_path": None,
                        "storage_root": None,
                        "exists": None,
                        "file_count": None,
                        "total_size_bytes": None,
                        "custom_storage_uri": custom_storage_uri
                    })

            results.append({
                "package": pkg,
                "storage_mode": storage_mode,
                "custom_storage_uri": custom_storage_uri,
                "storage_entries": storage_entries
            })

        return json.dumps({
            "device": device,
            "packages": results,
            "default_package": results[0]["package"] if results else None
        })

    except Exception as e:
        return json.dumps({"error": str(e)})


async def impl_fadcam_list_structure(ctx: Optional[Context], device: str, package: str,
                                     include_counts: bool = True) -> str:
    """List FadCam directory structure and file counts"""
    try:
        # Get storage info first
        storage_result = await impl_fadcam_detect_storage(ctx, device, package, include_counts=False)
        storage_info = json.loads(storage_result)

        if "error" in storage_info:
            return storage_result

        structures = []

        categories = {
            "Camera": ["Back", "Front", "Dual"],
            "Dual": [],  # Legacy
            "FadShot": ["Back", "Selfie", "FadRec"],
            "Screen": [],
            "Stream": [],
            "Faditor": ["Converted", "Merge"],
            "Forensics": ["Snapshots"],
        }

        for pkg_info in storage_info.get("packages", []):
            pkg = pkg_info.get("package")
            for entry in pkg_info.get("storage_entries", []):
                base_path = entry.get("base_path")
                if not base_path or not entry.get("exists"):
                    continue
                is_fadcam_layout = _is_fadcam_layout(device, base_path)
                structure = {
                    "package": pkg,
                    "base_path": base_path,
                    "storage_type": entry.get("type"),
                    "storage_root": entry.get("storage_root"),
                    "layout": "fadcam" if is_fadcam_layout else "flat",
                    "categories": {},
                    "total_files": 0 if include_counts else None,
                    "total_size_bytes": entry.get("total_size_bytes")
                }

                if not is_fadcam_layout:
                    cat_info = {
                        "path": base_path,
                        "exists": True,
                        "total_files": _count_media_files(device, base_path, maxdepth=1, fadcam_only=True)
                        if include_counts else None,
                        "subdirs": {}
                    }
                    structure["categories"]["CustomRoot"] = cat_info
                    if include_counts and cat_info["total_files"] is not None:
                        structure["total_files"] += cat_info["total_files"]
                    structures.append(structure)
                    continue

                for category, subdirs in categories.items():
                    if category == "Forensics":
                        cat_path = f"{base_path}/Forensics/Snapshots"
                        cat_info = {"path": cat_path, "exists": False, "total_files": 0, "subdirs": {}}
                        ls_cmd = _run_adb_command(device, ['shell', 'ls', '-la', cat_path])
                        if "No such file or directory" not in ls_cmd and "Permission denied" not in ls_cmd:
                            cat_info["exists"] = True
                            cat_info["total_files"] = _count_media_files(device, cat_path) if include_counts else None
                            if include_counts and cat_info["total_files"] is not None:
                                structure["total_files"] += cat_info["total_files"]
                            cat_info["subdirs"]["Snapshots"] = {
                                "path": cat_path,
                                "exists": True,
                                "file_count": cat_info["total_files"] if include_counts else None
                            }
                        structure["categories"][category] = cat_info
                        continue

                    cat_path = f"{base_path}/{category}"
                    cat_info = {"path": cat_path, "exists": False, "total_files": None, "subdirs": {}}

                    ls_cmd = _run_adb_command(device, ['shell', 'ls', '-la', cat_path])
                    if "No such file or directory" not in ls_cmd and "Permission denied" not in ls_cmd:
                        cat_info["exists"] = True

                        cat_info["total_files"] = (
                            _count_media_files(device, cat_path, maxdepth=1) if include_counts else None
                        )
                        if include_counts and cat_info["total_files"] is not None:
                            structure["total_files"] += cat_info["total_files"]

                        for subdir in subdirs:
                            sub_path = f"{cat_path}/{subdir}"
                            sub_info = {"path": sub_path, "exists": False, "file_count": None}

                            ls_sub_cmd = _run_adb_command(device, ['shell', 'ls', '-la', sub_path])
                            if "No such file or directory" not in ls_sub_cmd and "Permission denied" not in ls_sub_cmd:
                                sub_info["exists"] = True

                                sub_info["file_count"] = _count_media_files(device, sub_path) if include_counts else None
                                if include_counts and sub_info["file_count"] is not None:
                                    structure["total_files"] += sub_info["file_count"]

                            cat_info["subdirs"][subdir] = sub_info

                    structure["categories"][category] = cat_info

                # Root-level media files (e.g., FadCam_*.mp4 directly under base_path)
                root_count = _count_media_files(
                    device,
                    base_path,
                    maxdepth=1,
                    fadcam_only=True
                ) if include_counts else None
                if root_count is None or root_count > 0:
                    structure["categories"]["Root"] = {
                        "path": base_path,
                        "exists": True,
                        "total_files": root_count,
                        "subdirs": {}
                    }
                    if include_counts and root_count:
                        structure["total_files"] += root_count

                structures.append(structure)

        return json.dumps({
            "device": device,
            "structures": structures,
            "total_locations": len(structures)
        })

    except Exception as e:
        return json.dumps({"error": str(e)})


async def impl_fadcam_get_metadata(ctx: Optional[Context], device: str, package: str, file_path: str) -> str:
    """Get metadata for a specific FadCam video file"""
    try:
        # Check if file exists and get basic info
        stat_cmd = _run_adb_command(device, ['shell', 'stat', '-c', '%s,%Y', file_path])
        if "No such file" in stat_cmd or "Permission denied" in stat_cmd:
            return json.dumps({"error": f"File not accessible: {file_path}"})

        metadata = {
            "file_path": file_path,
            "filename": file_path.split('/')[-1],
            "size_bytes": 0,
            "modified_timestamp": 0,
            "created_date": None,
            "file_type": "unknown"
        }

        # Parse stat output
        try:
            size_str, mtime_str = stat_cmd.strip().split(',')
            metadata["size_bytes"] = int(size_str)
            metadata["modified_timestamp"] = int(mtime_str)
        except:
            pass

        # Determine file type
        if file_path.endswith('.mp4'):
            metadata["file_type"] = "video"
        elif file_path.endswith('.jpg'):
            metadata["file_type"] = "image"

        # Extract date from filename
        filename = metadata["filename"]
        if filename.startswith('FadCam_') and len(filename) >= 19:
            date_str = filename[7:7+15]  # YYYYMMDD_HHMMSS
            try:
                from datetime import datetime
                dt = datetime.strptime(date_str, '%Y%m%d_%H%M%S')
                metadata["created_date"] = dt.isoformat()
            except:
                pass
        elif filename.startswith('FadShot_') and len(filename) >= 23:
            date_str = filename[14:14+15]  # YYYYMMDD_HHMMSS
            try:
                from datetime import datetime
                dt = datetime.strptime(date_str, '%Y%m%d_%H%M%S')
                metadata["created_date"] = dt.isoformat()
            except:
                pass
        elif "/Forensics/Snapshots/" in file_path and filename.endswith(".jpg"):
            metadata.update(_parse_forensics_filename(file_path))

        return json.dumps(metadata)

    except Exception as e:
        return json.dumps({"error": str(e)})


async def impl_fadcam_pull_file(ctx: Optional[Context], device: str, package: str, file_path: str,
                               output_dir: str = "./fadcam_files",
                               confirm: bool = False,
                               base_path: Optional[str] = None,
                               storage_hint: Optional[str] = None) -> str:
    """Pull a specific FadCam file by exact path or filename."""
    try:
        from pathlib import Path
        if "/" not in file_path:
            filename = file_path
            if not base_path and storage_hint:
                storage_result = await impl_fadcam_detect_storage(ctx, device, package, include_counts=False)
                storage_info = json.loads(storage_result)
                if "error" in storage_info:
                    return storage_result
                resolved = await _resolve_or_elicit_base_path(
                    ctx,
                    storage_info,
                    storage_hint,
                    base_path,
                    "Pull by filename requires base_path."
                )
                if resolved.get("response"):
                    return json.dumps({
                        "device": device,
                        "package": package,
                        **resolved["response"]
                    })
                base_path = resolved.get("base_path")

            if not base_path:
                await _ctx_info(ctx, "Need a base_path (or storage_hint) to resolve filename.")
                storage_result = await impl_fadcam_detect_storage(ctx, device, package, include_counts=False)
                storage_info = json.loads(storage_result)
                if "error" in storage_info:
                    return storage_result
                base_paths = [
                    entry.get("base_path")
                    for pkg_info in storage_info.get("packages", [])
                    for entry in pkg_info.get("storage_entries", [])
                    if entry.get("base_path")
                ]
                chosen = await _elicit_base_path(ctx, base_paths, "Select base_path to resolve filename.")
                if chosen:
                    base_path = chosen
                else:
                    return json.dumps({
                        "device": device,
                        "package": package,
                        "message": "Filename needs a base_path. Choose one from available locations.",
                        "available_locations": base_paths,
                        "requires_selection": True
                    })

            matches = _find_fadcam_file_matches(device, base_path, filename)
            if not matches:
                return json.dumps({
                    "error": f"No match for filename: {filename}",
                    "base_path": base_path
                })
            if len(matches) > 1:
                chosen = await _elicit_base_path(ctx, matches, "Multiple matches. Choose one file to pull.")
                if chosen:
                    file_path = chosen
                else:
                    return json.dumps({
                        "device": device,
                        "package": package,
                        "message": "Multiple matches found. Choose a file.",
                        "available_matches": matches,
                        "requires_selection": True
                    })
            else:
                file_path = matches[0]

        if not confirm:
            metadata_result = await impl_fadcam_get_metadata(ctx, device, package, file_path)
            metadata = json.loads(metadata_result) if isinstance(metadata_result, str) else metadata_result
            await _ctx_info(ctx, "Preview only. Set confirm=true to pull.")
            return json.dumps({
                "device": device,
                "package": package,
                "file_path": file_path,
                "output_dir": _resolve_output_dir(output_dir),
                "message": "Preview only. Re-run with confirm=true to pull.",
                "metadata": metadata,
                "requires_confirmation": True
            })

        resolved_output_dir = _resolve_output_dir(output_dir)
        if resolved_output_dir != output_dir:
            await _ctx_info(ctx, f"Resolved output_dir to {resolved_output_dir}")
        output_path = Path(resolved_output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        local_path = Path(_resolve_preserved_local_path(str(output_path), file_path, base_path))
        local_path.parent.mkdir(parents=True, exist_ok=True)

        pull_output = _run_adb_command(device, ['pull', file_path, str(local_path)])
        if "error" in pull_output.lower() and "1 file pulled" not in pull_output:
            return json.dumps({"error": f"Failed to pull {local_path.name}: {pull_output}"})

        metadata_result = await impl_fadcam_get_metadata(ctx, device, package, file_path)
        metadata = json.loads(metadata_result) if isinstance(metadata_result, str) else metadata_result
        return json.dumps({
            "device": device,
            "package": package,
            "file_path": file_path,
            "local_path": str(local_path),
            "output_dir": str(output_path),
            "metadata": metadata
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


async def impl_fadcam_pull_files(ctx: Optional[Context], device: str, package: str, output_dir: str = "./fadcam_files",
                                category: Optional[str] = None, camera: Optional[str] = None,
                                limit: Optional[int] = None, date_from: Optional[str] = None,
                                date_to: Optional[str] = None, base_path: Optional[str] = None,
                                confirm: bool = False,
                                storage_hint: Optional[str] = None) -> str:
    """Pull FadCam files with advanced filtering"""
    try:
        from pathlib import Path
        import os
        from datetime import datetime

        # Get structure first
        structure_result = await impl_fadcam_list_structure(ctx, device, package, include_counts=False)
        structure = json.loads(structure_result)

        if "error" in structure:
            return structure_result

        if not base_path and storage_hint:
            storage_result = await impl_fadcam_detect_storage(ctx, device, package, include_counts=False)
            storage_info = json.loads(storage_result)
            if "error" in storage_info:
                return storage_result
            resolved = await _resolve_or_elicit_base_path(
                ctx,
                storage_info,
                storage_hint,
                base_path,
                "Pull requires base_path."
            )
            if resolved.get("response"):
                return json.dumps({
                    "device": device,
                    "package": package,
                    **resolved["response"]
                })
            base_path = resolved.get("base_path")

        if not base_path:
            await _ctx_info(ctx, "Need a base_path (or storage_hint) before pulling. Returning available locations.")
            base_paths = [loc.get("base_path") for loc in structure.get("structures", []) if loc.get("base_path")]
            chosen = await _elicit_base_path(ctx, base_paths, "Pull requires base_path.")
            if chosen:
                base_path = chosen
            else:
                return json.dumps({
                    "device": device,
                    "package": package,
                    "message": "Browse-first: choose a base_path from available locations before pulling.",
                    "available_locations": structure.get("structures", []),
                    "requires_selection": True
                })

        matching = [s for s in structure.get("structures", []) if s.get("base_path") == base_path]
        if not matching:
            await _ctx_warning(ctx, "base_path not found. Returning available base paths.")
            return json.dumps({
                "error": f"base_path not found: {base_path}",
                "available_base_paths": [s.get("base_path") for s in structure.get("structures", [])]
            })
        location = matching[0]
        if package in {"", "all", "*", "auto"}:
            package = location.get("package") or package

        # Create output directory
        resolved_output_dir = _resolve_output_dir(output_dir)
        if resolved_output_dir != output_dir:
            await _ctx_info(ctx, f"Resolved output_dir to {resolved_output_dir}")
        output_path = Path(resolved_output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Parse date filters
        date_from_dt = None
        date_to_dt = None
        if date_from:
            try:
                date_from_dt = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
            except:
                pass
        if date_to:
            try:
                date_to_dt = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
            except:
                pass

        pulled_files = []
        total_size = 0
        errors = []

        def should_pull_file(filename: str) -> bool:
            """Check if file should be pulled based on filters"""
            if not (filename.endswith('.mp4') or filename.endswith('.jpg')):
                return False

            # Date filtering
            if date_from_dt or date_to_dt:
                date_str = None
                if filename.startswith('FadCam_') and len(filename) >= 19:
                    date_str = filename[7:7+15]
                elif filename.startswith('FadShot_') and len(filename) >= 23:
                    date_str = filename[14:14+15]

                if date_str:
                    try:
                        file_dt = datetime.strptime(date_str, '%Y%m%d_%H%M%S')
                        if date_from_dt and file_dt < date_from_dt:
                            return False
                        if date_to_dt and file_dt > date_to_dt:
                            return False
                    except:
                        pass

            return True

        # If not confirmed, return a preview from the selected location.
        if not confirm:
            preview = await impl_fadcam_browse_files(
                ctx,
                device,
                package,
                category=category,
                camera=camera,
                limit=limit or 20,
                base_path=base_path
            )
            preview_obj = json.loads(preview) if isinstance(preview, str) else preview
            preview_obj["message"] = "Preview only. Re-run with confirm=true to pull."
            preview_obj["requires_confirmation"] = True
            await _ctx_info(ctx, "Preview only. Set confirm=true to pull.")
            return json.dumps(preview_obj)

        # Process categories
        for cat_name, cat_info in location["categories"].items():
            if category and cat_name.lower() != category.lower():
                continue

            if not cat_info["exists"]:
                continue

            is_custom_root = cat_name == "CustomRoot"
            is_root_media = cat_name == "Root"
            if cat_name == "Forensics":
                # Pull forensic snapshots (jpg only)
                remaining = (limit - len(pulled_files)) if limit else None
                files = [f for f in _find_media_files_limited(
                    device,
                    cat_info["path"],
                    remaining or 10_000,
                ) if f.endswith('.jpg')]
                for remote_path in files:
                    if limit and len(pulled_files) >= limit:
                        break
                    filename = remote_path.split('/')[-1]
                    local_path = Path(
                        _resolve_preserved_local_path(str(output_path), remote_path, base_path)
                    )
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    pull_cmd = ['pull', remote_path, str(local_path)]
                    pull_output = _run_adb_command(device, pull_cmd)
                    if "error" in pull_output.lower() and "1 file pulled" not in pull_output:
                        errors.append(f"Failed to pull {filename}: {pull_output}")
                        continue
                    metadata_result = await impl_fadcam_get_metadata(ctx, device, package, remote_path)
                    metadata = json.loads(metadata_result) if isinstance(metadata_result, str) else metadata_result
                    pulled_files.append({
                        "filename": filename,
                        "category": "Forensics",
                        "subcategory": "Snapshots",
                        "remote_path": remote_path,
                        "local_path": str(local_path),
                        "metadata": metadata
                    })
                    total_size += metadata.get("size_bytes", 0)
                continue

            subdirs = cat_info.get("subdirs", {})
            if not subdirs:
                remaining = (limit - len(pulled_files)) if limit else None
                files = _find_media_files_limited(
                    device,
                    cat_info["path"],
                    remaining or 10_000,
                    fadcam_only=is_custom_root or is_root_media,
                    maxdepth=1
                )
                for remote_path in files:
                    if limit and len(pulled_files) >= limit:
                        break
                    filename = remote_path.split('/')[-1]
                    if is_custom_root and not _is_fadcam_filename(filename):
                        continue
                    local_path = Path(
                        _resolve_preserved_local_path(str(output_path), remote_path, base_path)
                    )
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    pull_cmd = ['pull', remote_path, str(local_path)]
                    pull_output = _run_adb_command(device, pull_cmd)
                    if "error" in pull_output.lower() and "1 file pulled" not in pull_output:
                        errors.append(f"Failed to pull {filename}: {pull_output}")
                        continue
                    metadata_result = await impl_fadcam_get_metadata(ctx, device, package, remote_path)
                    metadata = json.loads(metadata_result) if isinstance(metadata_result, str) else metadata_result
                    pulled_files.append({
                        "filename": filename,
                        "category": cat_name,
                        "subcategory": None,
                        "remote_path": remote_path,
                        "local_path": str(local_path),
                        "metadata": metadata
                    })
                    total_size += metadata.get("size_bytes", 0)
                continue

            # Process subdirectories
            for sub_name, sub_info in subdirs.items():
                if camera and sub_name.lower() != camera.lower():
                    continue

                if not sub_info["exists"]:
                    continue

                # Get files in this subdirectory
                remaining = (limit - len(pulled_files)) if limit else None
                files = _find_media_files_limited(
                    device,
                    sub_info["path"],
                    remaining or 10_000,
                    maxdepth=1
                )

                for remote_path in files:
                    if limit and len(pulled_files) >= limit:
                        break

                    filename = remote_path.split('/')[-1]

                    if should_pull_file(filename):
                        local_path = Path(
                            _resolve_preserved_local_path(str(output_path), remote_path, base_path)
                        )
                        local_path.parent.mkdir(parents=True, exist_ok=True)

                        # Pull file
                        pull_cmd = _run_adb_command(device, ['pull', remote_path, str(local_path)])

                        if "error" in pull_cmd.lower() and "1 file pulled" not in pull_cmd:
                            errors.append(f"Failed to pull {filename}: {pull_cmd}")
                            continue

                        # Get metadata
                        metadata_result = await impl_fadcam_get_metadata(ctx, device, package, remote_path)
                        metadata = json.loads(metadata_result) if isinstance(metadata_result, str) else metadata_result

                        pulled_files.append({
                            "filename": filename,
                            "category": cat_name,
                            "subcategory": sub_name,
                            "remote_path": remote_path,
                            "local_path": str(local_path),
                            "metadata": metadata
                        })

                        total_size += metadata.get("size_bytes", 0)

        return json.dumps({
            "device": device,
            "package": package,
            "output_dir": str(output_path.absolute()),
            "total_pulled": len(pulled_files),
            "total_size_bytes": total_size,
            "files": pulled_files,
            "errors": errors,
            "filters_applied": {
                "category": category,
                "camera": camera,
                "limit": limit,
                "date_from": date_from,
                "date_to": date_to
            }
        })

    except Exception as e:
        return json.dumps({"error": str(e)})


async def impl_fadcam_browse_files(ctx: Optional[Context], device: str, package: str, category: Optional[str] = None,
                                  camera: Optional[str] = None, limit: int = 50,
                                  base_path: Optional[str] = None,
                                  storage_hint: Optional[str] = None) -> str:
    """Browse FadCam files without downloading - returns metadata only"""
    try:
        structure_result = await impl_fadcam_list_structure(ctx, device, package, include_counts=False)
        structure = json.loads(structure_result)

        if "error" in structure:
            return structure_result

        if not base_path and storage_hint:
            storage_result = await impl_fadcam_detect_storage(ctx, device, package, include_counts=False)
            storage_info = json.loads(storage_result)
            if "error" in storage_info:
                return storage_result
            resolved = await _resolve_or_elicit_base_path(
                ctx,
                storage_info,
                storage_hint,
                base_path,
                "Browse requires base_path."
            )
            if resolved.get("response"):
                return json.dumps({
                    "device": device,
                    "package": package,
                    **resolved["response"]
                })
            base_path = resolved.get("base_path")

        if not base_path:
            await _ctx_info(ctx, "Need a base_path (or storage_hint) to browse. Returning available locations.")
            base_paths = [loc.get("base_path") for loc in structure.get("structures", []) if loc.get("base_path")]
            chosen = await _elicit_base_path(ctx, base_paths, "Browse requires base_path.")
            if chosen:
                base_path = chosen
            else:
                return json.dumps({
                    "device": device,
                    "package": package,
                    "message": "Browse requires an explicit base_path. Choose one from available_locations.",
                    "available_locations": [
                        {
                            "package": loc.get("package"),
                            "base_path": loc.get("base_path"),
                            "storage_type": loc.get("storage_type"),
                            "layout": loc.get("layout"),
                        }
                        for loc in structure.get("structures", [])
                    ],
                    "requires_selection": True
                })

        files_info = []
        total_count = 0
        seen_any_location = False

        for location in structure.get("structures", []):
            if base_path and location.get("base_path") != base_path:
                continue
            seen_any_location = True

            pkg = location.get("package")
            storage_type = location.get("storage_type")
            base = location.get("base_path")
            layout = location.get("layout")

            if category and category.lower() == "fadshot":
                fadshot_root = f"{base}/FadShot"
                if _path_exists(device, fadshot_root):
                    subdirs = ("Back", "Selfie", "FadRec")
                    if camera:
                        subdirs = tuple(s for s in subdirs if s.lower() == camera.lower())
                    for sub_name in subdirs:
                        sub_path = f"{fadshot_root}/{sub_name}"
                        if not _path_exists(device, sub_path):
                            continue
                        entries = _list_media_entries_from_ls(device, sub_path)
                        for entry in entries:
                            if total_count >= limit:
                                break
                            metadata = _build_metadata_from_filename(entry["path"], entry.get("size_bytes"))
                            files_info.append({
                                "filename": metadata["filename"],
                                "category": "FadShot",
                                "subcategory": sub_name,
                                "remote_path": entry["path"],
                                "base_path": base,
                                "storage_type": storage_type,
                                "metadata": metadata
                            })
                            total_count += 1
                        if total_count >= limit:
                            break
                continue

            if category and category.lower() == "camera":
                subdirs = ("Back", "Front", "Dual")
                if camera:
                    subdirs = tuple(s for s in subdirs if s.lower() == camera.lower())
                for sub_name in subdirs:
                    sub_path = f"{base}/Camera/{sub_name}"
                    if not _path_exists(device, sub_path):
                        continue
                    entries = _list_media_entries_from_ls(device, sub_path)
                    entries = [e for e in entries if e["path"].endswith(".mp4")]
                    for entry in entries:
                        if total_count >= limit:
                            break
                        metadata = _build_metadata_from_filename(entry["path"], entry.get("size_bytes"))
                        files_info.append({
                            "filename": metadata["filename"],
                            "category": "Camera",
                            "subcategory": sub_name,
                            "remote_path": entry["path"],
                            "base_path": base,
                            "storage_type": storage_type,
                            "metadata": metadata
                        })
                        total_count += 1
                    if total_count >= limit:
                        break
                continue

            if category and category.lower() == "dual":
                dual_path = f"{base}/Dual"
                if _path_exists(device, dual_path):
                    entries = _list_media_entries_from_ls(device, dual_path)
                    entries = [e for e in entries if e["path"].endswith(".mp4")]
                    for entry in entries:
                        if total_count >= limit:
                            break
                        metadata = _build_metadata_from_filename(entry["path"], entry.get("size_bytes"))
                        files_info.append({
                            "filename": metadata["filename"],
                            "category": "Dual",
                            "subcategory": None,
                            "remote_path": entry["path"],
                            "base_path": base,
                            "storage_type": storage_type,
                            "metadata": metadata
                        })
                        total_count += 1
                continue

            if category and category.lower() in {"screen", "stream"}:
                cat_dir = "Screen" if category.lower() == "screen" else "Stream"
                cat_path = f"{base}/{cat_dir}"
                if _path_exists(device, cat_path):
                    entries = _list_media_entries_from_ls(device, cat_path)
                    entries = [e for e in entries if e["path"].endswith(".mp4")]
                    for entry in entries:
                        if total_count >= limit:
                            break
                        metadata = _build_metadata_from_filename(entry["path"], entry.get("size_bytes"))
                        files_info.append({
                            "filename": metadata["filename"],
                            "category": cat_dir,
                            "subcategory": None,
                            "remote_path": entry["path"],
                            "base_path": base,
                            "storage_type": storage_type,
                            "metadata": metadata
                        })
                        total_count += 1
                continue

            if category and category.lower() == "faditor":
                for sub_name in ("Converted", "Merge"):
                    sub_path = f"{base}/Faditor/{sub_name}"
                    if not _path_exists(device, sub_path):
                        continue
                    entries = _list_media_entries_from_ls(device, sub_path)
                    entries = [e for e in entries if e["path"].endswith(".mp4")]
                    for entry in entries:
                        if total_count >= limit:
                            break
                        metadata = _build_metadata_from_filename(entry["path"], entry.get("size_bytes"))
                        files_info.append({
                            "filename": metadata["filename"],
                            "category": "Faditor",
                            "subcategory": sub_name,
                            "remote_path": entry["path"],
                            "base_path": base,
                            "storage_type": storage_type,
                            "metadata": metadata
                        })
                        total_count += 1
                    if total_count >= limit:
                        break
                continue

            if storage_hint and storage_hint.lower().strip() in {"internal", "default_internal", "internal_default"}:
                fadshot_root = f"{base}/FadShot"
                if _path_exists(device, fadshot_root):
                    for sub_name in ("Back", "Selfie", "FadRec"):
                        sub_path = f"{fadshot_root}/{sub_name}"
                        if not _path_exists(device, sub_path):
                            continue
                        entries = _list_media_entries_from_ls(device, sub_path)
                        for entry in entries:
                            if total_count >= limit:
                                break
                            metadata = _build_metadata_from_filename(entry["path"], entry.get("size_bytes"))
                            files_info.append({
                                "filename": metadata["filename"],
                                "category": "FadShot",
                                "subcategory": sub_name,
                                "remote_path": entry["path"],
                                "base_path": base,
                                "storage_type": storage_type,
                                "metadata": metadata
                            })
                            total_count += 1
                        if total_count >= limit:
                            break

            for cat_name, cat_info in location.get("categories", {}).items():
                if category and cat_name.lower() != category.lower():
                    continue
                if not cat_info.get("exists"):
                    continue

                is_custom_root = cat_name == "CustomRoot" or layout == "flat"
                is_root_media = cat_name == "Root"
                if cat_name == "Forensics":
                    files = [f for f in _find_media_files(device, cat_info["path"]) if f.endswith('.jpg')]
                    for remote_path in files:
                        if total_count >= limit:
                            break
                        metadata = _build_metadata_from_filename(remote_path, None)
                        files_info.append({
                            "filename": metadata["filename"],
                            "category": "Forensics",
                            "subcategory": "Snapshots",
                            "remote_path": remote_path,
                            "base_path": base,
                            "storage_type": storage_type,
                            "metadata": metadata
                        })
                        total_count += 1
                    continue

                subdirs = cat_info.get("subdirs", {})
                remaining = limit - total_count
                if remaining <= 0:
                    break

                if subdirs:
                    for sub_name, sub_info in subdirs.items():
                        if camera and sub_name.lower() != camera.lower():
                            continue
                        if not sub_info.get("exists"):
                            continue
                        remaining = limit - total_count
                        if remaining <= 0:
                            break
                        entries = _list_media_entries_from_ls(device, sub_info["path"])
                        for entry in entries:
                            if total_count >= limit:
                                break
                            metadata = _build_metadata_from_filename(entry["path"], entry.get("size_bytes"))
                            files_info.append({
                                "filename": metadata["filename"],
                                "category": cat_name,
                                "subcategory": sub_name,
                                "remote_path": entry["path"],
                                "base_path": base,
                                "storage_type": storage_type,
                                "metadata": metadata
                            })
                            total_count += 1
                else:
                    remaining = limit - total_count
                    if remaining <= 0:
                        break
                    entries = _list_media_entries_from_ls(
                        device,
                        cat_info["path"],
                        fadcam_only=is_custom_root or is_root_media
                    )
                    for entry in entries:
                        if total_count >= limit:
                            break
                        metadata = _build_metadata_from_filename(entry["path"], entry.get("size_bytes"))
                        files_info.append({
                            "filename": metadata["filename"],
                            "category": cat_name,
                            "subcategory": None,
                            "remote_path": entry["path"],
                            "base_path": base,
                            "storage_type": storage_type,
                            "metadata": metadata
                        })
                        total_count += 1

        if base_path and not seen_any_location:
            await _ctx_warning(ctx, "base_path not found. Returning available base paths.")
            return json.dumps({
                "error": f"base_path not found: {base_path}",
                "available_base_paths": [loc.get("base_path") for loc in structure.get("structures", [])]
            })

        if total_count == 0:
            await _ctx_info(
                ctx,
                "No files found for the requested filters. Try a different base_path or category."
            )

        return json.dumps({
            "device": device,
            "package": package,
            "total_files": total_count,
            "files": files_info,
            "limit_applied": limit,
            "filters_applied": {
                "category": category,
                "camera": camera,
                "base_path": base_path
            }
        })

    except Exception as e:
        return json.dumps({"error": str(e)})
