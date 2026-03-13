"""MCP Configuration - Auto-detection and setup."""

import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any


def get_fadcat_install_path() -> Optional[Path]:
    """
    Auto-detect FadCat installation path.
    
    Handles:
    - Development mode (src directory)
    - Bundled app (macOS .app bundle)
    - Installed script location
    """
    # Check if running from source
    src_path = Path(__file__).parent.parent.parent
    if (src_path / "FadCat.py").exists():
        return src_path
    
    # Check if running from bundled app (macOS)
    if hasattr(sys, 'frozen'):
        app_path = Path(sys.executable).parent.parent.parent
        if (app_path / "Resources" / "FadCat.py").exists():
            return app_path / "Resources"
    
    # Check common installation paths
    for base_path in [
        Path.home() / "Applications" / "FadCat.app" / "Contents" / "Resources",
        Path("/Applications/FadCat.app/Contents/Resources"),
        Path.home() / ".local" / "share" / "FadCat",
    ]:
        if (base_path / "FadCat.py").exists():
            return base_path
    
    return None


def generate_mcp_config(use_fadcat_command: bool = True) -> Dict[str, Any]:
    """
    Generate default MCP configuration for IDEs.
    
    Returns config that can be merged into IDE settings.
    Uses 'fadcat' command by default (available after installation).
    Falls back to python -m if fadcat command not in PATH.
    """
    if use_fadcat_command:
        return {
            "mcpServers": {
                "fadcat": {
                    "command": "fadcat",
                    "args": ["--mcp"],
                    "env": {"PYTHONUNBUFFERED": "1"}
                }
            }
        }
    else:
        # Fallback: use python -m src.mcp
        fadcat_path = get_fadcat_install_path()
        if not fadcat_path:
            raise RuntimeError(
                "Could not find FadCat installation. "
                "Please ensure FadCat is properly installed."
            )
        return {
            "mcpServers": {
                "fadcat": {
                    "command": "python",
                    "args": ["-m", "src.mcp"],
                    "cwd": str(fadcat_path),
                    "env": {"PYTHONUNBUFFERED": "1"}
                }
            }
        }


def get_ide_config_paths() -> Dict[str, Path]:
    """
    Get settings file paths for all supported IDEs.
    
    Returns dict mapping IDE name to settings/config path.
    
    Supported IDEs:
    - vscode, cursor, windsurf, claude-code: mcpServers in settings.json
    - cline: mcp_servers.json
    - antigravity, gemini-cli: config.json
    """
    if sys.platform == "darwin":  # macOS
        return {
            "vscode": Path.home() / "Library" / "Application Support" / "Code" / "User" / "settings.json",
            "cursor": Path.home() / "Library" / "Application Support" / "Cursor" / "User" / "settings.json",
            "windsurf": Path.home() / "Library" / "Application Support" / "Windsurf" / "User" / "settings.json",
            "claude-code": Path.home() / "Library" / "Application Support" / "Claude" / "User" / "settings.json",
            "cline": Path.home() / ".config" / "cline" / "mcp_servers.json",
            "antigravity": Path.home() / ".config" / "antigravity" / "settings.json",
            "gemini-cli": Path.home() / ".config" / "gemini" / "config.json",
        }
    elif sys.platform == "win32":  # Windows
        return {
            "vscode": Path.home() / "AppData" / "Roaming" / "Code" / "User" / "settings.json",
            "cursor": Path.home() / "AppData" / "Roaming" / "Cursor" / "User" / "settings.json",
            "windsurf": Path.home() / "AppData" / "Roaming" / "Windsurf" / "User" / "settings.json",
            "claude-code": Path.home() / "AppData" / "Roaming" / "Claude" / "User" / "settings.json",
            "cline": Path.home() / "AppData" / "Roaming" / "cline" / "mcp_servers.json",
            "antigravity": Path.home() / "AppData" / "Roaming" / "antigravity" / "settings.json",
            "gemini-cli": Path.home() / "AppData" / "Local" / "gemini" / "config.json",
        }
    else:  # Linux
        return {
            "vscode": Path.home() / ".config" / "Code" / "User" / "settings.json",
            "cursor": Path.home() / ".config" / "Cursor" / "User" / "settings.json",
            "windsurf": Path.home() / ".config" / "Windsurf" / "User" / "settings.json",
            "claude-code": Path.home() / ".config" / "Claude" / "User" / "settings.json",
            "cline": Path.home() / ".config" / "cline" / "mcp_servers.json",
            "antigravity": Path.home() / ".config" / "antigravity" / "settings.json",
            "gemini-cli": Path.home() / ".config" / "gemini" / "config.json",
        }


def generate_config_for_ide(ide: str) -> str:
    """
    Generate config string for a specific IDE.
    
    Supported IDEs:
    - vscode, cursor, windsurf, claude-code (mcpServers format)
    - cline, antigravity, gemini-cli (alternative formats)
    
    Returns JSON that can be pasted into IDE settings file.
    """
    config = generate_mcp_config()
    
    # Most IDEs use mcpServers format
    return json.dumps(config, indent=2)
