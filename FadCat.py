"""
FadCat entry point
"""
import sys

print("DEBUG: FadCat.py starting...")

from src.core.pidcat_runner import run_pidcat_child

print("DEBUG: pidcat_runner imported")

try:
    from PyQt6.QtWidgets import QApplication, QSplashScreen
    from PyQt6.QtGui import QPixmap
    from PyQt6.QtCore import Qt, QTimer
    from pathlib import Path
    QT_AVAILABLE = True
    print("DEBUG: PyQt6 imported successfully")
except ImportError as e:
    print(f"DEBUG: Import error: {e}")
    QT_AVAILABLE = False


def launch_gui():
    if not QT_AVAILABLE:
        print("PyQt6 is not installed. Run: pip install PyQt6")
        sys.exit(1)
    app = QApplication(sys.argv)
    app.setApplicationName("FadCat")
    app.setOrganizationName("FadCat")
    splash = None
    splash_delay_ms = 1500
    try:
        logo_path = Path(__file__).parent / "src" / "icons" / "fadcat-logo.png"
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
