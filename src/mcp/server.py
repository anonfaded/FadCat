"""FadCat MCP Server - Model Context Protocol implementation for Android debugging."""

import sys
import logging
from typing import Any, Optional, List
from mcp.server import Server, InitializationOptions
from mcp.types import (
    Tool,
    TextContent,
    Resource,
    ResourceTemplate,
    Prompt,
    PromptArgument,
)
import json

# Setup logging to stderr (MCP requirement - stdout is reserved for protocol)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

from src.version import __version__, __author__, __app_name__

# Create MCP server
SERVER = Server("fadcat")

# Module-level state
_server_start_time = None
_active_connections = 0


@SERVER.list_tools()
async def list_tools() -> List[Tool]:
    """List all available MCP tools."""
    return [
        # Device and Connection Tools
        Tool(
            name="get_devices",
            description="Get list of connected Android devices",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        
        # Logcat Tools
        Tool(
            name="get_logcat_stream",
            description="Get logcat stream from a device with optional filters",
            inputSchema={
                "type": "object",
                "properties": {
                    "device": {"type": "string", "description": "Device serial"},
                    "package": {"type": "string", "description": "Filter by package (optional)"},
                    "level": {"type": "string", "description": "Minimum log level (V/D/I/W/E/F)"},
                    "lines": {"type": "integer", "description": "Number of lines to retrieve"}
                },
                "required": ["device"]
            }
        ),
        
        Tool(
            name="search_logs",
            description="Search in logcat history",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "tag_filter": {"type": "string", "description": "Optional tag filter"},
                    "level_filter": {"type": "string", "description": "Optional level filter"},
                    "limit": {"type": "integer", "description": "Max results"}
                },
                "required": ["query"]
            }
        ),
        
        Tool(
            name="filter_by_level",
            description="Filter current logcat by severity level",
            inputSchema={
                "type": "object",
                "properties": {
                    "device": {"type": "string", "description": "Device serial"},
                    "level": {"type": "string", "description": "Log level (V/D/I/W/E/F)"}
                },
                "required": ["device", "level"]
            }
        ),
        
        # Process and Package Tools
        Tool(
            name="get_app_processes",
            description="Get running processes for an app",
            inputSchema={
                "type": "object",
                "properties": {
                    "device": {"type": "string", "description": "Device serial"},
                    "package": {"type": "string", "description": "Package name"}
                },
                "required": ["device", "package"]
            }
        ),
        
        Tool(
            name="get_connected_packages",
            description="Get list of installed packages on device",
            inputSchema={
                "type": "object",
                "properties": {
                    "device": {"type": "string", "description": "Device serial"},
                    "running_only": {"type": "boolean", "description": "Only running apps"}
                },
                "required": ["device"]
            }
        ),
        
        # Error Analysis Tools
        Tool(
            name="parse_stacktrace",
            description="Parse and analyze Java exception stacktrace",
            inputSchema={
                "type": "object",
                "properties": {
                    "trace": {"type": "string", "description": "Raw stacktrace text"}
                },
                "required": ["trace"]
            }
        ),
        
        Tool(
            name="detect_error_type",
            description="Detect error type from logcat (ANR/CRASH/OOM/etc)",
            inputSchema={
                "type": "object",
                "properties": {
                    "logcat": {"type": "string", "description": "Logcat content"},
                    "device": {"type": "string", "description": "Device serial (optional)"}
                },
                "required": ["logcat"]
            }
        ),
        
        # Performance and Monitoring Tools
        Tool(
            name="analyze_performance",
            description="Analyze performance metrics (CPU, memory, FPS)",
            inputSchema={
                "type": "object",
                "properties": {
                    "device": {"type": "string", "description": "Device serial"},
                    "duration_seconds": {"type": "integer", "description": "Duration to monitor"}
                },
                "required": ["device"]
            }
        ),
        
        Tool(
            name="trace_network_calls",
            description="Extract and trace network calls from logs",
            inputSchema={
                "type": "object",
                "properties": {
                    "device": {"type": "string", "description": "Device serial"},
                    "package": {"type": "string", "description": "Package to trace"}
                },
                "required": ["device", "package"]
            }
        ),
        
        Tool(
            name="analyze_memory_leak",
            description="Detect potential memory leaks",
            inputSchema={
                "type": "object",
                "properties": {
                    "device": {"type": "string", "description": "Device serial"},
                    "package": {"type": "string", "description": "Package to analyze"}
                },
                "required": ["device", "package"]
            }
        ),
        
        # Device Management Tools
        Tool(
            name="clear_logcat",
            description="Clear logcat buffer on device",
            inputSchema={
                "type": "object",
                "properties": {
                    "device": {"type": "string", "description": "Device serial"}
                },
                "required": ["device"]
            }
        ),
        
        Tool(
            name="export_logs",
            description="Export logcat to file (JSON, CSV, HTML)",
            inputSchema={
                "type": "object",
                "properties": {
                    "device": {"type": "string", "description": "Device serial"},
                    "format": {"type": "string", "enum": ["json", "csv", "html"]},
                    "lines": {"type": "integer", "description": "Number of lines"}
                },
                "required": ["device", "format"]
            }
        ),
    ]


