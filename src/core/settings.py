import json
from pathlib import Path

SETTINGS_FILE = Path.home() / ".fadcat_settings.json"

DEFAULT_SETTINGS = {
    "packages": ["com.fadcam.beta", "com.android.systemui"],
    "default_package": "com.fadcam.beta",
    "theme": "dark"
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
