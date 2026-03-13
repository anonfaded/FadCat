"""FadCat MCP Server - Model Context Protocol implementation for Android debugging."""

import sys
import logging
from typing import Any, Optional, List
from fastmcp import FastMCP
import json

# Setup logging to stderr (MCP requirement - stdout is reserved for protocol)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

from src.version import __version__, __author__, __app_name__

# Create MCP server with FastMCP
server = FastMCP(__app_name__, __version__)

# Module-level state
_server_start_time = None
_active_connections = 0

# ============================================================================
# TOOLS - Android Debugging Operations
# ============================================================================

@server.tool()
async def get_devices() -> str:
    """Get list of connected Android devices"""
    logger.info("Tool called: get_devices")
    try:
        from src.mcp import tools
        result = await tools.impl_get_devices()
        return json.dumps(result) if isinstance(result, dict) else result
    except Exception as e:
        logger.exception("Error in get_devices")
        return f"Error: {str(e)}"


@server.tool()
async def get_logcat_stream(
    device: str,
    package: Optional[str] = None,
    level: str = "I",
    lines: int = 100
) -> str:
    """Get logcat stream from a device with optional filters
    
    Args:
        device: Device serial number
        package: Optional package name to filter by
        level: Minimum log level (V/D/I/W/E/F)
        lines: Number of lines to retrieve
    """
    logger.info(f"Tool called: get_logcat_stream for device {device}")
    try:
        from src.mcp import tools
        result = await tools.impl_get_logcat_stream(device, package, level, lines)
        return json.dumps(result) if isinstance(result, dict) else result
    except Exception as e:
        logger.exception("Error in get_logcat_stream")
        return f"Error: {str(e)}"


@server.tool()
async def search_logs(
    query: str,
    tag_filter: Optional[str] = None,
    level_filter: Optional[str] = None,
    limit: int = 50
) -> str:
    """Search in logcat history
    
    Args:
        query: Search query string
        tag_filter: Optional tag filter
        level_filter: Optional log level filter
        limit: Maximum number of results
    """
    logger.info(f"Tool called: search_logs with query '{query}'")
    try:
        from src.mcp import tools
        result = await tools.impl_search_logs(query, tag_filter, level_filter, limit)
        return json.dumps(result) if isinstance(result, dict) else result
    except Exception as e:
        logger.exception("Error in search_logs")
        return f"Error: {str(e)}"


@server.tool()
async def filter_by_level(device: str, level: str) -> str:
    """Filter current logcat by severity level
    
    Args:
        device: Device serial number
        level: Log level (V/D/I/W/E/F)
    """
    logger.info(f"Tool called: filter_by_level for device {device} with level {level}")
    try:
        from src.mcp import tools
        result = await tools.impl_filter_by_level(device, level)
        return json.dumps(result) if isinstance(result, dict) else result
    except Exception as e:
        logger.exception("Error in filter_by_level")
        return f"Error: {str(e)}"


@server.tool()
async def get_app_processes(device: str, package: str) -> str:
    """Get running processes for an app
    
    Args:
        device: Device serial number
        package: Package name
    """
    logger.info(f"Tool called: get_app_processes for {package} on {device}")
    try:
        from src.mcp import tools
        result = await tools.impl_get_app_processes(device, package)
        return result if isinstance(result, str) else json.dumps(result)
    except Exception as e:
        logger.exception("Error in get_app_processes")
        return json.dumps({"error": str(e)})


@server.tool()
async def get_connected_packages(device: str) -> str:
    """Get all packages connected to ADB on device
    
    Args:
        device: Device serial number
    """
    logger.info(f"Tool called: get_connected_packages for device {device}")
    try:
        from src.mcp import tools
        result = await tools.impl_get_connected_packages(device)
        return json.dumps(result) if isinstance(result, dict) else result
    except Exception as e:
        logger.exception("Error in get_connected_packages")
        return f"Error: {str(e)}"