@SERVER.call_tool()
async def call_tool(name: str, arguments: dict) -> List[TextContent]:
    """Execute a tool."""
    logger.info(f"Tool called: {name} with args: {arguments}")
    
    try:
        from src.mcp import tools
        
        if name == "get_devices":
            result = await tools.impl_get_devices()
        elif name == "get_logcat_stream":
            result = await tools.impl_get_logcat_stream(
                arguments.get('device'),
                arguments.get('package'),
                arguments.get('level', 'I'),
                arguments.get('lines', 100)
            )
        elif name == "search_logs":
            result = await tools.impl_search_logs(
                arguments.get('query'),
                arguments.get('tag_filter'),
                arguments.get('level_filter'),
                arguments.get('limit', 50)
            )
        elif name == "filter_by_level":
            result = await tools.impl_filter_by_level(
                arguments.get('device'),
                arguments.get('level')
            )
        elif name == "get_app_processes":
            result = await tools.impl_get_app_processes(
                arguments.get('device'),
                arguments.get('package')
            )
        elif name == "get_connected_packages":
            result = await tools.impl_get_connected_packages(arguments.get('device'))
        elif name == "parse_stacktrace":
            result = await tools.impl_parse_stacktrace(arguments.get('trace', ''))
        elif name == "detect_error_type":
            result = await tools.impl_detect_error_type(arguments.get('logcat', ''))
        elif name == "analyze_performance":
            result = await tools.impl_analyze_performance(arguments.get('device'))
        elif name == "trace_network_calls":
            result = await tools.impl_trace_network_calls(arguments.get('device'))
        elif name == "analyze_memory_leak":
            result = await tools.impl_analyze_memory_leak(arguments.get('device'))
        elif name == "clear_logcat":
            result = await tools.impl_clear_logcat(arguments.get('device'))
        elif name == "export_logs":
            result = await tools.impl_export_logs(
                arguments.get('device'),
                arguments.get('format', 'json'),
                arguments.get('lines', 1000)
            )
        else:
            result = json.dumps({"error": f"Unknown tool: {name}"})
        
        return [TextContent(type="text", text=result)]
    except Exception as e:
        logger.exception(f"Error calling tool {name}")
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

# ============================================================================
# Tool Implementations - Moved to src/mcp/tools.py
# All 13 tools are now fully implemented with cross-platform support
# ============================================================================


@SERVER.list_resources()
async def list_resources() -> List[ResourceTemplate]:
    """List available resources."""
    return [
        ResourceTemplate(
            uri_template="logcat://device/{device_serial}",
            name="Device Logcat",
            description="Current logcat stream from a device"
        ),
        ResourceTemplate(
            uri_template="android://devices",
            name="Connected Devices",
            description="List of connected Android devices"
        ),
        ResourceTemplate(
            uri_template="android://packages/{device_serial}",
            name="Device Packages",
            description="Installed packages on a device"
        ),
    ]


@SERVER.read_resource()
async def read_resource(uri: str) -> str:
    """Read a resource by URI."""
    logger.info(f"Reading resource: {uri}")
    
    try:
        from src.mcp import resources
        
        if uri.startswith("logcat://device/"):
            device_serial = uri.replace("logcat://device/", "")
            return await resources.read_logcat_device_resource(device_serial)
        elif uri == "android://devices":
            return await resources.read_android_devices_resource()
        elif uri.startswith("android://packages/"):
            device_serial = uri.replace("android://packages/", "")
            return await resources.read_android_packages_resource(device_serial)
        elif uri.startswith("android://processes/"):
            device_serial = uri.replace("android://processes/", "")
            return await resources.read_android_processes_resource(device_serial)
        else:
            return json.dumps({"error": f"Unknown resource: {uri}"})
    except Exception as e:
        logger.exception(f"Error reading resource {uri}")
        return json.dumps({"error": str(e)})


@SERVER.list_prompts()
async def list_prompts() -> List[Prompt]:
    """List available prompts."""
    return [
        Prompt(
            name="debug-crash-analyzer",
            description="Analyze Android crash logs and provide root cause analysis",
            arguments=[]
        ),
        Prompt(
            name="logcat-summarizer",
            description="Summarize what's happening in the app from logcat",
            arguments=[]
        ),
        Prompt(
            name="performance-monitor",
            description="Find performance bottlenecks and optimization opportunities",
            arguments=[]
        ),
        Prompt(
            name="network-debugger",
            description="Trace and debug network calls and connectivity issues",
            arguments=[]
        ),
    ]


@SERVER.get_prompt()
async def get_prompt(name: str, arguments: dict) -> str:
    """Get prompt content for a specific debugging task."""
    logger.info(f"Getting prompt: {name}")
    
    try:
        from src.mcp import prompts
        return await prompts.get_prompt(name)
    except Exception as e:
        logger.exception(f"Error getting prompt {name}")
        return f"Error: {str(e)}"


async def main():
    """Run MCP server on stdio."""
    logger.info("Starting FadCat MCP Server")
    from mcp.server.stdio import stdio_server
    
    # Create initialization options for MCP server using version info
    init_options = InitializationOptions(
        server_name=__app_name__,
        server_version=__version__,
        capabilities={}
    )
    
    # Run server on stdio transport
    async with stdio_server() as (read_stream, write_stream):
        logger.info("FadCat MCP Server running on stdio")
        await SERVER.run(read_stream, write_stream, init_options)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
