"""
FadCat entry point
"""
import sys

from src.core.pidcat_runner import run_pidcat_child

try:
    from PyQt6.QtWidgets import QApplication, QSplashScreen
    from PyQt6.QtGui import QPixmap
    from PyQt6.QtCore import Qt, QTimer
    from pathlib import Path
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
            with open(pidcat_path, 'r') as f:
                pidcat_code = f.read()
            # Execute pidcat code with proper namespace
            exec(compile(pidcat_code, pidcat_path, 'exec'), {'__name__': '__main__'})
        except Exception as e:
            import traceback
            print(f"Error running pidcat: {e}", file=sys.stderr)
            traceback.print_exc()
            sys.exit(1)
        return
    
    # internal child-process mode used by ProcessReader
    if '--child-pidcat' in sys.argv:
        run_pidcat_child()
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
