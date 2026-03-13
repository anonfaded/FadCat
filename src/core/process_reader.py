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

    def stop(self):
        # Terminate the child process and close PTY to break read loop
        self._stop_requested = True
        try:
            self.requestInterruption()
        except Exception:
            pass
        if self.process:
            try:
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
        """Run pidcat.py directly via exec() to avoid subprocess re-launching FadCat app.
        
        This is called in bundled mode to execute pidcat code directly without subprocess,
        which would cause sys.executable (the FadCat app binary) to be re-launched.
        
        Args:
            pidcat_path: Path to pidcat.py script
            pidcat_args: List of arguments to pass to pidcat (e.g., ['-s', 'device', 'package'])
        
        Edge cases handled:
        - pidcat.py not found in bundle
        - Import errors due to missing modules
        - Interrupted execution (Ctrl+C)
        - Missing command-line arguments (set sys.argv)
        """
        import sys as _sys
        import os
        import platform
        from pathlib import Path
        
        pidcat_file = Path(pidcat_path)
        
        # Edge case 1: Check if file exists
        if not pidcat_file.exists():
            self.line_ready.emit(f"❌ Error: pidcat script not found at {pidcat_path}\n")
            self.line_ready.emit(f"   Expected location: {pidcat_file}\n")
            self.line_ready.emit(f"   sys._MEIPASS: {getattr(_sys, '_MEIPASS', 'N/A')}\n")
            self.line_ready.emit(f"   sys.executable: {_sys.executable}\n")
            self.finished.emit()
            return
        
        # Determine bundled ADB path
        system = platform.system()
        if getattr(_sys, '_MEIPASS', None):
            # Running as bundled app (PyInstaller)
            base_path = Path(_sys._MEIPASS) / "platform-tools" / system.lower()
        else:
            # Fallback to macOS default for testing
            base_path = Path(_sys.executable).parent.parent / "Resources" / "platform-tools" / system.lower()
        
        adb_binary = "adb.exe" if system == "Windows" else "adb"
        bundled_adb_path = str(base_path / adb_binary)
        
        # Save original sys.argv, sys.frozen, and environment to restore later
        original_argv = _sys.argv
        original_frozen = getattr(_sys, 'frozen', False)
        original_adb_override = os.environ.get('FADCAT_ADB_PATH', None)
        
        try:
            # Set sys.argv to pidcat's arguments so argparse works correctly
            # Format: ['pidcat.py', '-s', 'device', 'package', ...]
            _sys.argv = [str(pidcat_file)] + (pidcat_args or [])
            
            # Ensure sys.frozen is True
            _sys.frozen = True
            
            # Set environment variable to override ADB path
            os.environ['FADCAT_ADB_PATH'] = bundled_adb_path
            
            with open(pidcat_path, 'r') as f:
                pidcat_code = f.read()
            
            # Create a namespace for pidcat execution with custom print and input that emits signals
            def _safe_input(prompt=""):
                """Fallback input() for when stdin is not available in exec mode."""
                self._emit_print(prompt, end="")
                # In exec mode, we can't read from stdin, so raise EOFError to trigger pidcat's error handling
                raise EOFError("No stdin available in bundled exec mode")
            
            namespace = {
                '__name__': '__main__',
                '__file__': pidcat_path,
                '_process_reader': self,
                '_original_print': print,
                # Override print to emit lines via the signal
                'print': self._emit_print,
                # Override input to handle missing stdin in exec mode
                'input': _safe_input,
                # Make sys.frozen available in the namespace
                'sys': _sys,
            }
            
            # Execute pidcat code
            exec(compile(pidcat_code, pidcat_path, 'exec'), namespace)
        except KeyboardInterrupt:
            self.line_ready.emit("--- FadCat stopped. ---\n")
        except FileNotFoundError as e:
            self.line_ready.emit(f"❌ Error: File not found: {e}\n")
        except ImportError as e:
            self.line_ready.emit(f"❌ Import Error: {e}\n")
            self.line_ready.emit("   Make sure all dependencies are bundled in the app.\n")
        except SyntaxError as e:
            self.line_ready.emit(f"❌ Syntax Error in pidcat.py: {e}\n")
        except Exception as e:
            import traceback
            self.line_ready.emit(f"❌ Error running pidcat: {e}\n")
            self.line_ready.emit("--- Traceback ---\n")
            self.line_ready.emit(traceback.format_exc())
        finally:
            # Restore original sys.argv, sys.frozen, and environment variable
            _sys.argv = original_argv
            _sys.frozen = original_frozen
            if original_adb_override is None:
                os.environ.pop('FADCAT_ADB_PATH', None)
            else:
                os.environ['FADCAT_ADB_PATH'] = original_adb_override
            self.finished.emit()
    
    def _emit_print(self, *args, **kwargs):
        """Custom print function that emits lines via signal instead of to stdout."""
        end = kwargs.get('end', '\n')
        sep = kwargs.get('sep', ' ')
        line = sep.join(str(arg) for arg in args) + end
        self.line_ready.emit(line)

    def run(self):
        env = dict(self.env)
        env.setdefault('PYTHONUNBUFFERED', '1')
        # Encourage color output
        env.setdefault('TERM', 'xterm-256color')
        env.setdefault('FORCE_COLOR', '1')
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
