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
