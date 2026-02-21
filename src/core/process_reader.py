import os
import subprocess
from PyQt6 import QtCore

class ProcessReader(QtCore.QThread):
    """Background thread that runs pidcat (or whatever cmd) and emits lines.
    On POSIX we attach the child to a pty so pidcat will emit ANSI escapes; on other
    systems we fall back to using pipes.
    """
    line_ready = QtCore.pyqtSignal(str)
    finished = QtCore.pyqtSignal()

    def __init__(self, cmd, env=None, input_text=None):
        super().__init__()
        self.cmd = cmd
        self.env = env or os.environ.copy()
        self.input_text = input_text
        self.process = None

    def run(self):
        env = dict(self.env)
        env.setdefault('PYTHONUNBUFFERED', '1')
        # Encourage color output
        env.setdefault('TERM', 'xterm-256color')
        env.setdefault('FORCE_COLOR', '1')
        # Ask pidcat to treat the terminal as very wide so it doesn't hard-wrap lines
        env.setdefault('COLUMNS', '2000')
        env.setdefault('LINES', '2000')

        # On POSIX, spawn the child attached to a pty so pidcat thinks it's a TTY
        if os.name == 'posix':
            try:
                import pty
                master, slave = pty.openpty()
                self.process = subprocess.Popen(self.cmd, stdin=slave, stdout=slave, stderr=slave, env=env)
                os.close(slave)
                buf = b''
                while True:
                    try:
                        chunk = os.read(master, 4096)
                    except OSError:
                        break
                    if not chunk:
                        break
                    buf += chunk
                    while b'\n' in buf:
                        line, buf = buf.split(b'\n', 1)
                        try:
                            decoded = line.decode('utf-8', errors='replace')
                        except Exception:
                            decoded = line.decode('latin-1', errors='replace')
                        self.line_ready.emit(decoded + '\n')
                if buf:
                    try:
                        decoded = buf.decode('utf-8', errors='replace')
                    except Exception:
                        decoded = buf.decode('latin-1', errors='replace')
                    self.line_ready.emit(decoded)
                try:
                    os.close(master)
                except Exception:
                    pass
                if self.process:
                    self.process.wait()
            finally:
                self.finished.emit()
            return

        # Fallback: use PIPE and text mode
        stdin_pipe = subprocess.PIPE if self.input_text else None
        try:
            self.process = subprocess.Popen(self.cmd, stdin=stdin_pipe, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, bufsize=1)
            if self.input_text and self.process.stdin:
                try:
                    self.process.stdin.write(self.input_text + '\n')
                    self.process.stdin.flush()
                except Exception:
                    pass

            for line in iter(self.process.stdout.readline, ''):
                if not line:
                    break
                self.line_ready.emit(line)

            try:
                if self.process.stdout:
                    self.process.stdout.close()
            except Exception:
                pass
            self.process.wait()
        finally:
            self.finished.emit()
