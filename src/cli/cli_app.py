import os
import sys
import subprocess
from src.utils.adb_utils import get_adb_devices
from src.core.pidcat_runner import get_pidcat_path, DEFAULT_PACKAGE

class LogcatCLI:
    def __init__(self):
        self.default_package = DEFAULT_PACKAGE

    def run_logcat(self, package=None):
        devices = get_adb_devices()
        chosen = None
        if not devices:
            print('No adb devices found.')
            return
        if len(devices) == 1:
            chosen = devices[0]
        else:
            print('Multiple devices found:')
            for i, d in enumerate(devices, 1):
                print(f'  [{i}] {d}')
            while True:
                sel = input(f'Enter device number [1-{len(devices)}]: ').strip()
                if sel.isdigit() and 1 <= int(sel) <= len(devices):
                    chosen = devices[int(sel) - 1]
                    break

        env = os.environ.copy()
        if chosen:
            env['ANDROID_SERIAL'] = chosen

        package = package or self.default_package
        env['PYTHONUNBUFFERED'] = '1'
        
        pidcat_path = get_pidcat_path()
        
        if chosen:
            cmd = [sys.executable, pidcat_path, '-s', chosen, package]
        else:
            cmd = [sys.executable, pidcat_path, package]
        try:
            subprocess.run(cmd, env=env)
        except KeyboardInterrupt:
            print('\nCtrl+C detected. Exiting.')
            return

    def run(self):
        while True:
            try:
                pkg = input(f'Enter package (or ENTER for default "{self.default_package}", "all" for full): ').strip()
                self.run_logcat(pkg if pkg else None)
                cont = input('Run another? (y/n): ').strip().lower()
                if cont != 'y':
                    break
            except KeyboardInterrupt:
                print('\nCtrl+C detected. Exiting.')
                break
