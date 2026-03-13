import os
import sys
import subprocess
from pathlib import Path
from src.core.settings import SettingsManager

def get_pidcat_path():
    """Returns the path to the bundled pidcat script with robust fallback logic.
    
    Handles multiple bundle structures:
    - macOS app bundle: Contents/Resources/src/core/pidcat.py
    - Linux dist folder: _internal/src/core/pidcat.py
    - Windows dist folder: _internal/src/core/pidcat.py
    - Dev mode: src/core/pidcat.py (relative to project root)
    """
    if getattr(sys, 'frozen', False):
        # Running as bundled PyInstaller app
        base_dir = Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))
        pidcat_path = base_dir / "src" / "core" / "pidcat.py"
        
        if pidcat_path.exists():
            return str(pidcat_path)
        
        # Fallback 1: Try one level up (sometimes _MEIPASS might be wrong)
        fallback1 = base_dir.parent / "src" / "core" / "pidcat.py"
        if fallback1.exists():
            return str(fallback1)
        
        # Fallback 2: Search in common PyInstaller locations
        fallback2 = Path(sys.executable).parent / "src" / "core" / "pidcat.py"
        if fallback2.exists():
            return str(fallback2)
        
        # Fallback 3: Search relative to frozen app
        if hasattr(sys, 'frozen') and sys.frozen == 'macosx_app':
            # macOS app: executable is in MacOS/, resources are in Resources/
            app_resources = Path(sys.executable).parent.parent / "Resources" / "src" / "core" / "pidcat.py"
            if app_resources.exists():
                return str(app_resources)
        
        # If all else fails, raise error with debugging info
        raise FileNotFoundError(
            f"pidcat.py not found in bundled app.\n"
            f"  _MEIPASS: {base_dir}\n"
            f"  Expected: {pidcat_path}\n"
            f"  sys.executable: {sys.executable}"
        )
    else:
        # Running as script - use project root
        project_root = Path(__file__).parent.parent.parent
        return str(project_root / "src" / "core" / "pidcat.py")

def get_python_executable():
    """Returns the bundled Python executable.
    
    In both dev and bundled modes, sys.executable IS the Python interpreter:
    - Dev mode: system Python running FadCat.py
    - Bundled mode: PyInstaller-bundled Python (FadCat app binary IS Python)
    
    Note: In bundled mode, pidcat runs via exec() in FadCat.py (not subprocess)
    to avoid re-launching the FadCat app window.
    """
    return sys.executable

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
    
    # Ensure project root is in PYTHONPATH for subprocess
    project_root = str(Path(__file__).parent.parent.parent)
    pythonpath = env.get('PYTHONPATH', '')
    if project_root not in pythonpath:
        env['PYTHONPATH'] = project_root + ':' + pythonpath if pythonpath else project_root
        
    settings = SettingsManager.load()
    package = pkg or settings.get("default_package", "com.fadcam.beta")
    
    pidcat_path = get_pidcat_path()
    python_executable = get_python_executable()
    
    # Build pidcat command with ignored tags
    cmd = [python_executable, pidcat_path, package]
    
    # Add ignored tags from settings
    ignored_tags = settings.get("ignored_tags", [])
    for tag in ignored_tags:
        cmd.extend(['-i', tag])
    
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
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
