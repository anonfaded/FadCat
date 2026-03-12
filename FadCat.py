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
    from PyQt6.QtCore import Qt
    from pathlib import Path
    from src.ui.gui_app import LogcatGUI
    QT_AVAILABLE = True
    print("DEBUG: PyQt6 and GUI imported successfully")
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
    try:
        logo_path = Path(__file__).parent / "src" / "icons" / "fadcat-logo.png"
        if logo_path.exists():
            pix = QPixmap(str(logo_path))
            if not pix.isNull():
                pix = pix.scaled(280, 280, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                splash = QSplashScreen(pix)
                splash.show()
                app.processEvents()
    except Exception:
        splash = None
    win = LogcatGUI()
    win.show()
    if splash:
        splash.finish(win)
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
