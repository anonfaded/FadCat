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


def generate_mcp_config() -> Dict[str, Any]:
    """
    Generate MCP configuration for IDEs.
    
    Returns config that can be merged into IDE settings.
    """
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
                "env": {
                    "PYTHONUNBUFFERED": "1"
                }
            }
        }
    }


def get_vscode_config_path() -> Path:
    """Get VSCode settings.json path."""
    if sys.platform == "darwin":  # macOS
        return Path.home() / ".config" / "Code" / "User" / "settings.json"
    elif sys.platform == "win32":  # Windows
        return Path.home() / "AppData" / "Roaming" / "Code" / "User" / "settings.json"
    else:  # Linux
        return Path.home() / ".config" / "Code" / "User" / "settings.json"


def get_cursor_config_path() -> Path:
    """Get Cursor settings.json path."""
    if sys.platform == "darwin":  # macOS
        return Path.home() / ".config" / "Cursor" / "User" / "settings.json"
    elif sys.platform == "win32":  # Windows
        return Path.home() / "AppData" / "Roaming" / "Cursor" / "User" / "settings.json"
    else:  # Linux
        return Path.home() / ".config" / "Cursor" / "User" / "settings.json"


def get_windsurf_config_path() -> Path:
    """Get Windsurf settings.json path."""
    if sys.platform == "darwin":  # macOS
        return Path.home() / ".config" / "Windsurf" / "User" / "settings.json"
    elif sys.platform == "win32":  # Windows
        return Path.home() / "AppData" / "Roaming" / "Windsurf" / "User" / "settings.json"
    else:  # Linux
        return Path.home() / ".config" / "Windsurf" / "User" / "settings.json"


def generate_config_for_ide(ide: str) -> str:
    """
    Generate config string for a specific IDE.
    
    Format: JSON that can be pasted into settings.json
    """
    config = generate_mcp_config()
    return json.dumps(config, indent=2)
