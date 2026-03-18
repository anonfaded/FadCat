"""FadCat MCP Server - Model Context Protocol implementation for Android debugging."""

import sys
import logging
import time
from typing import Any, Optional, List
from fastmcp import FastMCP, Context
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
_last_devices_cache: Optional[dict] = None
_last_devices_at: float = 0.0
_get_devices_repeat: int = 0


async def _ctx_info(ctx: Context, message: str) -> None:
    try:
        await ctx.info(message)
    except Exception:
        pass


async def _ctx_warning(ctx: Context, message: str) -> None:
    try:
        await ctx.warning(message)
    except Exception:
        pass

# ============================================================================
# TOOLS - Android Debugging Operations
# ============================================================================

@server.tool()
async def get_devices(ctx: Context) -> str:
    """Get list of connected Android devices"""
    await _ctx_info(ctx, "Tool called: get_devices")
    logger.info("Tool called: get_devices")
    try:
        from src.mcp import tools
        global _last_devices_cache, _last_devices_at, _get_devices_repeat
        now = time.monotonic()
        if _last_devices_cache and (now - _last_devices_at) < 10:
            _get_devices_repeat += 1
            if _get_devices_repeat >= 2:
                await _ctx_warning(ctx, "Repeated get_devices call; returning cached list. Reuse the last device selection.")
                cached = dict(_last_devices_cache)
                cached.update({
                    "requires_selection": True,
                    "message": "Device already listed. Choose one and do not call get_devices again.",
                    "do_not_call_get_devices_again": True
                })
                if _get_devices_repeat >= 3:
                    cached.update({
                        "tool_loop_detected": True,
                        "error": "Tool loop detected: stop calling get_devices and use selected_device."
                    })
                return json.dumps(cached)
            return json.dumps(_last_devices_cache)

        result = await tools.impl_get_devices(ctx)
        if isinstance(result, str):
            try:
                parsed = json.loads(result)
            except Exception:
                parsed = None
            if isinstance(parsed, dict):
                _last_devices_cache = parsed
            _last_devices_at = now
            _get_devices_repeat = 0
            return result

        if isinstance(result, dict):
            _last_devices_cache = result
        _last_devices_at = now
        _get_devices_repeat = 0
        return json.dumps(result) if isinstance(result, dict) else result
    except Exception as e:
        logger.exception("Error in get_devices")
        await _ctx_warning(ctx, f"Error in get_devices: {e}")
        return f"Error: {str(e)}"


