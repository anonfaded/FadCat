"""FadCat MCP Server - Model Context Protocol implementation for Android debugging."""

import sys
import logging
import os
import time
from typing import Any, Optional, List
from pathlib import Path
from fastmcp import FastMCP, Context
from fastmcp.server import providers as mcp_providers
import json

# Setup logging to stderr (MCP requirement - stdout is reserved for protocol)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

from src.version import __version__, __author__, __app_name__

# Suppress FastMCP banner on stdio to avoid MCP parse errors
os.environ.setdefault("FASTMCP_SHOW_SERVER_BANNER", "false")

# Create MCP server with FastMCP
server = FastMCP(__app_name__, __version__)

# Skills Provider (discoverable skills)
try:
    skills_root = Path.home() / ".codex" / "skills"
    if skills_root.exists():
        server.add_provider(mcp_providers.SkillsProvider(roots=[skills_root], supporting_files="template"))
except Exception:
    pass

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

@server.tool(annotations={
    "title": "List Devices",
    "readOnlyHint": True,
    "idempotentHint": True,
    "openWorldHint": True
})
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
                    return json.dumps(cached, ensure_ascii=False)
                return json.dumps(_last_devices_cache, ensure_ascii=False)

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
        return json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else result
    except Exception as e:
        logger.exception("Error in get_devices")
        await _ctx_warning(ctx, f"Error in get_devices: {e}")
        return f"Error: {str(e)}"


@server.tool(annotations={
    "title": "Get Logcat",
    "readOnlyHint": True,
    "idempotentHint": False,
    "openWorldHint": True
})
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
        return json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else result
    except Exception as e:
        logger.exception("Error in get_logcat_stream")
        await _ctx_warning(ctx, f"Error in get_logcat_stream: {e}")
        return f"Error: {str(e)}"


@server.tool(annotations={
    "title": "Search Logcat",
    "readOnlyHint": True,
    "idempotentHint": False,
    "openWorldHint": True
})
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
        return json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else result
    except Exception as e:
        logger.exception("Error in search_logs")
        await _ctx_warning(ctx, f"Error in search_logs: {e}")
        return f"Error: {str(e)}"


@server.tool(annotations={
    "title": "Filter Logcat by Level",
    "readOnlyHint": True,
    "idempotentHint": False,
    "openWorldHint": True
})
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
        return json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else result
    except Exception as e:
        logger.exception("Error in filter_by_level")
        await _ctx_warning(ctx, f"Error in filter_by_level: {e}")
        return f"Error: {str(e)}"


@server.tool(annotations={
    "title": "Get App Processes",
    "readOnlyHint": True,
    "idempotentHint": False,
    "openWorldHint": True
})
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
        return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.exception("Error in get_app_processes")
        await _ctx_warning(ctx, f"Error in get_app_processes: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@server.tool(annotations={
    "title": "Parse Stacktrace",
    "readOnlyHint": True,
    "idempotentHint": True,
    "openWorldHint": False
})
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
        return json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else result
    except Exception as e:
        logger.exception("Error in parse_stacktrace")
        await _ctx_warning(ctx, f"Error in parse_stacktrace: {e}")
        return f"Error: {str(e)}"


@server.tool(annotations={
    "title": "Detect Error Type",
    "readOnlyHint": True,
    "idempotentHint": True,
    "openWorldHint": False
})
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
        return json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else result
    except Exception as e:
        logger.exception("Error in detect_error_type")
        await _ctx_warning(ctx, f"Error in detect_error_type: {e}")
        return f"Error: {str(e)}"


@server.tool(annotations={
    "title": "Analyze Performance (Memory)",
    "readOnlyHint": True,
    "idempotentHint": False,
    "openWorldHint": True
})
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
        return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.exception("Error in analyze_performance")
        await _ctx_warning(ctx, f"Error in analyze_performance: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@server.tool(annotations={
    "title": "Clear Logcat",
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": False,
    "openWorldHint": True
})
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
        return json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else result
    except Exception as e:
        logger.exception("Error in clear_logcat")
        await _ctx_warning(ctx, f"Error in clear_logcat: {e}")
        return f"Error: {str(e)}"


