import sys
from src.cli.cli_app import LogcatCLI
from src.core.pidcat_runner import run_pidcat_child

try:
    from PyQt6.QtWidgets import QApplication
    from src.ui.gui_app import LogcatGUI
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

def choose_mode():
    print('Choose mode:')
    print('1. CLI')
    print('2. GUI (PyQt6)')
    choice = input('Enter 1 or 2: ').strip()
    if choice == '1':
        assistant = LogcatCLI()
        assistant.run()
    elif choice == '2':
        if not QT_AVAILABLE:
            print('PyQt6 not available. Install PyQt6 or run in CLI mode.')
            return
        app = QApplication(sys.argv)
        win = LogcatGUI()
        win.show()
        try:
            app.exec()
        except KeyboardInterrupt:
            pass
    else:
        print('Invalid choice')

def main():
    if '--child-pidcat' in sys.argv:
        run_pidcat_child()
        return

    if len(sys.argv) > 1 and sys.argv[1] == 'gui':
        if not QT_AVAILABLE:
            print('PyQt6 not available. Install PyQt6 or run without args for CLI.')
            sys.exit(1)
        app = QApplication(sys.argv)
        win = LogcatGUI()
        win.show()
        try:
            app.exec()
        except KeyboardInterrupt:
            pass
    else:
        choose_mode()

if __name__ == '__main__':
    main()
