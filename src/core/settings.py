import json
from pathlib import Path

SETTINGS_FILE = Path.home() / ".fadcat_settings.json"

DEFAULT_SETTINGS = {
    "packages": ["com.fadcam.beta", "com.android.systemui"],
    "default_package": "com.fadcam.beta",
    "theme": "dark",
    "ignored_tags": [
        "gralloc4",          # GPU memory allocation spam (register/unregister)
        "BufferPoolAccessor*",  # Buffer pool management spam
        "hwbinder",          # Hardware binder spam
        "binder",            # General binder spam (very verbose)
        "libc",              # C library messages
        "perfetto",          # System tracing (verbose)
        "PowerManagerService",  # Power management spam
        "WifiManager",       # Wifi spam
        "ConnectivityManager",  # Connectivity spam
        "BluetoothAdapter",  # Bluetooth spam
        "libEGL",            # OpenGL ES spam
        "libGLESv2",         # OpenGL ES 2.0 spam
        "PermissionController",  # Permission spam
        "system_server",     # System server noise
    ]
}

class SettingsManager:
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
    """Convenience wrapper for settings."""
    
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
    
    def save(self):
        SettingsManager.save(self._data)