@server.tool(annotations={
    "title": "Export Logcat",
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": False,
    "openWorldHint": True
})
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
        return json.dumps(result, ensure_ascii=False) if isinstance(result, dict) else result
    except Exception as e:
        logger.exception("Error in export_logs")
        await _ctx_warning(ctx, f"Error in export_logs: {e}")
        return f"Error: {str(e)}"


@server.tool(annotations={
    "title": "Get System Info",
    "readOnlyHint": True,
    "idempotentHint": False,
    "openWorldHint": True
})
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
        return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.exception("Error in get_system_info")
        await _ctx_warning(ctx, f"Error in get_system_info: {e}")
        return json.dumps({"error": str(e)})


@server.tool(annotations={
    "title": "Get FadCam File Metadata",
    "readOnlyHint": True,
    "idempotentHint": False,
    "openWorldHint": True
})
async def fadcam_get_metadata(ctx: Context, device: str, package: str, file_path: str) -> str:
    """Get metadata for a specific FadCam video file"""
    await _ctx_info(ctx, f"Tool called: fadcam_get_metadata for device {device}, package {package}, path {file_path}")
    logger.info(f"Tool called: fadcam_get_metadata for device {device}, package {package}, path {file_path}")
    try:
        from src.mcp import tools
        result = await tools.impl_fadcam_get_metadata(ctx, device, package, file_path)
        return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.exception("Error in fadcam_get_metadata")
        await _ctx_warning(ctx, f"Error in fadcam_get_metadata: {e}")
        return json.dumps({"error": str(e)})


