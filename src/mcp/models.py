"""MCP Data Models - Pydantic models for FadCat MCP features."""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class LogLevel(str, Enum):
    """Android log levels."""
    VERBOSE = "V"
    DEBUG = "D"
    INFO = "I"
    WARNING = "W"
    ERROR = "E"
    FATAL = "F"


class LogLine(BaseModel):
    """A single logcat log line."""
    timestamp: str
    level: LogLevel
    tag: str
    pid: Optional[int] = None
    tid: Optional[int] = None
    message: str
    raw: Optional[str] = None
    
    class Config:
        use_enum_values = True


class DeviceInfo(BaseModel):
    """Information about a connected Android device."""
    serial: str
    name: str
    status: str  # "device", "offline", "unauthorized"
    model: Optional[str] = None
    product: Optional[str] = None
    device: Optional[str] = None
    usb_port: Optional[str] = None
    is_emulator: bool = False


class ProcessInfo(BaseModel):
    """Information about a process on a device."""
    pid: int
    uid: int
    name: str
    package: str


class PackageInfo(BaseModel):
    """Information about an installed package."""
    package_name: str
    version_name: Optional[str] = None
    version_code: Optional[int] = None
    is_system: bool = False
    is_running: bool = False


class StackTraceInfo(BaseModel):
    """Parsed Java exception/stacktrace information."""
    exception_type: str
    message: str
    file: Optional[str] = None
    line: Optional[int] = None
    method: Optional[str] = None
    stack_frames: List[Dict[str, str]] = Field(default_factory=list)
    cause_type: Optional[str] = None
    cause_message: Optional[str] = None


class ErrorAnalysis(BaseModel):
    """Detailed error analysis from logcat."""
    error_type: str  # ANR, CRASH, OOM, TIMEOUT, EXCEPTION, etc.
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    root_cause: str
    affected_component: Optional[str] = None
    affected_package: Optional[str] = None
    timestamp: Optional[str] = None
    suggested_fix: Optional[str] = None
    stack_trace: Optional[StackTraceInfo] = None
    frequency: int = 1  # How many times this error appeared


class PerformanceMetrics(BaseModel):
    """Performance metrics from a device."""
    timestamp: str
    cpu_usage: float  # Percentage
    memory_used: int  # MB
    memory_total: int  # MB
    fps: Optional[float] = None
    jank_count: int = 0


class PerformanceReport(BaseModel):
    """Complete performance analysis report."""
    device: str
    duration_seconds: int
    metrics: List[PerformanceMetrics] = Field(default_factory=list)
    avg_cpu: float
    peak_memory: int
    min_fps: Optional[float] = None
    avg_fps: Optional[float] = None
    jank_frames: int = 0
    analysis: Optional[str] = None


class NetworkCall(BaseModel):
    """A single network call extracted from logs."""
    timestamp: str
    method: str  # GET, POST, etc.
    url: str
    status_code: Optional[int] = None
    duration_ms: Optional[int] = None
    size_bytes: Optional[int] = None
    error: Optional[str] = None


class NetworkTrace(BaseModel):
    """Network activity trace for a package."""
    package: str
    device: str
    calls: List[NetworkCall] = Field(default_factory=list)
    total_bytes: int = 0
    failed_count: int = 0
    duration_seconds: int = 0


class MemoryAllocation(BaseModel):
    """Memory allocation event."""
    timestamp: str
    size_bytes: int
    allocation_type: str  # ALLOC_FREED, ALLOC_CLASS, etc.
    class_name: Optional[str] = None


class MemoryAnalysis(BaseModel):
    """Memory leak detection and analysis."""
    device: str
    package: str
    suspected_leak: bool
    leak_size_mb: Optional[float] = None
    leak_type: Optional[str] = None  # ServiceConnection, Listener, etc.
    affected_class: Optional[str] = None
    allocations: List[MemoryAllocation] = Field(default_factory=list)
    recommendation: Optional[str] = None


class MCPServerStatus(BaseModel):
    """Status of the MCP server."""
    running: bool
    active_connections: int
    tools_available: int
    resources_available: int
    prompts_available: int
    uptime_seconds: Optional[int] = None
    version: str = "1.0.0"
    last_activity: Optional[str] = None