@server.tool()
async def parse_stacktrace(stacktrace: str) -> str:
    """Parse Android stacktrace and identify issues
    
    Args:
        stacktrace: The stack trace to parse
    """
    logger.info("Tool called: parse_stacktrace")
    try:
        from src.mcp import tools
        result = await tools.impl_parse_stacktrace(stacktrace)
        return json.dumps(result) if isinstance(result, dict) else result
    except Exception as e:
        logger.exception("Error in parse_stacktrace")
        return f"Error: {str(e)}"


@server.tool()
async def detect_error_type(logs: str) -> str:
    """Detect error types from logs
    
    Args:
        logs: Log content to analyze
    """
    logger.info("Tool called: detect_error_type")
    try:
        from src.mcp import tools
        result = await tools.impl_detect_error_type(logs)
        return json.dumps(result) if isinstance(result, dict) else result
    except Exception as e:
        logger.exception("Error in detect_error_type")
        return f"Error: {str(e)}"


@server.tool()
async def analyze_performance(device: str, package: str, duration: int = 10) -> str:
    """Analyze app performance metrics
    
    Args:
        device: Device serial number
        package: Package name
        duration: Duration to monitor in seconds
    """
    logger.info(f"Tool called: analyze_performance for {package} on {device} for {duration}s")
    try:
        from src.mcp import tools
        result = await tools.impl_analyze_performance(device, package, duration)
        return result if isinstance(result, str) else json.dumps(result)
    except Exception as e:
        logger.exception("Error in analyze_performance")
        return json.dumps({"error": str(e)})


@server.tool()
async def trace_network_calls(device: str, package: str) -> str:
    """Trace network calls from an app
    
    Args:
        device: Device serial number
        package: Package name
    """
    logger.info(f"Tool called: trace_network_calls for {package} on {device}")
    try:
        from src.mcp import tools
        result = await tools.impl_trace_network_calls(device, package)
        return result if isinstance(result, str) else json.dumps(result)
    except Exception as e:
        logger.exception("Error in trace_network_calls")
        return json.dumps({"error": str(e)})


@server.tool()
async def analyze_memory_leak(device: str, package: str) -> str:
    """Analyze memory leaks in an app
    
    Args:
        device: Device serial number
        package: Package name
    """
    logger.info(f"Tool called: analyze_memory_leak for {package} on {device}")
    try:
        from src.mcp import tools
        result = await tools.impl_analyze_memory_leak(device, package)
        return result if isinstance(result, str) else json.dumps(result)
    except Exception as e:
        logger.exception("Error in analyze_memory_leak")
        return json.dumps({"error": str(e)})


@server.tool()
async def clear_logcat(device: str) -> str:
    """Clear logcat buffer on device
    
    Args:
        device: Device serial number
    """
    logger.info(f"Tool called: clear_logcat for device {device}")
    try:
        from src.mcp import tools
        result = await tools.impl_clear_logcat(device)
        return json.dumps(result) if isinstance(result, dict) else result
    except Exception as e:
        logger.exception("Error in clear_logcat")
        return f"Error: {str(e)}"


@server.tool()
async def export_logs(device: str, format: str = "json", lines: int = 1000) -> str:
    """Export logcat to file
    
    Args:
        device: Device serial number
        format: Export format (json, csv, html)
        lines: Number of lines to export
    """
    logger.info(f"Tool called: export_logs for device {device} in {format} format")
    try:
        from src.mcp import tools
        result = await tools.impl_export_logs(device, format, lines)
        return json.dumps(result) if isinstance(result, dict) else result
    except Exception as e:
        logger.exception("Error in export_logs")
        return f"Error: {str(e)}"


@server.tool()
async def get_system_info(device: str) -> str:
    """Get comprehensive system information
    
    Args:
        device: Device serial number
    """
    logger.info(f"Tool called: get_system_info for device {device}")
    try:
        from src.mcp import tools
        result = await tools.impl_get_system_info(device)
        return result if isinstance(result, str) else json.dumps(result)
    except Exception as e:
        logger.exception("Error in get_system_info")
        return json.dumps({"error": str(e)})


# ============================================================================
# RESOURCES - URI-based Android data access
# ============================================================================

