import os
import sys
import time
import signal
import re
from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QLineEdit, QTextEdit, QComboBox, QMessageBox, QCheckBox
)

from src.utils.adb_utils import get_adb_devices
from src.core.pidcat_runner import get_pidcat_path, DEFAULT_PACKAGE
from src.core.process_reader import ProcessReader

# Precompiled regexes
SGR_RE = re.compile(r'\x1b\[(?P<code>[0-9;]*)m')
ESC_PRESENT = re.compile(r'\x1b\[')

class LogcatGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('FadCat - Android Logcat Assistant')
        self.resize(1000, 700)
        self.setStyleSheet('background:#141414; color:#e6e6e6;')

        # widgets
        self.device_cb = QComboBox()
        self.refresh_btn = QPushButton('Refresh')
        self.package_edit = QLineEdit(DEFAULT_PACKAGE)
        self.status_label = QLabel('Ready')

        self.start_btn = QPushButton('Start Logcat')
        self.stop_btn = QPushButton('Stop Logcat')
        self.stop_btn.setEnabled(False)
        self.clear_btn = QPushButton('Clear Logs')
        self.copy_btn = QPushButton('Copy Logs')

        # search widgets
        self.search_edit = QLineEdit()
        self.search_btn = QPushButton('Search')
        self.case_checkbox = QCheckBox('Case-insensitive')
        self.case_checkbox.setChecked(False)
        self.grep_mode_checkbox = QCheckBox('Grep Mode')
        self.grep_mode_checkbox.setChecked(False)
        self.prev_search_btn = QPushButton('Prev')
        self.next_search_btn = QPushButton('Next')
        self.search_count_label = QLabel('0/0')
        self.clear_search_btn = QPushButton('Clear Highlight')
        
        # auto-scroll checkbox
        self.auto_scroll_checkbox = QCheckBox('Auto-scroll')
        self.auto_scroll_checkbox.setChecked(True)

        # allow Enter in the search box to trigger the search
        try:
            self.search_edit.returnPressed.connect(self.search_logs)
        except Exception:
            pass

        # compact button styling
        btns = (self.start_btn, self.stop_btn, self.clear_btn, self.copy_btn,
                self.search_btn, self.prev_search_btn, self.next_search_btn)
        for b in btns:
            try:
                b.setFixedHeight(28)
                b.setStyleSheet('font-size:12px; padding:4px 8px;')
                b.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
            except Exception:
                pass

        # set icons from the current QApplication style where possible
        try:
            style = QApplication.style()
            if style:
                try:
                    self.start_btn.setIcon(style.standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaPlay))
                except Exception:
                    pass
                try:
                    self.stop_btn.setIcon(style.standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaStop))
                except Exception:
                    pass
                try:
                    self.clear_btn.setIcon(style.standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogResetButton))
                except Exception:
                    pass
                try:
                    self.copy_btn.setIcon(style.standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogSaveButton))
                except Exception:
                    pass
                try:
                    self.prev_search_btn.setIcon(style.standardIcon(QtWidgets.QStyle.StandardPixmap.SP_ArrowBack))
                except Exception:
                    pass
                try:
                    self.next_search_btn.setIcon(style.standardIcon(QtWidgets.QStyle.StandardPixmap.SP_ArrowForward))
                except Exception:
                    pass
        except Exception:
            pass

        # input and checkbox contrast adjustments
        try:
            self.search_edit.setStyleSheet('background:#181818; color:#e6e6e6; border:1px solid #333; padding:4px;')
            self.package_edit.setStyleSheet('background:#181818; color:#e6e6e6; border:1px solid #333; padding:4px;')
            self.device_cb.setStyleSheet('background:#181818; color:#e6e6e6; border:1px solid #333; padding:2px;')
            # Better checkbox styling for visibility
            checkbox_style = '''
                QCheckBox {
                    color: #e6e6e6;
                    font-weight: bold;
                    spacing: 8px;
                }
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                }
                QCheckBox::indicator:unchecked {
                    background-color: #333;
                    border: 2px solid #666;
                    border-radius: 3px;
                }
                QCheckBox::indicator:checked {
                    background-color: #2ecc71;
                    border: 2px solid #27ae60;
                    border-radius: 3px;
                }
                QCheckBox::indicator:unchecked:hover {
                    background-color: #404040;
                    border: 2px solid #777;
                }
                QCheckBox::indicator:checked:hover {
                    background-color: #3fd986;
                    border: 2px solid #2ecc71;
                }
            '''
            self.case_checkbox.setStyleSheet(checkbox_style)
            self.grep_mode_checkbox.setStyleSheet(checkbox_style)
            self.auto_scroll_checkbox.setStyleSheet(checkbox_style)
        except Exception:
            pass

        # log display
        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)
        self.log_widget.setStyleSheet('background:#0f0f0f; color:#e6e6e6; font-family:monospace;')

        # layout
        header = QHBoxLayout()
        header.addWidget(QLabel('Device:'))
        header.addWidget(self.device_cb)
        header.addWidget(self.refresh_btn)
        header.addWidget(QLabel('Package:'))
        header.addWidget(self.package_edit)
        header.addWidget(self.status_label)

        controls = QHBoxLayout()
        controls.addWidget(self.start_btn)
        controls.addWidget(self.stop_btn)
        controls.addWidget(self.clear_btn)
        controls.addWidget(self.copy_btn)

        search = QHBoxLayout()
        search.addWidget(QLabel('Search:'))
        search.addWidget(self.search_edit)
        search.addWidget(self.case_checkbox)
        search.addWidget(self.grep_mode_checkbox)
        search.addWidget(self.search_btn)
        search.addWidget(self.prev_search_btn)
        search.addWidget(self.next_search_btn)
        search.addWidget(self.search_count_label)
        search.addWidget(self.clear_search_btn)
        search.addWidget(self.auto_scroll_checkbox)

        # small shortcuts hint and wrap toggle
        self.shortcuts_label = QLabel('Shortcuts: Start Ctrl+R • Stop Ctrl+S • Find Ctrl+F • Next F3 • Prev Shift+F3')
        self.shortcuts_label.setStyleSheet('font-size:11px; color:#9aa0a6;')
        self.wrap_checkbox = QCheckBox('Wrap lines')
        self.wrap_checkbox.setChecked(True)
        try:
            self.wrap_checkbox.setStyleSheet('color:#d0d4d8;')
        except Exception:
            pass

        main = QVBoxLayout()
        main.addLayout(header)
        main.addLayout(controls)
        main.addLayout(search)
        # add shortcuts hint
        hints = QHBoxLayout()
        hints.addWidget(self.shortcuts_label)
        hints.addWidget(self.wrap_checkbox)
        hints.addStretch()
        main.addLayout(hints)
        main.addWidget(self.log_widget)
        self.setLayout(main)

        # signals
        self.refresh_btn.clicked.connect(self.refresh_devices)
        self.start_btn.clicked.connect(self.start_logcat)
        self.stop_btn.clicked.connect(self.stop_logcat)
        self.clear_btn.clicked.connect(self.clear_logs)
        self.copy_btn.clicked.connect(self.copy_logs)
        self.search_btn.clicked.connect(self.search_logs)
        self.search_edit.textChanged.connect(self.on_search_text_changed)
        self.case_checkbox.stateChanged.connect(self.on_search_text_changed)
        self.grep_mode_checkbox.stateChanged.connect(self.on_grep_mode_changed)
        self.auto_scroll_checkbox.stateChanged.connect(self.on_auto_scroll_toggled)
        self.prev_search_btn.clicked.connect(self.navigate_prev)
        self.next_search_btn.clicked.connect(self.navigate_next)
        self.clear_search_btn.clicked.connect(self.clear_search)

        # keyboard shortcuts
        try:
            QtGui.QShortcut(QtGui.QKeySequence('Ctrl+R'), self).activated.connect(self.start_logcat)
            QtGui.QShortcut(QtGui.QKeySequence('Ctrl+S'), self).activated.connect(self.stop_logcat)
            QtGui.QShortcut(QtGui.QKeySequence('F3'), self).activated.connect(self.navigate_next)
            QtGui.QShortcut(QtGui.QKeySequence('Shift+F3'), self).activated.connect(self.navigate_prev)
            QtGui.QShortcut(QtGui.QKeySequence('Ctrl+F'), self).activated.connect(lambda: self.search_edit.setFocus())
            # additional shortcuts: clear and copy
            QtGui.QShortcut(QtGui.QKeySequence('Ctrl+L'), self).activated.connect(self.clear_logs)
            QtGui.QShortcut(QtGui.QKeySequence('Ctrl+Shift+C'), self).activated.connect(self.copy_logs)
        except Exception:
            pass

        # wire wrap toggle and default wrap behavior
        try:
            self.wrap_checkbox.toggled.connect(self.toggle_wrap)
            self.log_widget.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.WidgetWidth)
            self.log_widget.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        except Exception:
            pass

        # state
        self.reader = None
        self.devices = []
        self._last_received = None
        # search state
        self.search_matches = []  # list of (start, length)
        self.current_search_index = -1
        # auto-scroll state - now controlled by checkbox only
        self.search_debounce_timer = None
        # grep mode state
        self.grep_mode_enabled = False
        self.all_logs_text = ""  # keep original logs for grep mode
        # color the start/stop buttons for clarity (placed here after styles are defined)
        self.start_btn.setStyleSheet('background:#2ecc71; color:#012a0f; font-weight:bold;')
        self.stop_btn.setStyleSheet('background:#e74c3c; color:#2b0000; font-weight:bold;')

        self.refresh_devices()
        try:
            self.install_sigint_handler()
        except Exception:
            pass

    def toggle_wrap(self, checked: bool):
        try:
            if checked:
                self.log_widget.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.WidgetWidth)
                self.log_widget.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            else:
                self.log_widget.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.NoWrap)
                self.log_widget.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        except Exception:
            pass

    def scroll_to_bottom(self):
        """Auto-scroll to the bottom if auto-scroll is enabled."""
        if self.auto_scroll_checkbox.isChecked():
            try:
                scrollbar = self.log_widget.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
            except Exception:
                pass

    def on_auto_scroll_toggled(self):
        """Handle auto-scroll checkbox toggle."""
        # If turning on auto-scroll, immediately scroll to bottom
        if self.auto_scroll_checkbox.isChecked():
            self.scroll_to_bottom()

    def on_search_text_changed(self):
        """Real-time search as user types."""
        # If grep mode is enabled, apply filtering immediately
        if self.grep_mode_enabled:
            # For grep mode, apply immediately without debounce
            self.apply_grep_mode()
            return
        
        # For normal search, use a debounce timer to avoid too many updates
        if self.search_debounce_timer:
            try:
                self.search_debounce_timer.stop()
            except Exception:
                pass
        
        self.search_debounce_timer = QtCore.QTimer()
        self.search_debounce_timer.setSingleShot(True)
        self.search_debounce_timer.timeout.connect(self.search_logs)
        self.search_debounce_timer.start(300)  # 300ms debounce

    def on_grep_mode_changed(self):
        """Toggle grep mode on/off and update display."""
        self.grep_mode_enabled = self.grep_mode_checkbox.isChecked()
        # Re-run search to apply grep filtering if needed
        if self.grep_mode_enabled:
            self.apply_grep_mode()
        else:
            # Restore all logs
            if self.all_logs_text:
                self.log_widget.clear()
                self.log_widget.insertPlainText(self.all_logs_text)
                # Re-run search with highlighting
                self.search_logs()

    def apply_grep_mode(self):
        """Filter logs to show only matching lines while preserving colors."""
        query = self.search_edit.text()
        if not query:
            return
        
        doc_text = self.all_logs_text if self.all_logs_text else self.log_widget.toPlainText()
        lines = doc_text.split('\n')
        
        case_insensitive = self.case_checkbox.isChecked()
        if case_insensitive:
            needle = query.lower()
        else:
            needle = query
        
        filtered_lines = []
        for line in lines:
            # Check against clean text (without ANSI codes)
            clean_line = SGR_RE.sub('', line)
            check_line = clean_line.lower() if case_insensitive else clean_line
            if needle in check_line:
                filtered_lines.append(line)
        
        # Update display with filtered lines, preserving colors
        self.log_widget.clear()
        for line in filtered_lines:
            if line:  # Skip empty lines
                if ESC_PRESENT.search(line):
                    try:
                        self.insert_colored_line(line)
                    except Exception:
                        self.append_html(self.color_line(line))
                else:
                    self.log_widget.append(line.rstrip('\n'))

    def append_html(self, html: str):
        cursor = self.log_widget.textCursor()
        try:
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
            self.log_widget.setTextCursor(cursor)
        except Exception:
            pass
        self.log_widget.insertHtml(html)
        try:
            cursor = self.log_widget.textCursor()
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
            self.log_widget.setTextCursor(cursor)
        except Exception:
            pass

    def insert_colored_line(self, line: str):
        """Insert a line into the QTextEdit using QTextCharFormat per ANSI segment.
        This preserves exact spacing and lets us use Qt colors (better contrast).
        """
        # high-contrast palette (match color_line)
        FG = {
            30: '#6b6f75', 31: '#ff5555', 32: '#50fa7b', 33: '#f1fa8c',
            34: '#6272a4', 35: '#ff79c6', 36: '#8be9fd', 37: '#e6e6e6',
            90: '#5a5f66', 91: '#ff6e6e', 92: '#69ff94', 93: '#ffffa5',
            94: '#caa9ff', 95: '#ff92df', 96: '#a4ffff', 97: '#ffffff'
        }

        # Determine a single line color (prefer the first color code seen)
        overall_color = None
        overall_bold = False
        for m in SGR_RE.finditer(line):
            codes = m.group('code') or '0'
            for c in codes.split(';'):
                try:
                    ci = int(c)
                except Exception:
                    continue
                if ci == 0:
                    # reset - stop considering prior colors
                    if overall_color is None:
                        overall_bold = False
                elif ci == 1:
                    overall_bold = True
                elif 30 <= ci <= 37 or 90 <= ci <= 97:
                    if overall_color is None:
                        overall_color = FG.get(ci)

        # Strip ANSI sequences to get clean text while preserving spacing/newlines
        try:
            clean = SGR_RE.sub('', line)
        except Exception:
            clean = line

        cursor = self.log_widget.textCursor()
        try:
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
            self.log_widget.setTextCursor(cursor)
        except Exception:
            pass

        fmt = QtGui.QTextCharFormat()
        fmt.setFontFamily('monospace')
        if overall_color:
            try:
                fmt.setForeground(QtGui.QBrush(QtGui.QColor(overall_color)))
            except Exception:
                pass
        if overall_bold:
            try:
                fmt.setFontWeight(QtGui.QFont.Weight.Bold)
            except Exception:
                pass

        # insert the full cleaned line as a single formatted chunk
        # preserve trailing newline behavior similar to append
        text_to_insert = clean
        # remove a single trailing newline to avoid double-spacing when using append elsewhere
        if text_to_insert.endswith('\n'):
            text_to_insert = text_to_insert.rstrip('\n') + '\n'
        cursor.insertText(text_to_insert, fmt)
        try:
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
            self.log_widget.setTextCursor(cursor)
        except Exception:
            pass

    def refresh_devices(self):
        devices = get_adb_devices()
        self.devices = devices
        self.device_cb.clear()
        if devices:
            self.device_cb.addItems(devices)
            self.start_btn.setEnabled(True)
            self.status_label.setText(f'{len(devices)} device(s)')
        else:
            self.start_btn.setEnabled(False)
            self.status_label.setText('No adb devices')

    def color_line(self, line: str) -> str:
        # Legacy HTML converter kept for compatibility; prefer insert_colored_line for exact spacing.
        FG = {
            # avoid pure black for readability on dark theme
            30: '#6b6f75', 31: '#ff5555', 32: '#50fa7b', 33: '#f1fa8c',
            34: '#6272a4', 35: '#ff79c6', 36: '#8be9fd', 37: '#e6e6e6',
            90: '#5a5f66', 91: '#ff6e6e', 92: '#69ff94', 93: '#ffffa5',
            94: '#caa9ff', 95: '#ff92df', 96: '#a4ffff', 97: '#ffffff'
        }

        # Find the first color/bold SGR and apply it to the whole line
        overall_color = None
        overall_bold = False
        for m in SGR_RE.finditer(line):
            codes = m.group('code') or '0'
            for c in codes.split(';'):
                try:
                    ci = int(c)
                except Exception:
                    continue
                if ci == 0:
                    if overall_color is None:
                        overall_bold = False
                elif ci == 1:
                    overall_bold = True
                elif 30 <= ci <= 37 or 90 <= ci <= 97:
                    if overall_color is None:
                        overall_color = FG.get(ci)

        try:
            clean = SGR_RE.sub('', line)
        except Exception:
            clean = line

        esc = clean.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        style = []
        if overall_color:
            style.append(f'color:{overall_color}')
        if overall_bold:
            style.append('font-weight:bold')
        if style:
            return f"<pre style='white-space:pre; margin:0; font-family:monospace; color:#e6e6e6;'><span style=\"{';'.join(style)}\">{esc}</span></pre>"
        return f"<pre style='white-space:pre; margin:0; font-family:monospace; color:#e6e6e6;'>{esc}</pre>"

    def install_sigint_handler(self):
        def _sigint(signum, frame):
            try:
                QtCore.QTimer.singleShot(0, self._on_sigint_requested)
            except Exception:
                pass
        signal.signal(signal.SIGINT, _sigint)

    def _on_sigint_requested(self):
        ans = QMessageBox.question(self, 'Terminate', 'Ctrl+C detected in terminal. Quit the GUI?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ans == QMessageBox.StandardButton.Yes:
            try:
                if self.reader and getattr(self.reader, 'process', None):
                    proc = self.reader.process
                    if proc and getattr(proc, 'terminate', None):
                        proc.terminate()
            except Exception:
                pass
            QApplication.quit()

    def start_logcat(self):
        package = self.package_edit.text().strip() or DEFAULT_PACKAGE
        device = self.device_cb.currentText().strip()
        env = os.environ.copy()
        input_text = None
        if device and self.devices and len(self.devices) > 1:
            try:
                idx = self.devices.index(device) + 1
                input_text = str(idx)
            except ValueError:
                input_text = None
        if device:
            env['ANDROID_SERIAL'] = device

        self.status_label.setText(f'Running on {device}')
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        pidcat_path = get_pidcat_path()

        # prefer passing device explicitly to pidcat to avoid interactive prompts
        # Use the short -s DEVICE flag (pidcat uses -s for device serial) and
        # pass the package name as a positional argument.
        if device:
            cmd = [sys.executable, pidcat_path, '-s', device, package]
        else:
            cmd = [sys.executable, pidcat_path, package]
        env['PYTHONUNBUFFERED'] = '1'

        self.reader = ProcessReader(cmd, env, input_text=input_text)
        self.reader.line_ready.connect(self.handle_line)
        self.reader.finished.connect(self.on_reader_finished)
        self.reader.start()

    def on_reader_finished(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_label.setText('Stopped')

    def handle_line(self, ln: str):
        # Filter out system noise logs
        # - gralloc4: hardware graphics allocation spam
        # - register/unregister: GPU memory allocation tracking
        # - flushMediametrics: MediaCodec debug noise
        ln_lower = ln.lower()
        if any(pattern in ln_lower for pattern in ['gralloc4', 'register: id=', 'unregister: id=', 'flushmediametrics']):
            return
        
        # If the line contains ANSI escapes, insert colored segments using QTextCursor for exact fidelity;
        # otherwise append plain text (this matches the old raw checkbox behavior).
        
        # Store in all_logs_text for grep mode and filtering
        self.all_logs_text += ln if ln.endswith('\n') else ln + '\n'
        
        # If grep mode is enabled, don't display unless it matches
        if self.grep_mode_enabled:
            query = self.search_edit.text()
            if query:
                case_insensitive = self.case_checkbox.isChecked()
                # Strip ANSI codes to check against clean text
                clean_ln = SGR_RE.sub('', ln)
                check_ln = clean_ln.lower() if case_insensitive else clean_ln
                needle = query.lower() if case_insensitive else query
                if needle not in check_ln:
                    self._last_received = time.time()
                    return  # Don't display non-matching lines in grep mode
        
        if ESC_PRESENT.search(ln):
            try:
                self.insert_colored_line(ln)
            except Exception:
                # fallback to HTML append if anything goes wrong
                self.append_html(self.color_line(ln))
        else:
            self.log_widget.append(ln.rstrip('\n'))
        
        self._last_received = time.time()
        # Auto-scroll to bottom only if auto-scroll is enabled AND we're at the bottom
        if self.auto_scroll_checkbox.isChecked():
            self.scroll_to_bottom()

    def stop_logcat(self):
        if self.reader and getattr(self.reader, 'process', None):
            proc = self.reader.process
            try:
                if proc and getattr(proc, 'terminate', None):
                    proc.terminate()
            except Exception:
                pass
        self.status_label.setText('Stopped')

    def clear_logs(self):
        self.log_widget.clear()
        self.all_logs_text = ""
        self.clear_search()

    def copy_logs(self):
        clip = QApplication.clipboard() if QApplication.instance() else None
        if clip:
            clip.setText(self.log_widget.toPlainText())
            QMessageBox.information(self, 'Copied', 'Logs copied to clipboard!')
        else:
            QMessageBox.information(self, 'Copied', 'Could not access clipboard.')

    def search_logs(self):
        query = self.search_edit.text()
        if not query:
            self.clear_search()
            return
        
        # If grep mode is on, apply filtering instead of highlighting
        if self.grep_mode_enabled:
            self.apply_grep_mode()
            return
        
        # Standard search with highlighting
        doc_text = self.log_widget.toPlainText()
        self.search_matches = []
        qlen = len(query)
        pos = 0
        if self.case_checkbox.isChecked():
            hay = doc_text.lower()
            needle = query.lower()
        else:
            hay = doc_text
            needle = query
        while True:
            idx = hay.find(needle, pos)
            if idx == -1:
                break
            self.search_matches.append((idx, qlen))
            pos = idx + max(1, qlen)

        self.current_search_index = 0 if self.search_matches else -1
        self.update_search_selection()

    def clear_search(self):
        self.search_matches = []
        self.current_search_index = -1
        self.search_count_label.setText('0/0')
        self.log_widget.setExtraSelections([])

    def navigate_next(self):
        if not self.search_matches:
            return
        self.current_search_index = (self.current_search_index + 1) % len(self.search_matches)
        self.update_search_selection()

    def navigate_prev(self):
        if not self.search_matches:
            return
        self.current_search_index = (self.current_search_index - 1) % len(self.search_matches)
        self.update_search_selection()

    def update_search_selection(self):
        # create ExtraSelections for all matches and a focused one for the current index
        extras = []
        doc = self.log_widget.document()
        for i, (start, length) in enumerate(self.search_matches):
            sel = QtWidgets.QTextEdit.ExtraSelection()
            cursor = self.log_widget.textCursor()
            cursor.setPosition(start)
            cursor.setPosition(start + length, QtGui.QTextCursor.MoveMode.KeepAnchor)
            sel.cursor = cursor
            fmt = QtGui.QTextCharFormat()
            if i == self.current_search_index:
                fmt.setBackground(QtGui.QBrush(QtGui.QColor('#ffd54f')))  # active highlight
                fmt.setForeground(QtGui.QBrush(QtGui.QColor('#000000')))
            else:
                fmt.setBackground(QtGui.QBrush(QtGui.QColor('#6e6e6e')))
            sel.format = fmt
            extras.append(sel)

        self.log_widget.setExtraSelections(extras)
        if self.current_search_index != -1 and self.search_matches:
            s, l = self.search_matches[self.current_search_index]
            cursor = self.log_widget.textCursor()
            cursor.setPosition(s)
            cursor.setPosition(s + l, QtGui.QTextCursor.MoveMode.KeepAnchor)
            self.log_widget.setTextCursor(cursor)
        # update label
        total = len(self.search_matches)
        cur = (self.current_search_index + 1) if self.current_search_index != -1 else 0
        self.search_count_label.setText(f'{cur}/{total}')