@server.tool(annotations={
    "title": "Pull FadCam File",
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": False,
    "openWorldHint": True
})
async def fadcam_pull_file(ctx: Context, device: str, package: str, file_path: str,
                          output_dir: str = "./fadcam_files",
                          confirm: bool = False,
                          base_path: Optional[str] = None,
                          storage_hint: Optional[str] = None) -> str:
    """Pull a specific FadCam file by exact path or filename.

    confirm: Set true to perform the pull. If false, returns a preview.
    base_path: Required to resolve filename-only requests.
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
        return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.exception("Error in fadcam_pull_file")
        await _ctx_warning(ctx, f"Error in fadcam_pull_file: {e}")
        return json.dumps({"error": str(e)})


@server.tool(annotations={
    "title": "Browse FadCam Camera",
    "readOnlyHint": True,
    "idempotentHint": False,
    "openWorldHint": True
})
async def fadcam_browse_camera(ctx: Context, device: str, package: str,
                               camera: Optional[str] = None, limit: int = 200,
                               base_path: Optional[str] = None,
                               storage_hint: Optional[str] = None,
                               full_scan: bool = True) -> str:
    """Browse camera recordings (metadata only)."""
    await _ctx_info(ctx, f"Tool called: fadcam_browse_camera for device {device}, package {package}")
    logger.info(f"Tool called: fadcam_browse_camera for device {device}, package {package}")
    try:
        from src.mcp import tools
        result = await tools.impl_fadcam_browse_camera(
            ctx, device, package, camera, limit, base_path, storage_hint, full_scan
        )
        return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.exception("Error in fadcam_browse_camera")
        await _ctx_warning(ctx, f"Error in fadcam_browse_camera: {e}")
        return json.dumps({"error": str(e)})


@server.tool(annotations={
    "title": "Browse FadCam FadShot",
    "readOnlyHint": True,
    "idempotentHint": False,
    "openWorldHint": True
})
async def fadcam_browse_fadshot(ctx: Context, device: str, package: str,
                                camera: Optional[str] = None, limit: int = 200,
                                base_path: Optional[str] = None,
                                storage_hint: Optional[str] = None,
                                full_scan: bool = True) -> str:
    """Browse FadShot screenshots (metadata only)."""
    await _ctx_info(ctx, f"Tool called: fadcam_browse_fadshot for device {device}, package {package}")
    logger.info(f"Tool called: fadcam_browse_fadshot for device {device}, package {package}")
    try:
        from src.mcp import tools
        result = await tools.impl_fadcam_browse_fadshot(
            ctx, device, package, camera, limit, base_path, storage_hint, full_scan
        )
        return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.exception("Error in fadcam_browse_fadshot")
        await _ctx_warning(ctx, f"Error in fadcam_browse_fadshot: {e}")
        return json.dumps({"error": str(e)})


@server.tool(annotations={
    "title": "Browse FadCam Dual",
    "readOnlyHint": True,
    "idempotentHint": False,
    "openWorldHint": True
})
async def fadcam_browse_dual(ctx: Context, device: str, package: str,
                             limit: int = 200,
                             base_path: Optional[str] = None,
                             storage_hint: Optional[str] = None,
                             full_scan: bool = True) -> str:
    """Browse legacy Dual recordings (metadata only)."""
    await _ctx_info(ctx, f"Tool called: fadcam_browse_dual for device {device}, package {package}")
    logger.info(f"Tool called: fadcam_browse_dual for device {device}, package {package}")
    try:
        from src.mcp import tools
        result = await tools.impl_fadcam_browse_dual(
            ctx, device, package, limit, base_path, storage_hint, full_scan
        )
        return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.exception("Error in fadcam_browse_dual")
        await _ctx_warning(ctx, f"Error in fadcam_browse_dual: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@server.tool(annotations={
    "title": "Browse FadCam Screen",
    "readOnlyHint": True,
    "idempotentHint": False,
    "openWorldHint": True
})
async def fadcam_browse_screen(ctx: Context, device: str, package: str,
                               limit: int = 200,
                               base_path: Optional[str] = None,
                               storage_hint: Optional[str] = None,
                               full_scan: bool = True) -> str:
    """Browse screen recordings (metadata only)."""
    await _ctx_info(ctx, f"Tool called: fadcam_browse_screen for device {device}, package {package}")
    logger.info(f"Tool called: fadcam_browse_screen for device {device}, package {package}")
    try:
        from src.mcp import tools
        result = await tools.impl_fadcam_browse_screen(
            ctx, device, package, limit, base_path, storage_hint, full_scan
        )
        return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.exception("Error in fadcam_browse_screen")
        await _ctx_warning(ctx, f"Error in fadcam_browse_screen: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@server.tool(annotations={
    "title": "Browse FadCam Stream",
    "readOnlyHint": True,
    "idempotentHint": False,
    "openWorldHint": True
})
async def fadcam_browse_stream(ctx: Context, device: str, package: str,
                               limit: int = 200,
                               base_path: Optional[str] = None,
                               storage_hint: Optional[str] = None,
                               full_scan: bool = True) -> str:
    """Browse stream recordings (metadata only)."""
    await _ctx_info(ctx, f"Tool called: fadcam_browse_stream for device {device}, package {package}")
    logger.info(f"Tool called: fadcam_browse_stream for device {device}, package {package}")
    try:
        from src.mcp import tools
        result = await tools.impl_fadcam_browse_stream(
            ctx, device, package, limit, base_path, storage_hint, full_scan
        )
        return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.exception("Error in fadcam_browse_stream")
        await _ctx_warning(ctx, f"Error in fadcam_browse_stream: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@server.tool(annotations={
    "title": "Browse FadCam Faditor",
    "readOnlyHint": True,
    "idempotentHint": False,
    "openWorldHint": True
})
async def fadcam_browse_faditor(ctx: Context, device: str, package: str,
                                limit: int = 200,
                                base_path: Optional[str] = None,
                                storage_hint: Optional[str] = None,
                                full_scan: bool = True) -> str:
    """Browse Faditor output videos (metadata only)."""
    await _ctx_info(ctx, f"Tool called: fadcam_browse_faditor for device {device}, package {package}")
    logger.info(f"Tool called: fadcam_browse_faditor for device {device}, package {package}")
    try:
        from src.mcp import tools
        result = await tools.impl_fadcam_browse_faditor(
            ctx, device, package, limit, base_path, storage_hint, full_scan
        )
        return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.exception("Error in fadcam_browse_faditor")
        await _ctx_warning(ctx, f"Error in fadcam_browse_faditor: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@server.tool(annotations={
    "title": "Browse FadCam Root",
    "readOnlyHint": True,
    "idempotentHint": False,
    "openWorldHint": True
})
async def fadcam_browse_root(ctx: Context, device: str, package: str,
                             limit: int = 200,
                             base_path: Optional[str] = None,
                             storage_hint: Optional[str] = None,
                             full_scan: bool = True) -> str:
    """Browse root-level media files under the FadCam base path (metadata only)."""
    await _ctx_info(ctx, f"Tool called: fadcam_browse_root for device {device}, package {package}")
    logger.info(f"Tool called: fadcam_browse_root for device {device}, package {package}")
    try:
        from src.mcp import tools
        result = await tools.impl_fadcam_browse_root(
            ctx, device, package, limit, base_path, storage_hint, full_scan
        )
        return result if isinstance(result, str) else json.dumps(result)
    except Exception as e:
        logger.exception("Error in fadcam_browse_root")
        await _ctx_warning(ctx, f"Error in fadcam_browse_root: {e}")
        return json.dumps({"error": str(e)})


@server.tool(annotations={
    "title": "Browse FadCam Forensics",
    "readOnlyHint": True,
    "idempotentHint": False,
    "openWorldHint": True
})
async def fadcam_browse_forensics(ctx: Context, device: str, package: str,
                                  limit: int = 0, full_scan: bool = True) -> str:
    """Browse forensic snapshots only (metadata).

    Internal app storage only: /storage/emulated/0/Android/data/<pkg>/files/FadCam/Forensics/Snapshots
    limit=0 returns counts only (no file listing).
    """
    await _ctx_info(ctx, f"Tool called: fadcam_browse_forensics for device {device}, package {package}")
    logger.info(f"Tool called: fadcam_browse_forensics for device {device}, package {package}")
    try:
        from src.mcp import tools
        result = await tools.impl_fadcam_browse_forensics(ctx, device, package, limit, full_scan)
        return result if isinstance(result, str) else json.dumps(result)
    except Exception as e:
        logger.exception("Error in fadcam_browse_forensics")
        await _ctx_warning(ctx, f"Error in fadcam_browse_forensics: {e}")
        return json.dumps({"error": str(e)})


@server.tool(annotations={
    "title": "Pull FadCam Forensics",
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": False,
    "openWorldHint": True
})
async def fadcam_pull_forensics(ctx: Context, device: str, package: str,
                                output_dir: str = "./fadcam_files",
                                limit: Optional[int] = None,
                                confirm: bool = False) -> str:
    """Pull forensic snapshots only."""
    await _ctx_info(ctx, f"Tool called: fadcam_pull_forensics for device {device}, package {package}")
    logger.info(f"Tool called: fadcam_pull_forensics for device {device}, package {package}")
    try:
        from src.mcp import tools
        result = await tools.impl_fadcam_pull_forensics(ctx, device, package, output_dir, limit, confirm)
        return result if isinstance(result, str) else json.dumps(result)
    except Exception as e:
        logger.exception("Error in fadcam_pull_forensics")
        await _ctx_warning(ctx, f"Error in fadcam_pull_forensics: {e}")
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
    Focus on memory usage (PSS) and GC behavior.
    """
    logger.info("Prompt accessed: performance-monitor")
    try:
        from src.mcp import prompts
        return await prompts.get_prompt("performance-monitor")
    except Exception as e:
        logger.exception("Error getting performance monitor prompt")
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
    logger.info(f"Starting FadCat MCP Server ({__app_name__} v{__version__})")
    try:
        server.run(show_banner=False)
    except KeyboardInterrupt:
        logger.info("MCP Server stopped by user")
    except Exception as e:
        logger.exception(f"MCP Server fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
