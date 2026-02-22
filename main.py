"""
FadCat entry point
"""
import sys

from src.core.pidcat_runner import run_pidcat_child

try:
    from PyQt6.QtWidgets import QApplication
    from src.ui.gui_app import LogcatGUI
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False


def launch_gui():
    if not QT_AVAILABLE:
        print("PyQt6 is not installed. Run: pip install PyQt6")
        sys.exit(1)
    app = QApplication(sys.argv)
    app.setApplicationName("FadCat")
    app.setOrganizationName("FadCat")
    win = LogcatGUI()
    win.show()
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