@server.tool()
async def get_logcat_stream(
    ctx: Context,
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
    await _ctx_info(ctx, f"Tool called: get_logcat_stream for device {device}")
    logger.info(f"Tool called: get_logcat_stream for device {device}")
    try:
        from src.mcp import tools
        result = await tools.impl_get_logcat_stream(ctx, device, package, level, lines)
        return json.dumps(result) if isinstance(result, dict) else result
    except Exception as e:
        logger.exception("Error in get_logcat_stream")
        await _ctx_warning(ctx, f"Error in get_logcat_stream: {e}")
        return f"Error: {str(e)}"


@server.tool()
async def search_logs(
    ctx: Context,
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
    await _ctx_info(ctx, f"Tool called: search_logs with query '{query}'")
    logger.info(f"Tool called: search_logs with query '{query}'")
    try:
        from src.mcp import tools
        result = await tools.impl_search_logs(ctx, query, tag_filter, level_filter, limit)
        return json.dumps(result) if isinstance(result, dict) else result
    except Exception as e:
        logger.exception("Error in search_logs")
        await _ctx_warning(ctx, f"Error in search_logs: {e}")
        return f"Error: {str(e)}"


@server.tool()
async def filter_by_level(ctx: Context, device: str, level: str) -> str:
    """Filter current logcat by severity level
    
    Args:
        device: Device serial number
        level: Log level (V/D/I/W/E/F)
    """
    await _ctx_info(ctx, f"Tool called: filter_by_level for device {device} with level {level}")
    logger.info(f"Tool called: filter_by_level for device {device} with level {level}")
    try:
        from src.mcp import tools
        result = await tools.impl_filter_by_level(ctx, device, level)
        return json.dumps(result) if isinstance(result, dict) else result
    except Exception as e:
        logger.exception("Error in filter_by_level")
        await _ctx_warning(ctx, f"Error in filter_by_level: {e}")
        return f"Error: {str(e)}"


@server.tool()
async def get_app_processes(ctx: Context, device: str, package: str) -> str:
    """Get running processes for an app
    
    Args:
        device: Device serial number
        package: Package name
    """
    await _ctx_info(ctx, f"Tool called: get_app_processes for {package} on {device}")
    logger.info(f"Tool called: get_app_processes for {package} on {device}")
    try:
        from src.mcp import tools
        result = await tools.impl_get_app_processes(ctx, device, package)
        return result if isinstance(result, str) else json.dumps(result)
    except Exception as e:
        logger.exception("Error in get_app_processes")
        await _ctx_warning(ctx, f"Error in get_app_processes: {e}")
        return json.dumps({"error": str(e)})


@server.tool()
async def get_connected_packages(ctx: Context, device: str) -> str:
    """Get all packages connected to ADB on device
    
    Args:
        device: Device serial number
    """
    await _ctx_info(ctx, f"Tool called: get_connected_packages for device {device}")
    logger.info(f"Tool called: get_connected_packages for device {device}")
    try:
        from src.mcp import tools
        result = await tools.impl_get_connected_packages(ctx, device)
        return json.dumps(result) if isinstance(result, dict) else result
    except Exception as e:
        logger.exception("Error in get_connected_packages")
        await _ctx_warning(ctx, f"Error in get_connected_packages: {e}")
        return f"Error: {str(e)}"


@server.tool()
async def parse_stacktrace(ctx: Context, stacktrace: str) -> str:
    """Parse Android stacktrace and identify issues
    
    Args:
        stacktrace: The stack trace to parse
    """
    await _ctx_info(ctx, "Tool called: parse_stacktrace")
    logger.info("Tool called: parse_stacktrace")
    try:
        from src.mcp import tools
        result = await tools.impl_parse_stacktrace(ctx, stacktrace)
        return json.dumps(result) if isinstance(result, dict) else result
    except Exception as e:
        logger.exception("Error in parse_stacktrace")
        await _ctx_warning(ctx, f"Error in parse_stacktrace: {e}")
        return f"Error: {str(e)}"


@server.tool()
async def detect_error_type(ctx: Context, logs: str) -> str:
    """Detect error types from logs
    
    Args:
        logs: Log content to analyze
    """
    await _ctx_info(ctx, "Tool called: detect_error_type")
    logger.info("Tool called: detect_error_type")
    try:
        from src.mcp import tools
        result = await tools.impl_detect_error_type(ctx, logs)
        return json.dumps(result) if isinstance(result, dict) else result
    except Exception as e:
        logger.exception("Error in detect_error_type")
        await _ctx_warning(ctx, f"Error in detect_error_type: {e}")
        return f"Error: {str(e)}"


@server.tool()
async def analyze_performance(ctx: Context, device: str, package: str, duration: int = 10) -> str:
    """Analyze app performance metrics (memory only)
    
    Args:
        device: Device serial number
        package: Package name
        duration: Duration to monitor in seconds
    """
    await _ctx_info(ctx, f"Tool called: analyze_performance for {package} on {device} for {duration}s")
    logger.info(f"Tool called: analyze_performance for {package} on {device} for {duration}s")
    try:
        from src.mcp import tools
        result = await tools.impl_analyze_performance(ctx, device, package, duration)
        return result if isinstance(result, str) else json.dumps(result)
    except Exception as e:
        logger.exception("Error in analyze_performance")
        await _ctx_warning(ctx, f"Error in analyze_performance: {e}")
        return json.dumps({"error": str(e)})


@server.tool()
async def clear_logcat(ctx: Context, device: str) -> str:
    """Clear logcat buffer on device
    
    Args:
        device: Device serial number
    """
    await _ctx_info(ctx, f"Tool called: clear_logcat for device {device}")
    logger.info(f"Tool called: clear_logcat for device {device}")
    try:
        from src.mcp import tools
        result = await tools.impl_clear_logcat(ctx, device)
        return json.dumps(result) if isinstance(result, dict) else result
    except Exception as e:
        logger.exception("Error in clear_logcat")
        await _ctx_warning(ctx, f"Error in clear_logcat: {e}")
        return f"Error: {str(e)}"


@server.tool()
async def export_logs(ctx: Context, device: str, format: str = "json", lines: int = 1000) -> str:
    """Export logcat to file
    
    Args:
        device: Device serial number
        format: Export format (json, csv, html)
        lines: Number of lines to export
    """
    await _ctx_info(ctx, f"Tool called: export_logs for device {device} in {format} format")
    logger.info(f"Tool called: export_logs for device {device} in {format} format")
    try:
        from src.mcp import tools
        result = await tools.impl_export_logs(ctx, device, format, lines)
        return json.dumps(result) if isinstance(result, dict) else result
    except Exception as e:
        logger.exception("Error in export_logs")
        await _ctx_warning(ctx, f"Error in export_logs: {e}")
        return f"Error: {str(e)}"


@server.tool()
async def get_system_info(ctx: Context, device: str) -> str:
    """Get comprehensive system information
    
    Args:
        device: Device serial number
    """
    await _ctx_info(ctx, f"Tool called: get_system_info for device {device}")
    logger.info(f"Tool called: get_system_info for device {device}")
    try:
        from src.mcp import tools
        result = await tools.impl_get_system_info(ctx, device)
        return result if isinstance(result, str) else json.dumps(result)
    except Exception as e:
        logger.exception("Error in get_system_info")
        await _ctx_warning(ctx, f"Error in get_system_info: {e}")
        return json.dumps({"error": str(e)})


@server.tool()
async def pull_fadcam_media(ctx: Context, device: str, package: str, media_type: str = "all",
                           output_dir: str = "./fadcam_media", limit: Optional[int] = None,
                           base_path: Optional[str] = None, confirm: bool = False,
                           storage_hint: Optional[str] = None) -> str:
    """Pull FadCam media files from device
    
    Coarse pull by media type (videos/screenshots/all).
    Requires base_path to avoid scanning all locations.
    For precise filters (FadShot only, camera filter, date range), use fadcam_pull_files.

    Args:
        device: Device serial number
        package: App package (auto-detects all com.fadcam.* variants):
            - com.fadcam (Free version)
            - com.fadcam.beta (Beta version)
            - com.fadcam.proplus (Paid Pro+ version)
            - com.fadcam.notes (Notes app)
            - com.fadcam.calc (Calculator app)
            - com.fadcam.weather (Weather app)
        media_type: Type of media to pull ("videos", "screenshots", or "all")
        output_dir: Local directory to save files
        limit: Maximum number of files to pull (optional)
        base_path: Specific base path to pull from (required)
        confirm: Set true to perform the pull. If false, returns a preview.
        storage_hint: Optional hint like "internal", "download", "dcim", "sd_download", "custom"
    """
    await _ctx_info(ctx, f"Tool called: pull_fadcam_media for device {device}, package {package}")
    logger.info(f"Tool called: pull_fadcam_media for device {device}, package {package}")
    try:
        from src.mcp import tools
        result = await tools.impl_pull_fadcam_media(
            ctx, device, package, media_type, output_dir, limit, base_path, confirm, storage_hint
        )
        return result if isinstance(result, str) else json.dumps(result)
    except Exception as e:
        logger.exception("Error in pull_fadcam_media")
        await _ctx_warning(ctx, f"Error in pull_fadcam_media: {e}")
        return json.dumps({"error": str(e)})


@server.tool()
async def fadcam_list_packages(ctx: Context, device: str) -> str:
    """List all FadCam packages installed on a device"""
    await _ctx_info(ctx, f"Tool called: fadcam_list_packages for device {device}")
    logger.info(f"Tool called: fadcam_list_packages for device {device}")
    try:
        from src.mcp import tools
        result = await tools.impl_fadcam_list_packages(ctx, device)
        return result if isinstance(result, str) else json.dumps(result)
    except Exception as e:
        logger.exception("Error in fadcam_list_packages")
        await _ctx_warning(ctx, f"Error in fadcam_list_packages: {e}")
        return json.dumps({"error": str(e)})


@server.tool()
async def fadcam_detect_storage(ctx: Context, device: str, package: str, include_counts: bool = False) -> str:
    """Detect FadCam storage configuration for a package

    include_counts: When true, performs file counting (slower).
    """
    await _ctx_info(ctx, f"Tool called: fadcam_detect_storage for device {device}, package {package}")
    logger.info(
        f"Tool called: fadcam_detect_storage for device {device}, package {package}, "
        f"include_counts={include_counts}"
    )
    try:
        from src.mcp import tools
        result = await tools.impl_fadcam_detect_storage(ctx, device, package, include_counts)
        return result if isinstance(result, str) else json.dumps(result)
    except Exception as e:
        logger.exception("Error in fadcam_detect_storage")
        await _ctx_warning(ctx, f"Error in fadcam_detect_storage: {e}")
        return json.dumps({"error": str(e)})


@server.tool()
async def fadcam_list_structure(ctx: Context, device: str, package: str, include_counts: bool = False) -> str:
    """List FadCam directory structure and file counts

    include_counts: When true, performs file counting (slower).
    """
    await _ctx_info(ctx, f"Tool called: fadcam_list_structure for device {device}, package {package}")
    logger.info(
        f"Tool called: fadcam_list_structure for device {device}, package {package}, "
        f"include_counts={include_counts}"
    )
    try:
        from src.mcp import tools
        result = await tools.impl_fadcam_list_structure(ctx, device, package, include_counts)
        return result if isinstance(result, str) else json.dumps(result)
    except Exception as e:
        logger.exception("Error in fadcam_list_structure")
        await _ctx_warning(ctx, f"Error in fadcam_list_structure: {e}")
        return json.dumps({"error": str(e)})


@server.tool()
async def fadcam_get_metadata(ctx: Context, device: str, package: str, file_path: str) -> str:
    """Get metadata for a specific FadCam video file"""
    await _ctx_info(ctx, f"Tool called: fadcam_get_metadata for device {device}, package {package}, path {file_path}")
    logger.info(f"Tool called: fadcam_get_metadata for device {device}, package {package}, path {file_path}")
    try:
        from src.mcp import tools
        result = await tools.impl_fadcam_get_metadata(ctx, device, package, file_path)
        return result if isinstance(result, str) else json.dumps(result)
    except Exception as e:
        logger.exception("Error in fadcam_get_metadata")
        await _ctx_warning(ctx, f"Error in fadcam_get_metadata: {e}")
        return json.dumps({"error": str(e)})


@server.tool()
async def fadcam_pull_file(ctx: Context, device: str, package: str, file_path: str,
                          output_dir: str = "./fadcam_files",
                          confirm: bool = False,
                          base_path: Optional[str] = None,
                          storage_hint: Optional[str] = None) -> str:
    """Pull a specific FadCam file by exact path or filename.

    confirm: Set true to perform the pull. If false, returns a preview.
    base_path/storage_hint: Used to resolve filename-only requests.
    """
    await _ctx_info(ctx, f"Tool called: fadcam_pull_file for device {device}, package {package}, path {file_path}")
    logger.info(f"Tool called: fadcam_pull_file for device {device}, package {package}, path {file_path}")
    try:
        from src.mcp import tools
        result = await tools.impl_fadcam_pull_file(
            ctx,
            device,
            package,
            file_path,
            output_dir,
            confirm,
            base_path,
            storage_hint
        )
        return result if isinstance(result, str) else json.dumps(result)
    except Exception as e:
        logger.exception("Error in fadcam_pull_file")
        await _ctx_warning(ctx, f"Error in fadcam_pull_file: {e}")
        return json.dumps({"error": str(e)})


@server.tool()
async def fadcam_pull_files(ctx: Context, device: str, package: str, output_dir: str = "./fadcam_files",
                           category: Optional[str] = None, camera: Optional[str] = None,
                           limit: Optional[int] = None, date_from: Optional[str] = None,
                           date_to: Optional[str] = None, base_path: Optional[str] = None,
                           confirm: bool = False, storage_hint: Optional[str] = None) -> str:
    """Pull FadCam files with advanced filtering options

    Requires base_path to ensure the pull happens only in the user-selected location.
    confirm: Set true to perform the pull. If false, returns a preview.
    storage_hint: Optional hint like "internal", "download", "dcim", "sd_download", "custom"
    """
    await _ctx_info(ctx, f"Tool called: fadcam_pull_files for device {device}, package {package}")
    logger.info(f"Tool called: fadcam_pull_files for device {device}, package {package}")
    try:
        from src.mcp import tools
        result = await tools.impl_fadcam_pull_files(
            ctx, device, package, output_dir, category, camera, limit, date_from, date_to, base_path, confirm, storage_hint
        )
        return result if isinstance(result, str) else json.dumps(result)
    except Exception as e:
        logger.exception("Error in fadcam_pull_files")
        await _ctx_warning(ctx, f"Error in fadcam_pull_files: {e}")
        return json.dumps({"error": str(e)})


@server.tool()
async def fadcam_browse_files(ctx: Context, device: str, package: str, category: Optional[str] = None,
                             camera: Optional[str] = None, limit: int = 50,
                             base_path: Optional[str] = None, storage_hint: Optional[str] = None) -> str:
    """Browse FadCam files without downloading - returns metadata only

    base_path is required to avoid scanning all locations.
    storage_hint can be used to resolve a base_path (e.g., "internal", "download", "dcim", "sd_download", "custom").
    """
    await _ctx_info(ctx, f"Tool called: fadcam_browse_files for device {device}, package {package}")
    logger.info(f"Tool called: fadcam_browse_files for device {device}, package {package}")
    try:
        from src.mcp import tools
        result = await tools.impl_fadcam_browse_files(ctx, device, package, category, camera, limit, base_path, storage_hint)
        return result if isinstance(result, str) else json.dumps(result)
    except Exception as e:
        logger.exception("Error in fadcam_browse_files")
        await _ctx_warning(ctx, f"Error in fadcam_browse_files: {e}")
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


@server.prompt()
async def fadcat_about() -> str:
    """About FadCat

    Explain what FadCat is and show example prompts for FadCam media workflows.
    """
    logger.info("Prompt accessed: fadcat-about")
    try:
        from src.mcp import prompts
        return await prompts.get_prompt("fadcat-about")
    except Exception as e:
        logger.exception("Error getting FadCat about prompt")
        return f"Error: {str(e)}"


@server.prompt()
async def fadcam_media_helper() -> str:
    """FadCam Media Helper

    Guide browse-first and confirm-before-pull workflows.
    """
    logger.info("Prompt accessed: fadcam-media-helper")
    try:
        from src.mcp import prompts
        return await prompts.get_prompt("fadcam-media-helper")
    except Exception as e:
        logger.exception("Error getting FadCam media helper prompt")
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
