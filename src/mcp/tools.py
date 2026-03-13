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
    pattern = r'^(\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})\s+(\d+)\s+(\d+)\s+([VDIWEF])\s+([^:]+):\s*(.*)$'
    
    match = re.match(pattern, line)
    if not match:
        return None
    
    timestamp, pid, tid, level, tag, message = match.groups()
    
    level_map = {'V': 'VERBOSE', 'D': 'DEBUG', 'I': 'INFO', 'W': 'WARNING', 'E': 'ERROR', 'F': 'FATAL'}
    
    return LogLine(
        timestamp=timestamp,
        level=level_map.get(level, level),
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
    Get list of connected Android devices.
    
    Returns JSON list of DeviceInfo objects.
    """
    try:
        serials = get_adb_devices()
        
        devices = []
        for serial in serials:
            try:
                # Get device properties
                model_output = _run_adb_command(serial, ['shell', 'getprop', 'ro.product.model'])
                model = model_output.strip() if model_output and not model_output.startswith('Error') else 'Unknown'
                
                manufacturer_output = _run_adb_command(serial, ['shell', 'getprop', 'ro.product.manufacturer'])
                manufacturer = manufacturer_output.strip() if manufacturer_output and not manufacturer_output.startswith('Error') else 'Unknown'
                
                android_version_output = _run_adb_command(serial, ['shell', 'getprop', 'ro.build.version.release'])
                android_version = android_version_output.strip() if android_version_output and not android_version_output.startswith('Error') else 'Unknown'
                
                device = DeviceInfo(
                    serial=serial,
                    name=f"{manufacturer} {model}",
                    android_version=android_version,
                    model=model,
                    manufacturer=manufacturer
                )
                devices.append(device.model_dump())
            except Exception as e:
                # Still add device even if we can't get properties
                device = DeviceInfo(serial=serial, name="Unknown", android_version="Unknown")
                devices.append(device.model_dump())
        
        return json.dumps({"devices": devices, "count": len(devices)})
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


async def impl_get_app_processes(device: str, package: Optional[str] = None) -> str:
    """
    Get running processes for an app or all processes.
    
    Args:
        device: Device serial
        package: Optional package name to filter by
    
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
            
            if package and package not in proc_name:
                continue
            
            try:
                process = ProcessInfo(
                    pid=int(pid_str),
                    ppid=int(ppid_str),
                    name=proc_name,
                    user=user,
                    vsize=int(vsize_str),
                    rss=int(rss_str)
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
                package = PackageInfo(name=package_name)
                packages.append(package.model_dump())
        
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
        exception_message = ""
        
        # Find exception line (usually first line or line with "Exception")
        for line in lines:
            if 'Exception' in line or 'Error' in line:
                exception_type = line.strip()
                if ':' in exception_type:
                    exception_type, exception_message = exception_type.split(':', 1)
                    exception_message = exception_message.strip()
                break
        
        # Extract stack frames
        frames = []
        for line in lines:
            if 'at ' in line:
                frames.append(line.strip())
        
        stack_trace = StackTraceInfo(
            exception_type=exception_type,
            exception_message=exception_message,
            stack_frames=frames,
            raw_trace=trace
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
        
        if 'ANR in ' in logcat or 'Application Not Responding' in logcat:
            error_type = "ANR"
            severity = "HIGH"
        elif 'OutOfMemoryError' in logcat or 'Native crash' in logcat:
            error_type = "OOM"
            severity = "CRITICAL"
        elif 'FATAL EXCEPTION' in logcat or 'AndroidRuntime' in logcat:
            error_type = "CRASH"
            severity = "CRITICAL"
        elif 'NullPointerException' in logcat:
            error_type = "NPE"
            severity = "HIGH"
        elif 'SecurityException' in logcat:
            error_type = "SECURITY"
            severity = "HIGH"
        elif 'IOException' in logcat:
            error_type = "IO"
            severity = "MEDIUM"
        elif 'Timeout' in logcat or 'TIMEOUT' in logcat:
            error_type = "TIMEOUT"
            severity = "MEDIUM"
        
        # Extract key lines
        key_lines = []
        for line in logcat.split('\n'):
            if any(keyword in line for keyword in ['Exception', 'Error', 'FATAL', 'ANR']):
                key_lines.append(line.strip())
        
        error_analysis = ErrorAnalysis(
            error_type=error_type,
            severity=severity,
            description=f"Detected {error_type} in logcat",
            key_lines=key_lines[:5],
            suggestions=[
                f"Review logs for {error_type}",
                "Check device memory usage",
                "Look for permission issues"
            ]
        )
        
        return json.dumps(error_analysis.model_dump())
    except Exception as e:
        return json.dumps({"error": str(e)})


async def impl_analyze_performance(device: str) -> str:
    """
    Analyze device performance (CPU, memory, FPS).
    
    Args:
        device: Device serial
    
    Returns:
        JSON with PerformanceReport object
    """
    try:
        # Get memory info
        meminfo_output = _run_adb_command(device, ['shell', 'cat', '/proc/meminfo'])
        
        total_mem = 0
        available_mem = 0
        
        for line in meminfo_output.split('\n'):
            if line.startswith('MemTotal:'):
                total_mem = int(line.split()[1])
            elif line.startswith('MemAvailable:'):
                available_mem = int(line.split()[1])
        
        used_mem = total_mem - available_mem
        memory_usage = (used_mem / total_mem * 100) if total_mem > 0 else 0
        
        # Get CPU info  
        cpu_output = _run_adb_command(device, ['shell', 'top', '-n', '1'])
        
        # Create metrics
        metrics = PerformanceMetrics(
            cpu_usage=0,  # Would need more complex parsing
            memory_usage=memory_usage,
            memory_total_mb=total_mem / 1024,
            memory_used_mb=used_mem / 1024,
            fps=0,  # Would need SurfaceFlinger data
            battery_temp=0,
            battery_level=0
        )
        
        report = PerformanceReport(
            device=device,
            timestamp="",
            metrics=metrics,
            potential_issues=[
                "High memory usage" if memory_usage > 80 else "Memory usage normal"
            ]
        )
        
        return json.dumps(report.model_dump())
    except Exception as e:
        return json.dumps({"error": str(e)})


async def impl_analyze_memory_leak(device: str) -> str:
    """
    Analyze potential memory leaks from logcat.
    
    Args:
        device: Device serial
    
    Returns:
        JSON with MemoryAnalysis object
    """
    try:
        logcat_output = _run_adb_command(device, ['logcat', '-d', '-v', 'threadtime'])
        
        memory_allocs = []
        gc_events = []
        
        for line in logcat_output.split('\n'):
            if 'GC_EXPLICIT' in line or 'GC_CONCURRENT' in line:
                gc_events.append(line.strip())
            elif 'OutOfMemory' in line or 'Memory pressure' in line:
                alloc = MemoryAllocation(
                    size_bytes=0,
                    tag="OutOfMemory",
                    timestamp=""
                )
                memory_allocs.append(alloc.model_dump())
        
        analysis = MemoryAnalysis(
            device=device,
            allocations=memory_allocs,
            gc_events=gc_events[:20],
            potential_leaks=[
                "High GC frequency detected" if len(gc_events) > 10 else "GC events normal"
            ],
            recommendations=[
                "Review object lifecycle",
                "Check for circular references",
                "Profile with Android Studio"
            ]
        )
        
        return json.dumps(analysis.model_dump())
    except Exception as e:
        return json.dumps({"error": str(e)})


async def impl_trace_network_calls(device: str) -> str:
    """
    Trace network calls from logcat (HTTP, DNS, etc).
    
    Args:
        device: Device serial
    
    Returns:
        JSON with NetworkTrace object
    """
    try:
        logcat_output = _run_adb_command(device, ['logcat', '-d', '-v', 'threadtime'])
        
        calls = []
        
        # Simple pattern matching for common network operations
        for line in logcat_output.split('\n'):
            if any(keyword in line for keyword in ['http', 'HTTP', 'okhttp', 'retrofit', 'volley']):
                call = NetworkCall(
                    method="GET",
                    url="",
                    status_code=200,
                    latency_ms=0,
                    timestamp="",
                    bytes_sent=0,
                    bytes_received=0
                )
                calls.append(call.model_dump())
        
        trace = NetworkTrace(
            device=device,
            calls=calls[:50],
            total_requests=len(calls),
            total_errors=0
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
