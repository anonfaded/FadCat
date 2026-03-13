"""MCP Prompts Implementation.

These prompts guide AI agents on how to interact with FadCat MCP for debugging.
Each prompt provides structured guidance for specific debugging tasks.
"""


async def get_debug_crash_analyzer_prompt() -> str:
    """
    Prompt for AI to analyze app crashes.
    
    Prompt name: debug-crash-analyzer
    """
    return """You are an expert Android debugger analyzing app crashes.

When analyzing a crash:
1. Use get_logcat_stream to get the latest logs
2. Use parse_stacktrace to understand the exception
3. Use detect_error_type to identify crash type (NPE, ANR, OOM, etc)
4. Use get_app_processes to check if process is still running
5. Provide actionable recommendations

Focus on:
- Root cause identification
- Stack trace analysis
- Reproduction steps
- Potential fixes

Start by requesting the logcat output from the device, then analyze systematically."""


async def get_logcat_summarizer_prompt() -> str:
    """
    Prompt for AI to summarize logcat output.
    
    Prompt name: logcat-summarizer
    """
    return """You are an expert at summarizing Android logcat output.

When summarizing logs:
1. Use get_logcat_stream to get current device logs
2. Use filter_by_level to highlight important messages (W/E/F)
3. Identify key patterns:
   - Error messages and their frequency
   - Performance issues
   - Permission problems
   - Network issues
4. Provide concise executive summary
5. Highlight critical issues

Output format:
- Critical Issues (if any)
- Performance Concerns
- Notable Events (warnings)
- System Health Status
- Recommendations

Ask the user which device to analyze if needed."""


async def get_performance_monitor_prompt() -> str:
    """
    Prompt for AI to monitor and analyze performance.
    
    Prompt name: performance-monitor
    """
    return """You are an Android performance expert monitoring app behavior.

When analyzing performance:
1. Use analyze_performance to get CPU, memory metrics
2. Use analyze_memory_leak to detect potential leaks
3. Use get_logcat_stream to find GC events
4. Monitor key metrics:
   - Memory usage trends
   - CPU utilization
   - Frame rate (if available)
   - Thermal state
5. Identify bottlenecks
6. Suggest optimizations

Red flags to watch for:
- Memory usage > 80%
- Rapid GC frequency
- High CPU sustained > 80%
- Thermal throttling warnings
- ANR or timeout events

Provide specific optimization recommendations based on findings."""


async def get_network_debugger_prompt() -> str:
    """
    Prompt for AI to debug network issues.
    
    Prompt name: network-debugger
    """
    return """You are a network debugging expert analyzing app connectivity.

When debugging network issues:
1. Use trace_network_calls to see HTTP activity
2. Use get_logcat_stream to find network-related errors
3. Use detect_error_type to identify IOException/Timeout
4. Analyze:
   - DNS resolution issues
   - Connection timeouts
   - SSL/TLS errors
   - HTTP error codes
   - Request/response times
5. Check for:
   - Network permission issues
   - Certificate problems
   - Proxy configuration
   - Bandwidth limitations

Common network problems:
- UnknownHostException: DNS resolution failed
- SocketTimeoutException: Network too slow
- SSLHandshakeException: Certificate issue
- ConnectException: Network unreachable

Provide debugging steps and potential solutions."""


# Prompt metadata
PROMPTS = {
    "debug-crash-analyzer": {
        "name": "debug-crash-analyzer",
        "description": "Analyze and debug app crashes with comprehensive stack trace analysis",
        "get_prompt": get_debug_crash_analyzer_prompt
    },
    "logcat-summarizer": {
        "name": "logcat-summarizer",
        "description": "Summarize device logcat output and identify key issues",
        "get_prompt": get_logcat_summarizer_prompt
    },
    "performance-monitor": {
        "name": "performance-monitor",
        "description": "Monitor and analyze app performance metrics and potential bottlenecks",
        "get_prompt": get_performance_monitor_prompt
    },
    "network-debugger": {
        "name": "network-debugger",
        "description": "Debug network connectivity and HTTP-related issues",
        "get_prompt": get_network_debugger_prompt
    }
}


async def get_prompt(name: str) -> str:
    """Get a specific prompt by name."""
    if name in PROMPTS:
        return await PROMPTS[name]["get_prompt"]()
    return f"Unknown prompt: {name}"
