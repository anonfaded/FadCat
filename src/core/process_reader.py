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
        self._pty_master = None
        self._stop_requested = False
        self._exec_stop_requester = None  # For exec mode stop requests

    def stop(self):
        """Terminate the child process and close PTY to break read loop."""
        self._stop_requested = True
        # Also signal exec mode to stop if running
        if self._exec_stop_requester:
            self._exec_stop_requester.stop = True
        try:
            self.requestInterruption()
        except Exception:
            pass
        if self.process:
            try:
                # On Windows, terminate the entire process tree
                if os.name == 'nt':
                    import subprocess as sp
                    try:
                        sp.run(['taskkill', '/F', '/T', '/PID', str(self.process.pid)], 
                               check=False, capture_output=True, timeout=2)
                    except Exception:
                        pass
                else:
                    self.process.terminate()
            except Exception:
                pass
            # Hard kill fallback if terminate doesn't exit quickly
            try:
                self.process.wait(timeout=0.5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
        if self._pty_master is not None:
            try:
                os.close(self._pty_master)
            except Exception:
                pass
            self._pty_master = None

    def _run_pidcat_via_exec(self, pidcat_path, pidcat_args=None):
        """Run pidcat.py via exec() to avoid subprocess re-launching FadCat app.

        This is called in bundled mode to execute pidcat code directly without subprocess,
        which would cause sys.executable (the FadCat app binary) to be re-launched.

        Note: This approach works on macOS but can cause segfaults on Linux due to
        Qt thread safety issues with subprocess calls inside exec().
        """
        import sys as _sys
        import platform
        from pathlib import Path
        from src.utils.adb_path import get_arch_suffix

        pidcat_file = Path(pidcat_path)

        if not pidcat_file.exists():
            self.line_ready.emit(f"❌ Error: pidcat script not found at {pidcat_path}\n")
            self.finished.emit()
            return

        # Determine bundled ADB path
        system = platform.system()
        arch_suffix = get_arch_suffix()
        if arch_suffix is None:
            self.line_ready.emit(f"❌ Error: unsupported architecture for bundled ADB on {system}\n")
            self.finished.emit()
            return

        meipass_root = getattr(_sys, "_MEIPASS", None)
        if meipass_root:
            base_path = Path(meipass_root) / "platform-tools" / arch_suffix
        else:
            base_path = Path(_sys.executable).parent.parent / "Resources" / "platform-tools" / arch_suffix

        adb_binary = "adb.exe" if system == "Windows" else "adb"
        bundled_adb_path = str(base_path / adb_binary)

        # Save original state
        original_argv = _sys.argv
        original_frozen = getattr(_sys, 'frozen', False)
        original_adb_override = os.environ.get('FADCAT_ADB_PATH', None)

        try:
            # Setup for pidcat execution
            _sys.argv = [str(pidcat_file)] + (pidcat_args or [])
            _sys.frozen = True
            os.environ['FADCAT_ADB_PATH'] = bundled_adb_path

            # Add _internal to sys.path for imports to work
            if hasattr(_sys, '_MEIPASS'):
                _internal_path = Path(_sys._MEIPASS)
                if (_internal_path / '_internal').exists():
                    _internal_path = _internal_path / '_internal'
                if str(_internal_path) not in _sys.path:
                    _sys.path.insert(0, str(_internal_path))

            # Read pidcat code
            with open(pidcat_path, 'r', encoding='utf-8') as f:
                pidcat_code = f.read()

            # Create namespace for execution
            def _safe_input(prompt=""):
                self._emit_print(prompt, end="")
                raise EOFError("No stdin available")

            class _StopRequester:
                def __init__(self):
                    self.stop = False

            stop_requester = _StopRequester()
            self._exec_stop_requester = stop_requester

            namespace = {
                '__name__': '__main__',
                '__file__': pidcat_path,
                '_process_reader': self,
                'print': self._emit_print,
                'input': _safe_input,
                'sys': _sys,
                '__stdout_isatty_override__': True,
                '__stop_requester__': stop_requester,
            }

            # Execute pidcat code
            exec(compile(pidcat_code, pidcat_path, 'exec'), namespace)

        except KeyboardInterrupt:
            self.line_ready.emit("--- FadCat stopped. ---\n")
        except SystemExit as e:
            # pidcat called sys.exit() - this is normal
            self.line_ready.emit(f"--- pidcat exited with code: {e.code} ---\n")
        except Exception as e:
            import traceback
            self.line_ready.emit(f"❌ Error running pidcat: {e}\n")
            self.line_ready.emit("--- Traceback ---\n")
            self.line_ready.emit(traceback.format_exc())
        finally:
            # Restore original state
            _sys.argv = original_argv
            _sys.frozen = original_frozen
            if original_adb_override is None:
                os.environ.pop('FADCAT_ADB_PATH', None)
            else:
                os.environ['FADCAT_ADB_PATH'] = original_adb_override
            self._exec_stop_requester = None
            self.finished.emit()

    def _emit_print(self, *args, **kwargs):
        """Custom print function that emits lines via signal instead of to stdout."""
        end = kwargs.get('end', '\n')
        sep = kwargs.get('sep', ' ')
        line = sep.join(str(arg) for arg in args) + end
        self.line_ready.emit(line)

    def run(self):
        """Main thread execution - runs pidcat and emits output lines."""
        env = dict(self.env)
        env.setdefault('PYTHONUNBUFFERED', '1')
        # Encourage color output
        env.setdefault('TERM', 'xterm-256color')
        env.setdefault('FORCE_COLOR', '1')
        env.setdefault('FORCE_COLOR_OUTPUT', '1')  # Force pidcat to output ANSI colors
        # Ask pidcat to treat the terminal as very wide so it doesn't hard-wrap lines
        env.setdefault('COLUMNS', '2000')
        env.setdefault('LINES', '2000')

        # Special case: __exec_pidcat__ means run pidcat via exec to avoid re-launching app
        if self.cmd and self.cmd[0] == '__exec_pidcat__':
            pidcat_path = self.cmd[1] if len(self.cmd) > 1 else None
            pidcat_args = self.cmd[2:] if len(self.cmd) > 2 else []
            self._run_pidcat_via_exec(pidcat_path, pidcat_args)
            return

        # On POSIX, spawn the child attached to a pty so pidcat thinks it's a TTY
        if os.name == 'posix':
            try:
                import pty
                import select
                master, slave = pty.openpty()
                self._pty_master = master
                self.process = subprocess.Popen(self.cmd, stdin=slave, stdout=slave, stderr=slave, env=env)
                os.close(slave)
                buf = b''
                while True:
                    if self._stop_requested or self.isInterruptionRequested():
                        break
                    try:
                        r, _, _ = select.select([master], [], [], 0.2)
                        if not r:
                            continue
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
                        # Decoded with utf-8 (errors='replace') above; emit directly.
                        self.line_ready.emit(decoded + '\n')
                if buf:
                    try:
                        decoded = buf.decode('utf-8', errors='replace')
                    except Exception:
                        decoded = buf.decode('latin-1', errors='replace')
                    # Decoded with utf-8 (errors='replace') above; emit directly.
                    self.line_ready.emit(decoded)
                try:
                    os.close(master)
                except Exception:
                    pass
                self._pty_master = None
                if self.process:
                    try:
                        self.process.wait(timeout=0.5)
                    except Exception:
                        try:
                            self.process.kill()
                        except Exception:
                            pass
            finally:
                self.finished.emit()
            return

        # Fallback: use PIPE and text mode
        stdin_pipe = subprocess.PIPE if self.input_text else None
        try:
            # On Windows, force UTF-8 decoding to avoid locale 'charmap' errors when
            # reading binary output from adb/pidcat which may contain emojis or
            # other non-CP1252 characters. Use errors='replace' to avoid exceptions.
            if os.name == 'nt':
                self.process = subprocess.Popen(self.cmd, stdin=stdin_pipe, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', env=env, bufsize=1)
            else:
                self.process = subprocess.Popen(self.cmd, stdin=stdin_pipe, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, bufsize=1)
            if self.input_text and self.process.stdin:
                try:
                    self.process.stdin.write(self.input_text + '\n')
                    self.process.stdin.flush()
                except Exception:
                    pass
            if self.process.stdout:
                for line in iter(self.process.stdout.readline, ''):
                    if self._stop_requested or self.isInterruptionRequested():
                        break
                    # Emit lines directly; encoding configured on Popen ensures
                    # emojis and special characters are preserved or replaced safely.
                    self.line_ready.emit(line)
            if self.process:
                try:
                    self.process.wait(timeout=0.5)
                except Exception:
                    try:
                        self.process.kill()
                    except Exception:
                        pass
        finally:
            self.finished.emit()
