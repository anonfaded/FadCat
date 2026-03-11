import json
import sys
import os
from pathlib import Path

def get_settings_path() -> Path:
    """
    Returns the path to the settings file.
    In development (not frozen), it uses the project root.
    In production (frozen), it uses platform-specific app data directories.
    """
    if getattr(sys, 'frozen', False):
        # Packaged/Production mode: OS-standard locations
        if sys.platform == 'win32':
            base = Path(os.environ.get('APPDATA', Path.home()))
        elif sys.platform == 'darwin':
            base = Path.home() / 'Library' / 'Application Support'
        else:
            base = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
        
        app_dir = base / "FadCat"
        app_dir.mkdir(parents=True, exist_ok=True)
        return app_dir / "settings.json"
    else:
        # Development mode: project root for easy access
        root = Path(__file__).parent.parent.parent
        return root / "fadcat_settings.json"

SETTINGS_FILE = get_settings_path()

# Default configuration - safe defaults for a clean start
DEFAULT_SETTINGS = {
    "packages": ["com.fadcam", "com.fadcam.beta"],
    "default_package": "com.fadcam.beta",
    "theme": "dark",
    "ignored_tags": [
        "gralloc4",
        "BufferPoolAccessor*",
        "hwbinder",
        "binder",
        "libc",
        "perfetto",
        "PowerManagerService",
        "WifiManager",
        "ConnectivityManager",
        "BluetoothAdapter",
        "libEGL",
        "libGLESv2",
        "PermissionController",
        "system_server",
    ],
    "session_titles": [], # List of last open session titles
    "device_names": {}    # Mapping of {serial: custom_name}
}

class SettingsManager:
    """Handles low-level JSON I/O for application settings."""
    @staticmethod
    def load():
        if not SETTINGS_FILE.exists():
            return DEFAULT_SETTINGS.copy()
        try:
            with open(SETTINGS_FILE, 'r') as f:
                data = json.load(f)
                settings = DEFAULT_SETTINGS.copy()
                settings.update(data)
                return settings
        except Exception:
            return DEFAULT_SETTINGS.copy()

    @staticmethod
    def save(settings):
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")


class Settings:
    """Convenience wrapper for application-wide settings with getter/setter properties."""
    
    def __init__(self):
        self._data = SettingsManager.load()
    
    @property
    def packages(self) -> list[str]:
        return self._data.get("packages", [])
    
    @packages.setter
    def packages(self, value: list[str]):
        self._data["packages"] = value
    
    @property
    def default_package(self) -> str:
        return self._data.get("default_package", "")
    
    @default_package.setter
    def default_package(self, value: str):
        self._data["default_package"] = value
    
    @property
    def ignored_tags(self) -> list[str]:
        return self._data.get("ignored_tags", DEFAULT_SETTINGS.get("ignored_tags", []))
    
    @ignored_tags.setter
    def ignored_tags(self, value: list[str]):
        self._data["ignored_tags"] = value

    @property
    def session_titles(self) -> list[str]:
        return self._data.get("session_titles", [])

    @session_titles.setter
    def session_titles(self, value: list[str]):
        self._data["session_titles"] = value

    @property
    def device_names(self) -> dict[str, str]:
        return self._data.get("device_names", {})

    @device_names.setter
    def device_names(self, value: dict[str, str]):
        self._data["device_names"] = value
    
    def save(self):
        SettingsManager.save(self._data)

