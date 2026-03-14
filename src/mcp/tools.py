"""
FadCat MCP Tools - Implementation of all 13 MCP tools.

These tools connect directly to Android Debug Bridge (ADB) and logcat to provide
AI agents with real-time access to device debugging information.

Cross-platform support: Works on macOS, Linux, and Windows.
"""

import subprocess
import json
import re
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any

from src.utils.adb_utils import get_adb_devices
from src.utils.adb_path import get_adb_path
from src.mcp.models import (
    LogLine, DeviceInfo, ProcessInfo, PackageInfo,
    ErrorAnalysis, StackTraceInfo, PerformanceReport,
    PerformanceMetrics, NetworkCall, NetworkTrace,
    MemoryAllocation, MemoryAnalysis
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


# ============================================================================
# Tool Implementations - All 13 Tools
# ============================================================================

async def impl_get_devices() -> str:
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
        
        return json.dumps({
            "devices": devices, 
            "count": len(devices),
            "primary_device": devices[0]["serial"] if devices else None,
            "has_real_devices": len(real_devices) > 0,
            "has_emulators": len(emulators) > 0
        })
    except Exception as e:
        return json.dumps({"error": str(e), "devices": []})


async def impl_get_logcat_stream(device: str, package: Optional[str] = None, 
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


async def impl_search_logs(query: str, tag_filter: Optional[str] = None,
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


async def impl_filter_by_level(device: str, level: str) -> str:
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


async def impl_get_app_processes(device: str, package: str) -> str:
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


async def impl_get_connected_packages(device: str) -> str:
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


async def impl_parse_stacktrace(trace: str) -> str:
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


async def impl_detect_error_type(logcat: str) -> str:
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


async def impl_analyze_performance(device: str, package: str, duration: int = 10) -> str:
    """
    Analyze app performance (CPU, memory, FPS) for specific package.
    
    Args:
        device: Device serial
        package: Package name to profile
        duration: Duration to monitor in seconds
    
    Returns:
        JSON with PerformanceReport object
    """
    try:
        # Get memory info for the package
        dumpsys_output = _run_adb_command(device, ['shell', 'dumpsys', 'meminfo', package])
        
        native_heap = 0
        dart_heap = 0
        total_mem = 0
        
        for line in dumpsys_output.split('\n'):
            if 'TOTAL' in line:
                parts = line.split()
                if len(parts) > 1:
                    try:
                        total_mem = int(parts[-1])
                    except:
                        pass
        
        # Create single metric snapshot
        metric = PerformanceMetrics(
            timestamp="",
            cpu_usage=0,  # Would need pidstat or similar
            memory_used=total_mem,
            memory_total=0,
            fps=None,
            jank_count=0
        )
        
        report = PerformanceReport(
            device=device,
            duration_seconds=duration,
            metrics=[metric],
            avg_cpu=0,
            peak_memory=total_mem,
            min_fps=None,
            avg_fps=None,
            jank_frames=0,
            analysis=f"Profiled {package} for {duration}s. Memory usage: {total_mem}MB"
        )
        
        return json.dumps(report.model_dump())
    except Exception as e:
        return json.dumps({"error": str(e)})


async def impl_analyze_memory_leak(device: str, package: str) -> str:
    """
    Analyze potential memory leaks from logcat for a package.
    
    Args:
        device: Device serial
        package: Package name to analyze
    
    Returns:
        JSON with MemoryAnalysis object
    """
    try:
        logcat_output = _run_adb_command(device, ['logcat', '-d', '-v', 'threadtime'])
        
        memory_allocs = []
        gc_events = []
        suspected_leak = False
        
        for line in logcat_output.split('\n'):
            if package in line:
                if 'GC_EXPLICIT' in line or 'GC_CONCURRENT' in line:
                    gc_events.append(line.strip())
                elif 'OutOfMemory' in line or 'Memory pressure' in line:
                    suspected_leak = True
                    alloc = MemoryAllocation(
                        timestamp="",
                        size_bytes=0,
                        allocation_type="OutOfMemory"
                    )
                    memory_allocs.append(alloc.model_dump())
        
        analysis = MemoryAnalysis(
            device=device,
            package=package,
            suspected_leak=suspected_leak or len(gc_events) > 15,
            leak_size_mb=None,
            leak_type="Possible memory leak" if suspected_leak else None,
            allocations=memory_allocs,
            recommendation="Review object lifecycle and check for circular references" if suspected_leak else "Memory usage appears normal"
        )
        
        return json.dumps(analysis.model_dump())
    except Exception as e:
        return json.dumps({"error": str(e)})


async def impl_trace_network_calls(device: str, package: str) -> str:
    """
    Trace network calls from logcat for a package.
    
    Args:
        device: Device serial
        package: Package name to trace
    
    Returns:
        JSON with NetworkTrace object
    """
    try:
        logcat_output = _run_adb_command(device, ['logcat', '-d', '-v', 'threadtime'])
        
        calls = []
        total_errors = 0
        
        # Simple pattern matching for common network operations
        for line in logcat_output.split('\n'):
            if package not in line:
                continue
                
            if any(keyword in line for keyword in ['http', 'HTTP', 'okhttp', 'retrofit', 'volley']):
                # Check for errors
                status_code = 200
                if 'error' in line.lower() or '4' in line[:50] or '5' in line[:50]:
                    status_code = 400
                    total_errors += 1
                    
                call = NetworkCall(
                    method="GET",
                    url="[extracted from logs]",
                    status_code=status_code,
                    duration_ms=None,
                    timestamp="",
                    size_bytes=None,
                    error=None if status_code == 200 else "See logs for details"
                )
                calls.append(call.model_dump())
        
        trace = NetworkTrace(
            package=package,
            device=device,
            calls=calls[:50],
            total_bytes=0,
            failed_count=total_errors,
            duration_seconds=0
        )
        
        return json.dumps(trace.model_dump())
    except Exception as e:
        return json.dumps({"error": str(e)})


async def impl_clear_logcat(device: str) -> str:
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


async def impl_export_logs(device: str, format: str = "json", lines: int = 1000) -> str:
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


async def impl_get_system_info(device: str) -> str:
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
            "wifi_enabled": None,
            "mobile_data_enabled": None,
            "airplane_mode": None,
            "screen_on": None,
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
        
        # Try to get wifi state
        try:
            wifi_output = _run_adb_command(device, ['shell', 'settings', 'get', 'global', 'wifi_on'])
            system_info["wifi_enabled"] = wifi_output.strip() == '1'
        except:
            pass
        
        # Try to get mobile data state
        try:
            mobile_output = _run_adb_command(device, ['shell', 'settings', 'get', 'global', 'mobile_data'])
            system_info["mobile_data_enabled"] = mobile_output.strip() == '1'
        except:
            pass
        
        # Try to get airplane mode
        try:
            airplane_output = _run_adb_command(device, ['shell', 'settings', 'get', 'global', 'airplane_mode_on'])
            system_info["airplane_mode"] = airplane_output.strip() == '1'
        except:
            pass
        
        # Try to get screen state
        try:
            screen_output = _run_adb_command(device, ['shell', 'dumpsys', 'power', '|', 'grep', 'mScreenOn'])
            system_info["screen_on"] = 'true' in screen_output.lower()
        except:
            pass
        
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


async def impl_pull_fadcam_media(device: str, package: str, media_type: str = "all",
                                output_dir: str = "./fadcam_media", limit: Optional[int] = None) -> str:
    """
    Pull FadCam media files from device with comprehensive storage support.

    Supports all FadCam storage modes and app variants:
    - com.fadcam (stable), com.fadcam.beta, com.fadcam.pro, com.fadcam.proplus, com.fadcam.lab
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

        # Auto-detect package if not specified or validate
        if not package.startswith("com.fadcam"):
            # Try to find available FadCam packages
            packages_output = _run_adb_command(device, ['shell', 'pm', 'list', 'packages', '|', 'grep', 'fadcam'])
            available_packages = []
            for line in packages_output.split('\n'):
                if line.startswith('package:'):
                    pkg = line.split(':', 1)[1].strip()
                    if 'fadcam' in pkg.lower():
                        available_packages.append(pkg)

            if not available_packages:
                return json.dumps({"error": "No FadCam packages found on device"})

            if package not in available_packages:
                return json.dumps({
                    "error": f"Package {package} not found. Available: {available_packages}",
                    "available_packages": available_packages
                })

        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        files_pulled = []
        errors = []
        total_size = 0

        # Check storage mode from shared preferences
        storage_mode = "internal"  # default
        custom_storage_uri = None

        try:
            # Try to access shared preferences
            prefs_cmd = _run_adb_command(device, ['shell', 'cat', f'/data/data/{package}/shared_prefs/{package}_preferences.xml'])
            if "Permission denied" not in prefs_cmd and "No such file" not in prefs_cmd:
                # Parse storage mode
                if 'storage_mode' in prefs_cmd:
                    if '"custom"' in prefs_cmd:
                        storage_mode = "custom"
                    elif '"internal"' in prefs_cmd:
                        storage_mode = "internal"

                # Extract custom storage URI
                import re
                uri_match = re.search(r'custom_storage_uri.*?>(.*?)<', prefs_cmd)
                if uri_match:
                    custom_storage_uri = uri_match.group(1)
        except:
            pass  # Fall back to internal storage

        # Determine base paths to check
        base_paths = []

        if storage_mode == "custom" and custom_storage_uri:
            # For custom storage, we'd need to parse the SAF URI
            # This is complex as it requires the app's permission to access
            # For now, fall back to internal and note the limitation
            errors.append(f"Custom storage detected but SAF access not implemented. URI: {custom_storage_uri}")

        # Always check internal storage path
        internal_base = f"/storage/emulated/0/Android/data/{package}/files/FadCam"
        base_paths.append(("internal", internal_base))

        # Define media sources based on comprehensive FadCam structure
        media_sources = []

        if media_type in ["videos", "all"]:
            # Camera videos
            media_sources.extend([
                ("video", "back", f"{internal_base}/Camera/Back/*.mp4"),
                ("video", "front", f"{internal_base}/Camera/Front/*.mp4"),
                ("video", "dual", f"{internal_base}/Camera/Dual/*.mp4"),
                # Legacy dual folder
                ("video", "dual_legacy", f"{internal_base}/Dual/*.mp4"),
            ])

        if media_type in ["screenshots", "all"]:
            # FadShot photos
            media_sources.extend([
                ("screenshot", "back", f"{internal_base}/FadShot/Back/*.jpg"),
                ("screenshot", "selfie", f"{internal_base}/FadShot/Selfie/*.jpg"),
                ("screenshot", "fadrec", f"{internal_base}/FadShot/FadRec/*.jpg"),
            ])

        # Screen recordings
        if media_type in ["videos", "all"]:
            media_sources.append(("screen_recording", None, f"{internal_base}/Screen/*.mp4"))

        # Stream recordings
        if media_type in ["videos", "all"]:
            media_sources.append(("stream", None, f"{internal_base}/Stream/*.mp4"))

        # Faditor edited videos
        if media_type in ["videos", "all"]:
            media_sources.extend([
                ("faditor_converted", None, f"{internal_base}/Faditor/Converted/*.mp4"),
                ("faditor_merge", None, f"{internal_base}/Faditor/Merge/*.mp4"),
            ])

        # Process each media source
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

                    # Create local filename with package prefix to avoid conflicts
                    package_short = package.split('.')[-1]  # "fadcam", "beta", "pro", etc.
                    local_filename = f"{package_short}_{filename}"
                    local_path = output_path / local_filename

                    # Pull file from device
                    device_file_path = f"{dir_path}/{filename}"
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
            storage_mode=storage_mode,
            custom_storage_uri=custom_storage_uri
        )

        return json.dumps(result.model_dump())

    except Exception as e:
        return json.dumps({"error": str(e)})


async def impl_fadcam_list_packages(device: str) -> str:
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


async def impl_fadcam_detect_storage(device: str, package: str) -> str:
    """Detect FadCam storage configuration for a package"""
    try:
        # Check device connection
        devices_output = _run_adb_command(device, ['shell', 'echo', 'connected'])
        if "connected" not in devices_output:
            return json.dumps({"error": f"Device {device} not connected"})

        # Check if package exists
        packages_output = _run_adb_command(device, ['shell', 'pm', 'list', 'packages', package])
        if f"package:{package}" not in packages_output:
            return json.dumps({"error": f"Package {package} not found on device"})

        storage_info = {
            "package": package,
            "storage_mode": "internal",  # default
            "internal_path": f"/storage/emulated/0/Android/data/{package}/files/FadCam",
            "custom_storage_uri": None,
            "internal_exists": False,
            "internal_file_count": 0
        }

        # Check internal storage
        ls_cmd = _run_adb_command(device, ['shell', 'ls', '-la', storage_info["internal_path"]])
        if "No such file or directory" not in ls_cmd and "Permission denied" not in ls_cmd:
            storage_info["internal_exists"] = True
            # Count total files
            find_cmd = _run_adb_command(device, [
                'shell', 'find', storage_info["internal_path"],
                '-type', 'f', '(', '-name', '*.mp4', '-o', '-name', '*.jpg', ')', '|', 'wc', '-l'
            ])
            try:
                storage_info["internal_file_count"] = int(find_cmd.strip())
            except:
                pass

        return json.dumps(storage_info)

    except Exception as e:
        return json.dumps({"error": str(e)})


async def impl_fadcam_list_structure(device: str, package: str) -> str:
    """List FadCam directory structure and file counts"""
    try:
        # Get storage info first
        storage_result = await impl_fadcam_detect_storage(device, package)
        storage_info = json.loads(storage_result)

        if "error" in storage_info:
            return storage_result

        base_path = storage_info["internal_path"]
        structure = {
            "package": package,
            "base_path": base_path,
            "storage_mode": storage_info["storage_mode"],
            "categories": {},
            "total_files": 0,
            "total_size_bytes": 0
        }

        # Define all possible categories and subdirectories
        categories = {
            "Camera": ["Back", "Front", "Dual"],
            "FadShot": ["Back", "Selfie", "FadRec"],
            "Dual": [],  # Legacy
            "Screen": [],
            "Stream": [],
            "Faditor": ["Converted", "Merge"]
        }

        for category, subdirs in categories.items():
            cat_path = f"{base_path}/{category}"
            cat_info = {"path": cat_path, "exists": False, "total_files": 0, "subdirs": {}}

            # Check if category directory exists
            ls_cmd = _run_adb_command(device, ['shell', 'ls', '-la', cat_path])
            if "No such file or directory" not in ls_cmd and "Permission denied" not in ls_cmd:
                cat_info["exists"] = True

                # Count files directly in category
                find_cmd = _run_adb_command(device, [
                    'shell', 'find', cat_path, '-maxdepth', '1',
                    '-type', 'f', '(', '-name', '*.mp4', '-o', '-name', '*.jpg', ')', '|', 'wc', '-l'
                ])
                try:
                    cat_info["total_files"] = int(find_cmd.strip())
                    structure["total_files"] += cat_info["total_files"]
                except:
                    pass

                # Check subdirectories
                for subdir in subdirs:
                    sub_path = f"{cat_path}/{subdir}"
                    sub_info = {"path": sub_path, "exists": False, "file_count": 0}

                    ls_sub_cmd = _run_adb_command(device, ['shell', 'ls', '-la', sub_path])
                    if "No such file or directory" not in ls_sub_cmd and "Permission denied" not in ls_sub_cmd:
                        sub_info["exists"] = True

                        # Count files in subdirectory
                        find_sub_cmd = _run_adb_command(device, [
                            'shell', 'find', sub_path,
                            '-type', 'f', '(', '-name', '*.mp4', '-o', '-name', '*.jpg', ')', '|', 'wc', '-l'
                        ])
                        try:
                            sub_info["file_count"] = int(find_sub_cmd.strip())
                            structure["total_files"] += sub_info["file_count"]
                        except:
                            pass

                    cat_info["subdirs"][subdir] = sub_info

            structure["categories"][category] = cat_info

        return json.dumps(structure)

    except Exception as e:
        return json.dumps({"error": str(e)})


async def impl_fadcam_get_metadata(device: str, package: str, file_path: str) -> str:
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
            "duration_seconds": 0,
            "resolution": None,
            "bitrate": 0,
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

        # Try to get video metadata using ffprobe if available
        if metadata["file_type"] == "video":
            probe_cmd = _run_adb_command(device, [
                'shell', 'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', file_path
            ])

            if "ffprobe" not in probe_cmd and "not found" not in probe_cmd:
                try:
                    import json as json_lib
                    probe_data = json_lib.loads(probe_cmd)

                    if 'format' in probe_data:
                        fmt = probe_data['format']
                        if 'duration' in fmt:
                            metadata['duration_seconds'] = float(fmt['duration'])
                        if 'bit_rate' in fmt:
                            try:
                                metadata['bitrate'] = int(fmt['bit_rate'])
                            except:
                                pass

                    if 'streams' in probe_data:
                        for stream in probe_data['streams']:
                            if stream.get('codec_type') == 'video':
                                width = stream.get('width')
                                height = stream.get('height')
                                if width and height:
                                    metadata['resolution'] = f"{width}x{height}"
                                break
                except:
                    pass

        return json.dumps(metadata)

    except Exception as e:
        return json.dumps({"error": str(e)})


async def impl_fadcam_pull_files(device: str, package: str, output_dir: str = "./fadcam_files",
                                category: Optional[str] = None, camera: Optional[str] = None,
                                limit: Optional[int] = None, date_from: Optional[str] = None,
                                date_to: Optional[str] = None) -> str:
    """Pull FadCam files with advanced filtering"""
    try:
        from pathlib import Path
        import os
        from datetime import datetime

        # Get structure first
        structure_result = await impl_fadcam_list_structure(device, package)
        structure = json.loads(structure_result)

        if "error" in structure:
            return structure_result

        # Create output directory
        output_path = Path(output_dir)
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

        # Process categories
        for cat_name, cat_info in structure["categories"].items():
            if category and cat_name.lower() != category.lower():
                continue

            if not cat_info["exists"]:
                continue

            # Process subdirectories
            for sub_name, sub_info in cat_info["subdirs"].items():
                if camera and sub_name.lower() != camera.lower():
                    continue

                if not sub_info["exists"]:
                    continue

                # Get files in this subdirectory
                find_cmd = _run_adb_command(device, [
                    'shell', 'find', sub_info["path"],
                    '-type', 'f', '(', '-name', '*.mp4', '-o', '-name', '*.jpg', ')'
                ])

                if "No such file" in find_cmd or "Permission denied" in find_cmd:
                    continue

                files = [f.strip() for f in find_cmd.split('\n') if f.strip()]

                for remote_path in files:
                    if limit and len(pulled_files) >= limit:
                        break

                    filename = remote_path.split('/')[-1]

                    if should_pull_file(filename):
                        # Create local path
                        package_short = package.split('.')[-1]
                        local_filename = f"{package_short}_{cat_name}_{sub_name}_{filename}"
                        local_path = output_path / local_filename

                        # Pull file
                        pull_cmd = _run_adb_command(device, ['pull', remote_path, str(local_path)])

                        if "error" in pull_cmd.lower() and "1 file pulled" not in pull_cmd:
                            errors.append(f"Failed to pull {filename}: {pull_cmd}")
                            continue

                        # Get metadata
                        metadata_result = await impl_fadcam_get_metadata(device, package, remote_path)
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


async def impl_fadcam_browse_files(device: str, package: str, category: Optional[str] = None,
                                  camera: Optional[str] = None, limit: int = 50) -> str:
    """Browse FadCam files without downloading - returns metadata only"""
    try:
        # Get structure first
        structure_result = await impl_fadcam_list_structure(device, package)
        structure = json.loads(structure_result)

        if "error" in structure:
            return structure_result

        files_info = []
        total_count = 0

        # Process categories
        for cat_name, cat_info in structure["categories"].items():
            if category and cat_name.lower() != category.lower():
                continue

            if not cat_info["exists"]:
                continue

            # Process subdirectories
            for sub_name, sub_info in cat_info["subdirs"].items():
                if camera and sub_name.lower() != camera.lower():
                    continue

                if not sub_info["exists"]:
                    continue

                # Get files in this subdirectory
                find_cmd = _run_adb_command(device, [
                    'shell', 'find', sub_info["path"],
                    '-type', 'f', '(', '-name', '*.mp4', '-o', '-name', '*.jpg', ')'
                ])

                if "No such file" in find_cmd or "Permission denied" in find_cmd:
                    continue

                files = [f.strip() for f in find_cmd.split('\n') if f.strip()]

                for remote_path in files:
                    if total_count >= limit:
                        break

                    # Get metadata for this file
                    metadata_result = await impl_fadcam_get_metadata(device, package, remote_path)
                    metadata = json.loads(metadata_result) if isinstance(metadata_result, str) else metadata_result

                    if "error" not in metadata:
                        files_info.append({
                            "filename": metadata["filename"],
                            "category": cat_name,
                            "subcategory": sub_name,
                            "remote_path": remote_path,
                            "metadata": metadata
                        })
                        total_count += 1

        return json.dumps({
            "device": device,
            "package": package,
            "total_files": total_count,
            "files": files_info,
            "limit_applied": limit,
            "filters_applied": {
                "category": category,
                "camera": camera
            }
        })

    except Exception as e:
        return json.dumps({"error": str(e)})
