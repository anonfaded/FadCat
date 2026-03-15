"""
pidcat_runner.py - Helper functions for running pidcat in FadCat.

This module provides functions to:
- Get the path to the bundled pidcat.py script
- Get the Python executable path
- Run pidcat as a child process (for bundled mode)
"""
import os
import sys
import subprocess
from pathlib import Path


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

        # Fallback 1: Try one level up
        fallback1 = base_dir.parent / "src" / "core" / "pidcat.py"
        if fallback1.exists():
            return str(fallback1)

        # Fallback 2: Search in common PyInstaller locations
        fallback2 = Path(sys.executable).parent / "src" / "core" / "pidcat.py"
        if fallback2.exists():
            return str(fallback2)

        # Fallback 3: Search relative to frozen app
        if hasattr(sys, 'frozen') and sys.frozen == 'macosx_app':
            # macOS app: executable in MacOS/, resources in Resources/
            app_resources = (
                Path(sys.executable).parent.parent
                / "Resources" / "src" / "core" / "pidcat.py"
            )
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
    """Child mode: run pidcat via subprocess to avoid re-launching FadCat GUI.

    Command line format:
        fadcat --child-pidcat --package /path/to/pidcat.py \\
               [--device SERIAL] [PACKAGE_NAME] [PIDCAT_ARGS...]

    This is used by ProcessReader in bundled mode to run pidcat without
    causing the FadCat app to re-launch itself.
    """
    # Parse only our custom flags, pass everything else to pidcat
    argv = sys.argv[1:]
    pidcat_path = None
    device = None

    i = 0
    while i < len(argv):
        if argv[i] == '--child-pidcat':
            i += 1
        elif argv[i] == '--package' and i + 1 < len(argv):
            pidcat_path = argv[i + 1]
            i += 2
        elif argv[i] == '--device' and i + 1 < len(argv):
            device = argv[i + 1]
            i += 2
        else:
            break

    # Remaining args are for pidcat
    pidcat_args = argv[i:]

    env = os.environ.copy()
    if device:
        env['ANDROID_SERIAL'] = device

    # Ensure project root is in PYTHONPATH
    project_root = str(Path(__file__).parent.parent.parent)
    pythonpath = env.get('PYTHONPATH', '')
    if project_root not in pythonpath:
        env['PYTHONPATH'] = project_root + ':' + pythonpath if pythonpath else project_root

    if not pidcat_path:
        pidcat_path = get_pidcat_path()

    python_executable = get_python_executable()

    # Build pidcat command
    cmd = [python_executable, pidcat_path] + pidcat_args

    # On POSIX, use PTY to preserve ANSI colors (pidcat checks isatty)
    if os.name == 'posix':
        import pty
        import select

        master, slave = pty.openpty()
        p = subprocess.Popen(
            cmd, stdin=slave, stdout=slave, stderr=slave,
            env=env, close_fds=True
        )
        os.close(slave)
        try:
            while True:
                r, _, _ = select.select([master], [], [], 0.2)
                if r:
                    chunk = os.read(master, 4096)
                    if not chunk:
                        break
                    sys.stdout.write(chunk.decode('utf-8', errors='replace'))
                    sys.stdout.flush()
        except KeyboardInterrupt:
            pass
        finally:
            try:
                os.close(master)
            except OSError:
                pass
            try:
                p.wait(timeout=0.5)
            except BaseException:
                try:
                    p.kill()
                except BaseException:
                    pass
    else:
        # Windows fallback: use PIPE
        try:
            p = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, env=env
            )
            for line in iter(p.stdout.readline, ''):
                if not line:
                    break
                sys.stdout.write(line)
                sys.stdout.flush()
            try:
                p.stdout.close()
            except OSError:
                pass
            p.wait()
        except KeyboardInterrupt:
            try:
                if p and getattr(p, 'terminate', None):
                    p.terminate()
            except OSError:
                pass
    sys.exit(0)