@server.resource("logcat://device/{device_serial}")
async def logcat_device_resource(device_serial: str) -> str:
    """Current logcat stream from a device"""
    logger.info(f"Resource accessed: logcat://device/{device_serial}")
    try:
        from src.mcp import resources
        return await resources.read_logcat_device_resource(device_serial)
    except Exception as e:
        logger.exception(f"Error reading logcat resource for {device_serial}")
        return json.dumps({"error": str(e)})


@server.resource("android://devices")
async def android_devices_resource() -> str:
    """List of connected Android devices"""
    logger.info("Resource accessed: android://devices")
    try:
        from src.mcp import resources
        return await resources.read_android_devices_resource()
    except Exception as e:
        logger.exception("Error reading devices resource")
        return json.dumps({"error": str(e)})


@server.resource("android://packages/{device_serial}")
async def android_packages_resource(device_serial: str) -> str:
    """Installed packages on a device"""
    logger.info(f"Resource accessed: android://packages/{device_serial}")
    try:
        from src.mcp import resources
        return await resources.read_android_packages_resource(device_serial)
    except Exception as e:
        logger.exception(f"Error reading packages resource for {device_serial}")
        return json.dumps({"error": str(e)})


@server.resource("android://processes/{device_serial}")
async def android_processes_resource(device_serial: str) -> str:
    """Running processes on a device"""
    logger.info(f"Resource accessed: android://processes/{device_serial}")
    try:
        from src.mcp import resources
        return await resources.read_android_processes_resource(device_serial)
    except Exception as e:
        logger.exception(f"Error reading processes resource for {device_serial}")
        return json.dumps({"error": str(e)})


# ============================================================================
# PROMPTS - AI-guided debugging workflows
# ============================================================================

@server.prompt()
async def debug_crash_analyzer() -> str:
    """Crash/Exception Analysis
    
    Helps analyze crash logs and exceptions from the logcat stream.
    Identify the root cause and potential fixes.
    """
    logger.info("Prompt accessed: debug-crash-analyzer")
    try:
        from src.mcp import prompts
        return await prompts.get_prompt("debug-crash-analyzer")
    except Exception as e:
        logger.exception("Error getting crash analyzer prompt")
        return f"Error: {str(e)}"


@server.prompt()
async def logcat_summarizer() -> str:
    """Logcat Analysis Summary
    
    Summarize what's happening in the app from logcat output.
    Identify errors, warnings, and important events.
    """
    logger.info("Prompt accessed: logcat-summarizer")
    try:
        from src.mcp import prompts
        return await prompts.get_prompt("logcat-summarizer")
    except Exception as e:
        logger.exception("Error getting logcat summarizer prompt")
        return f"Error: {str(e)}"


@server.prompt()
async def performance_monitor() -> str:
    """Performance Optimization
    
    Find performance bottlenecks and optimization opportunities.
    Analyze CPU usage, memory, and frame rates.
    """
    logger.info("Prompt accessed: performance-monitor")
    try:
        from src.mcp import prompts
        return await prompts.get_prompt("performance-monitor")
    except Exception as e:
        logger.exception("Error getting performance monitor prompt")
        return f"Error: {str(e)}"


@server.prompt()
async def network_debugger() -> str:
    """Network Debugging
    
    Trace and debug network calls and connectivity issues.
    Analyze API responses and network errors.
    """
    logger.info("Prompt accessed: network-debugger")
    try:
        from src.mcp import prompts
        return await prompts.get_prompt("network-debugger")
    except Exception as e:
        logger.exception("Error getting network debugger prompt")
        return f"Error: {str(e)}"


# ============================================================================
# SERVER ENTRY POINT
# ============================================================================

def main():
    """Run MCP server on stdio."""
    # Print FadCat branding
    print("\n" + "="*70)
    print("┌" + "─"*68 + "┐")
    print("│ " + " "*66 + " │")
    print("│ " + "FadCat MCP Server".center(66) + " │")
    print("│ " + f"v{__version__} - Android Debug Companion".center(66) + " │")
    print("│ " + " "*66 + " │")
    print("└" + "─"*68 + "┘")
    print("="*70 + "\n")
    
    logger.info(f"Starting FadCat MCP Server ({__app_name__} v{__version__})")
    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("MCP Server stopped by user")
    except Exception as e:
        logger.exception(f"MCP Server fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
