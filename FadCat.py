"""
FadCat entry point
"""
import sys
import os

# Auto-install CLI wrapper on macOS (first launch only)
def _install_cli():
    if sys.platform != 'darwin':
        return
    try:
        cli_dir = os.path.expanduser('~/.local/bin')
        cli_dst = os.path.join(cli_dir, 'fadcat')

        app_bin = '/Applications/FadCat.app/Contents/MacOS/FadCat'
        if not os.path.exists(app_bin):
            return
        desired = f'#!/bin/bash\nexec "{app_bin}" "$@"\n'

        if os.path.exists(cli_dst):
            try:
                with open(cli_dst, 'r', encoding='utf-8') as f:
                    if f.read() == desired:
                        return
            except Exception:
                pass

        os.makedirs(cli_dir, exist_ok=True)
        with open(cli_dst, 'w', encoding='utf-8') as f:
            f.write(desired)
        os.chmod(cli_dst, 0o755)

        # Add to PATH for login shells
        for rc in ['.zprofile', '.bash_profile']:
            rc_path = os.path.expanduser(f'~/{rc}')
            try:
                if os.path.exists(rc_path):
                    with open(rc_path, 'r+', encoding='utf-8') as f:
                        content = f.read()
                        if '$HOME/.local/bin' not in content and '.local/bin' not in content:
                            f.write('\nexport PATH="$HOME/.local/bin:$PATH"\n')
            except Exception:
                pass
    except Exception:
        # Silently fail - CLI install is optional
        pass

_install_cli()

# Check for CLI/MCP modes BEFORE importing PyQt6 (which captures stdin)
# This prevents "RuntimeError: lost sys.stdin" when using --cli or --mcp
_is_cli_mode = '--cli' in sys.argv or '--mcp' in sys.argv or '--child-pidcat' in sys.argv
_is_pidcat_mode = len(sys.argv) > 1 and 'pidcat.py' in sys.argv[1]

from src.core.pidcat_runner import run_pidcat_child
from pathlib import Path

QT_AVAILABLE = False
if not _is_cli_mode and not _is_pidcat_mode:
    try:
        from PyQt6.QtWidgets import QApplication, QSplashScreen
        from PyQt6.QtGui import QPixmap
        from PyQt6.QtCore import Qt, QTimer
        QT_AVAILABLE = True
    except ImportError as e:
        QT_AVAILABLE = False


def launch_gui():
    if not QT_AVAILABLE:
        print("PyQt6 is not installed. Run: pip install PyQt6")
        sys.exit(1)
    
    # Suppress PyQt warnings (font, platform theme, etc)
    # These are cosmetic warnings that don't affect functionality
    import os
    os.environ['QT_LOGGING_RULES'] = '*=false'
    
    app = QApplication(sys.argv)
    
    # Import version
    from src.version import __version__, __app_name__
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("FadSecLab")
    
    splash = None
    splash_delay_ms = 1500
    try:
        # Try multiple possible icon paths for bundled/dev environments
        # Use fadcat-logo.png for splash screen
        logo_path = Path(__file__).parent / "src" / "icons" / "fadcat-logo.png"
        if not logo_path.exists():
            # Try relative to Resources in bundled app
            logo_path = Path(__file__).parent / "Resources" / "src" / "icons" / "fadcat-logo.png"
        if not logo_path.exists():
            # Try looking in sys.frozen context
            if hasattr(sys, 'frozen'):
                logo_path = Path(sys.frozen) / "src" / "icons" / "fadcat-logo.png"
        
        if logo_path.exists():
            pix = QPixmap(str(logo_path))
            if not pix.isNull():
                pix = pix.scaled(280, 280, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                splash = QSplashScreen(pix)
                splash.setMask(pix.mask())
                splash.setStyleSheet("background: transparent;")
                splash.show()
                splash.raise_()
                app.processEvents()
    except Exception:
        splash = None
    def _show_main():
        from src.ui.gui_app import LogcatGUI
        win = LogcatGUI()
        win.show()
        if splash:
            splash.finish(win)
    def _show_splash_then_main():
        if splash:
            splash.show()
            splash.raise_()
            app.processEvents()
            QTimer.singleShot(splash_delay_ms, _show_main)
        else:
            _show_main()
    QTimer.singleShot(0, _show_splash_then_main)
    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        pass


def main():
    # Handle direct pidcat.py execution (when bundled FadCat runs pidcat as subprocess)
    if len(sys.argv) > 1 and 'pidcat.py' in sys.argv[1]:
        # Run pidcat directly instead of GUI
        # pidcat.py expects to execute when imported, so we use exec to run its code
        pidcat_path = sys.argv[1]
        pidcat_args = sys.argv[2:] if len(sys.argv) > 2 else []

        # Update sys.argv to what pidcat expects
        sys.argv = [pidcat_path] + pidcat_args

        try:
            with open(pidcat_path, 'r', encoding='utf-8') as f:
                pidcat_code = f.read()
            # Execute pidcat code with a safe print/input to avoid OSError
            # when stdout/stderr are not standard consoles (bundled GUI).
            import os as _os
            import sys as _sys

            def _safe_print(*args, **kwargs):
                sep = kwargs.get('sep', ' ')
                end = kwargs.get('end', '\n')
                text = sep.join(str(a) for a in args) + end
                try:
                    # Try writing str to stdout
                    _sys.stdout.write(text)
                    _sys.stdout.flush()
                except Exception:
                    try:
                        # Fallback: write encoded bytes to buffer if available
                        if hasattr(_sys.stdout, 'buffer'):
                            _sys.stdout.buffer.write(text.encode('utf-8', errors='replace'))
                            _sys.stdout.buffer.flush()
                        else:
                            # Last resort: attempt stderr
                            _sys.stderr.write(text)
                            _sys.stderr.flush()
                    except Exception:
                        # Give up silently to avoid cascading exceptions during shutdown
                        pass

            def _safe_input(prompt=''):
                try:
                    return input(prompt)
                except EOFError:
                    raise
                except Exception:
                    return ''

            exec(compile(pidcat_code, pidcat_path, 'exec'), {
                '__name__': '__main__',
                'os': _os,
                'sys': _sys,
                'print': _safe_print,
                'input': _safe_input,
            })
        except Exception as e:
            import traceback
            print(f"Error running pidcat: {e}", file=sys.stderr)
            traceback.print_exc()
            sys.exit(1)
        return

    # internal child-process mode used by ProcessReader
    # Usage: fadcat --child-pidcat --package /path/to/pidcat.py [--device SERIAL] [PACKAGE_NAME]
    if '--child-pidcat' in sys.argv:
        from src.core.pidcat_runner import run_pidcat_child
        run_pidcat_child()
        return

    # MCP (Model Context Protocol) server mode
    if '--mcp' in sys.argv:
        try:
            from src.mcp.server import main as run_mcp
            print("Starting FadCat MCP Server...", file=sys.stderr)
            run_mcp()
        except ImportError as e:
            print(f"MCP dependencies not installed: {e}", file=sys.stderr)
            print("Run: pip install -r requirements.txt", file=sys.stderr)
            sys.exit(1)
        except KeyboardInterrupt:
            print("MCP Server stopped", file=sys.stderr)
            sys.exit(0)
        except Exception as e:
            print(f"MCP Server error: {e}", file=sys.stderr)
            sys.exit(1)
        return

    # explicit CLI mode
    if '--cli' in sys.argv:
        from src.cli.cli_app import LogcatCLI
        LogcatCLI().run()
        return

    # default: GUI
    launch_gui()


if __name__ == '__main__':
    main()
