import os
import sys
import subprocess
from pathlib import Path
from src.core.settings import SettingsManager

def get_pidcat_path():
    """Returns the path to the bundled pidcat script."""
    if getattr(sys, 'frozen', False):
        # Running as a bundled exe
        base_dir = Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))
        return str(base_dir / "src" / "core" / "pidcat.py")
    else:
        # Running as script
        return str(Path(__file__).parent / "pidcat.py")

def run_pidcat_child():
    """Child mode: run pidcat with the same behavior and forward stdout."""
    pkg = None
    dev = None
    argv = sys.argv[1:]
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--package' and i + 1 < len(argv):
            pkg = argv[i + 1]; i += 2; continue
        if a == '--device' and i + 1 < len(argv):
            dev = argv[i + 1]; i += 2; continue
        i += 1
    env = os.environ.copy()
    if dev:
        env['ANDROID_SERIAL'] = dev
        
    settings = SettingsManager.load()
    package = pkg or settings.get("default_package", "com.fadcam.beta")
    
    pidcat_path = get_pidcat_path()
    
    try:
        p = subprocess.Popen([sys.executable, pidcat_path, package], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        for line in iter(p.stdout.readline, ''):
            if not line:
                break
            sys.stdout.write(line)
            sys.stdout.flush()
        try:
            p.stdout.close()
        except Exception:
            pass
        p.wait()
    except KeyboardInterrupt:
        try:
            if p and getattr(p, 'terminate', None):
                p.terminate()
        except Exception:
            pass
    sys.exit(0)
