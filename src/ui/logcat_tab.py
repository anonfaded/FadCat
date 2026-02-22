"""
FadCat — LogcatTab
"""
import os
import re
import sys

from PyQt6 import QtWidgets, QtGui, QtCore
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QComboBox, QMessageBox, QFrame,
    QFileDialog, QSizePolicy, QApplication
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

from src.utils.adb_utils import get_adb_devices
from src.core.pidcat_runner import get_pidcat_path
from src.core.process_reader import ProcessReader
from src.core.settings import SettingsManager
from src.ui.icons import (
    icon_play, icon_stop, icon_refresh, icon_clear,
    icon_copy, icon_save, icon_up, icon_down, icon_search,
    icon_filter, icon_device, icon_package, icon_close
)

SGR_RE      = re.compile(r'\x1b\[(?P<code>[0-9;]*)m')
ESC_PRESENT = re.compile(r'\x1b\[')


class LogcatTab(QWidget):
    """One logcat session — lives inside a QTabWidget tab."""

    status_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = SettingsManager.load()
        self._setup_ui()
        self._setup_connections()
        self._setup_state()
        self.refresh_devices()

    # ── UI construction ──────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_control_bar())
        root.addWidget(self._build_search_bar())
        root.addWidget(self._build_log_area())

    def _build_control_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("controlBar")
        bar.setFixedHeight(46)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(6)

        device_lbl = QLabel("Device")
        device_lbl.setProperty("muted", True)
        self.device_cb = QComboBox()
        self.device_cb.setMinimumWidth(160)
        self.device_cb.setMaximumWidth(260)
        self.device_cb.setToolTip("Connected ADB device")

        self.refresh_btn = QPushButton()
        self.refresh_btn.setIcon(icon_refresh())
        self.refresh_btn.setToolTip("Refresh devices")
        self.refresh_btn.setProperty("role", "icon")
        self.refresh_btn.setFixedSize(30, 30)

        pkg_lbl = QLabel("Package")
        pkg_lbl.setProperty("muted", True)
        self.package_cb = QComboBox()
        self.package_cb.setEditable(True)
        self.package_cb.setMinimumWidth(220)
        self.package_cb.setMaximumWidth(360)
        self.package_cb.addItems(self.settings.get("packages", []))
        self.package_cb.setCurrentText(self.settings.get("default_package", ""))
        self.package_cb.setToolTip("Target package (e.g. com.example.app)")
        if self.package_cb.lineEdit():
            self.package_cb.lineEdit().setPlaceholderText("com.example.app")

        lay.addWidget(device_lbl)
        lay.addWidget(self.device_cb)
        lay.addWidget(self.refresh_btn)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Plain)
        sep.setFixedHeight(20)
        lay.addWidget(sep)

        lay.addWidget(pkg_lbl)
        lay.addWidget(self.package_cb)
        lay.addStretch()

        self.start_btn = QPushButton("Start")
        self.start_btn.setIcon(icon_play())
        self.start_btn.setProperty("role", "start")
        self.start_btn.setToolTip("Start logcat")

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setIcon(icon_stop())
        self.stop_btn.setProperty("role", "stop")
        self.stop_btn.setToolTip("Stop logcat")
        self.stop_btn.setEnabled(False)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.VLine)
        sep2.setFrameShadow(QFrame.Shadow.Plain)
        sep2.setFixedHeight(20)

        self.clear_btn = QPushButton()
        self.clear_btn.setIcon(icon_clear())
        self.clear_btn.setToolTip("Clear logs  Ctrl+L")
        self.clear_btn.setProperty("role", "icon")
        self.clear_btn.setFixedSize(30, 30)

        self.copy_btn = QPushButton()
        self.copy_btn.setIcon(icon_copy())
        self.copy_btn.setToolTip("Copy all logs to clipboard")
        self.copy_btn.setProperty("role", "icon")
        self.copy_btn.setFixedSize(30, 30)

        self.save_btn = QPushButton()
        self.save_btn.setIcon(icon_save())
        self.save_btn.setToolTip("Save logs to file")
        self.save_btn.setProperty("role", "icon")
        self.save_btn.setFixedSize(30, 30)

        lay.addWidget(self.start_btn)
        lay.addWidget(self.stop_btn)
        lay.addWidget(sep2)
        lay.addWidget(self.clear_btn)
        lay.addWidget(self.copy_btn)
        lay.addWidget(self.save_btn)
        return bar

    def _build_search_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("searchBar")
        bar.setFixedHeight(38)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(4)

        self._search_icon_lbl = QLabel()
        self._search_icon_lbl.setPixmap(icon_search().pixmap(14, 14))

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search\u2026")
        self.search_edit.setMinimumWidth(160)
        self.search_edit.setMaximumWidth(300)
        self.search_edit.setClearButtonEnabled(True)

        self.case_btn = QPushButton("Aa")
        self.case_btn.setToolTip("Case sensitive")
        self.case_btn.setCheckable(True)
        self.case_btn.setProperty("role", "toggle")
        self.case_btn.setFixedHeight(26)
        self.case_btn.setFixedWidth(32)

        self.grep_btn = QPushButton("Grep")
        self.grep_btn.setToolTip("Filter: show only matching lines")
        self.grep_btn.setCheckable(True)
        self.grep_btn.setProperty("role", "toggle")
        self.grep_btn.setFixedHeight(26)
        self.grep_btn.setFixedWidth(44)

        self.prev_btn = QPushButton()
        self.prev_btn.setIcon(icon_up())
        self.prev_btn.setProperty("role", "icon")
        self.prev_btn.setFixedSize(26, 26)
        self.prev_btn.setToolTip("Previous match")

        self.next_btn = QPushButton()
        self.next_btn.setIcon(icon_down())
        self.next_btn.setProperty("role", "icon")
        self.next_btn.setFixedSize(26, 26)
        self.next_btn.setToolTip("Next match")

        self.match_lbl = QLabel("0/0")
        self.match_lbl.setProperty("muted", True)
        self.match_lbl.setMinimumWidth(40)
        self.match_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        sep_v = QFrame()
        sep_v.setFrameShape(QFrame.Shape.VLine)
        sep_v.setFrameShadow(QFrame.Shadow.Plain)
        sep_v.setFixedHeight(18)

        self.auto_scroll_btn = QPushButton("Auto-scroll")
        self.auto_scroll_btn.setCheckable(True)
        self.auto_scroll_btn.setChecked(True)
        self.auto_scroll_btn.setProperty("role", "toggle")
        self.auto_scroll_btn.setFixedHeight(26)

        self.wrap_btn = QPushButton("Wrap")
        self.wrap_btn.setCheckable(True)
        self.wrap_btn.setChecked(True)
        self.wrap_btn.setProperty("role", "toggle")
        self.wrap_btn.setFixedHeight(26)
        self.wrap_btn.toggled.connect(self.toggle_wrap)

        lay.addWidget(self._search_icon_lbl)
        lay.addSpacing(2)
        lay.addWidget(self.search_edit)
        lay.addWidget(self.case_btn)
        lay.addWidget(self.grep_btn)
        lay.addWidget(self.prev_btn)
        lay.addWidget(self.next_btn)
        lay.addWidget(self.match_lbl)
        lay.addWidget(sep_v)
        lay.addWidget(self.auto_scroll_btn)
        lay.addWidget(self.wrap_btn)
        lay.addStretch()
        return bar

    def _build_log_area(self) -> QTextEdit:
        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)
        self.log_widget.setLineWrapMode(QtWidgets.QTextEdit.LineWrapMode.WidgetWidth)
        self.log_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        return self.log_widget

    # ── wiring ───────────────────────────────────────────────────────────────

    def _setup_connections(self):
        self.refresh_btn.clicked.connect(self.refresh_devices)
        self.start_btn.clicked.connect(self.start_logcat)
        self.stop_btn.clicked.connect(self.stop_logcat)
        self.clear_btn.clicked.connect(self.clear_logs)
        self.copy_btn.clicked.connect(self.copy_logs)
        self.save_btn.clicked.connect(self.save_logs)

        self.search_edit.textChanged.connect(self._on_search_changed)
        self.search_edit.returnPressed.connect(self.navigate_next)
        self.case_btn.toggled.connect(self._on_search_changed)
        self.grep_btn.toggled.connect(self._on_grep_toggled)
        self.auto_scroll_btn.toggled.connect(self._on_autoscroll_toggled)

        self.prev_btn.clicked.connect(self.navigate_prev)
        self.next_btn.clicked.connect(self.navigate_next)

    def _setup_state(self):
        self.reader = None
        self.devices = []
        self.search_matches = []
        self.current_match_idx = -1
        self._debounce = None
        self.all_logs_text = ""

    # ── public API ────────────────────────────────────────────────────────────

    def apply_settings(self, settings: dict):
        self.settings = settings
        current_pkg = self.package_cb.currentText()
        self.package_cb.blockSignals(True)
        self.package_cb.clear()
        self.package_cb.addItems(settings.get("packages", []))
        if current_pkg in settings.get("packages", []):
            self.package_cb.setCurrentText(current_pkg)
        else:
            self.package_cb.setCurrentText(settings.get("default_package", ""))
        self.package_cb.blockSignals(False)

    # ── device management ─────────────────────────────────────────────────────

    def refresh_devices(self):
        self.devices = get_adb_devices()
        self.device_cb.blockSignals(True)
        self.device_cb.clear()
        if self.devices:
            self.device_cb.addItems(self.devices)
            self.start_btn.setEnabled(True)
        else:
            self.device_cb.addItem("No devices")
            self.start_btn.setEnabled(False)
        self.device_cb.blockSignals(False)
        self.status_changed.emit()

    # ── logcat control ────────────────────────────────────────────────────────

    def start_logcat(self):
        package = self.package_cb.currentText().strip()
        device  = self.device_cb.currentText().strip()
        if not package or not self.devices:
            return

        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'
        if device and device != "No devices":
            env['ANDROID_SERIAL'] = device

        pidcat_path = get_pidcat_path()
        if device and device != "No devices":
            cmd = [sys.executable, pidcat_path, '-s', device, package]
        else:
            cmd = [sys.executable, pidcat_path, package]

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        self.reader = ProcessReader(cmd, env)
        self.reader.line_ready.connect(self._handle_line)
        self.reader.finished.connect(self._on_reader_finished)
        self.reader.start()
        self.status_changed.emit()

    def stop_logcat(self):
        if self.reader and getattr(self.reader, 'process', None):
            try:
                self.reader.process.terminate()
            except Exception:
                pass

    def _on_reader_finished(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.status_changed.emit()

    # ── log handling ──────────────────────────────────────────────────────────

    _NOISE = ('gralloc4', 'register: id=', 'unregister: id=', 'flushmediametrics')

    def _handle_line(self, ln: str):
        ln_lower = ln.lower()
        if any(p in ln_lower for p in self._NOISE):
            return

        self.all_logs_text += (ln if ln.endswith('\n') else ln + '\n')

        if self.grep_btn.isChecked():
            query = self.search_edit.text()
            if query and not self._line_matches(ln, query):
                return

        if ESC_PRESENT.search(ln):
            self._insert_colored(ln)
        else:
            self.log_widget.append(ln.rstrip('\n'))

        if self.auto_scroll_btn.isChecked():
            self._scroll_bottom()

    def _line_matches(self, line: str, query: str) -> bool:
        clean = SGR_RE.sub('', line)
        if self.case_btn.isChecked():
            return query in clean
        return query.lower() in clean.lower()

    def _insert_colored(self, line: str):
        FG = {
            30: '#6b6f75', 31: '#ff5555', 32: '#50fa7b', 33: '#f1fa8c',
            34: '#6272a4', 35: '#ff79c6', 36: '#8be9fd', 37: '#e6e6e6',
            90: '#5a5f66', 91: '#ff6e6e', 92: '#69ff94', 93: '#ffffa5',
            94: '#caa9ff', 95: '#ff92df', 96: '#a4ffff', 97: '#ffffff'
        }
        color, bold = None, False
        for m in SGR_RE.finditer(line):
            codes = m.group('code') or '0'
            for c in codes.split(';'):
                try:
                    ci = int(c)
                except ValueError:
                    continue
                if ci == 0:
                    if color is None:
                        bold = False
                elif ci == 1:
                    bold = True
                elif (30 <= ci <= 37) or (90 <= ci <= 97):
                    if color is None:
                        color = FG.get(ci)

        clean = SGR_RE.sub('', line)
        cursor = self.log_widget.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        fmt = QtGui.QTextCharFormat()
        if color:
            fmt.setForeground(QtGui.QBrush(QtGui.QColor(color)))
        if bold:
            fmt.setFontWeight(QtGui.QFont.Weight.Bold)
        text = clean.rstrip('\n') + '\n'
        cursor.insertText(text, fmt)
        self.log_widget.setTextCursor(cursor)

    # ── search ────────────────────────────────────────────────────────────────

    def _on_search_changed(self):
        if self.grep_btn.isChecked():
            self._apply_grep()
            return
        if self._debounce:
            self._debounce.stop()
        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self.search_logs)
        self._debounce.start(250)

    def _on_grep_toggled(self, checked: bool):
        if checked:
            self._apply_grep()
        else:
            self.log_widget.clear()
            if self.all_logs_text:
                for line in self.all_logs_text.splitlines():
                    if ESC_PRESENT.search(line):
                        self._insert_colored(line)
                    else:
                        self.log_widget.append(line)
            self.search_logs()

    def _apply_grep(self):
        query = self.search_edit.text()
        if not query:
            return
        doc = self.all_logs_text or self.log_widget.toPlainText()
        self.log_widget.clear()
        for line in doc.splitlines():
            if self._line_matches(line, query):
                if ESC_PRESENT.search(line):
                    self._insert_colored(line)
                else:
                    self.log_widget.append(line)

    def search_logs(self):
        query = self.search_edit.text()
        if not query:
            self._clear_search_highlights()
            return
        if self.grep_btn.isChecked():
            self._apply_grep()
            return

        hay = self.log_widget.toPlainText()
        self.search_matches = []
        qlen = len(query)
        pos  = 0
        if not self.case_btn.isChecked():
            needle, stack = query.lower(), hay.lower()
        else:
            needle, stack = query, hay
        while True:
            idx = stack.find(needle, pos)
            if idx == -1:
                break
            self.search_matches.append((idx, qlen))
            pos = idx + max(1, qlen)

        self.current_match_idx = 0 if self.search_matches else -1
        self._render_highlights()

    def navigate_next(self):
        if not self.search_matches:
            self.search_logs()
            return
        self.current_match_idx = (self.current_match_idx + 1) % len(self.search_matches)
        self._render_highlights()

    def navigate_prev(self):
        if not self.search_matches:
            return
        self.current_match_idx = (self.current_match_idx - 1) % len(self.search_matches)
        self._render_highlights()

    def _clear_search_highlights(self):
        self.search_matches = []
        self.current_match_idx = -1
        self.match_lbl.setText("0/0")
        self.log_widget.setExtraSelections([])

    def _render_highlights(self):
        extras = []
        for i, (start, length) in enumerate(self.search_matches):
            sel = QtWidgets.QTextEdit.ExtraSelection()
            cur = self.log_widget.textCursor()
            cur.setPosition(start)
            cur.setPosition(start + length, QtGui.QTextCursor.MoveMode.KeepAnchor)
            sel.cursor = cur
            fmt = QtGui.QTextCharFormat()
            if i == self.current_match_idx:
                fmt.setBackground(QtGui.QBrush(QtGui.QColor('#ffcc00')))
                fmt.setForeground(QtGui.QBrush(QtGui.QColor('#000000')))
            else:
                fmt.setBackground(QtGui.QBrush(QtGui.QColor('#4a4a2a')))
            sel.format = fmt
            extras.append(sel)

        self.log_widget.setExtraSelections(extras)

        if self.current_match_idx != -1 and self.search_matches:
            s, l = self.search_matches[self.current_match_idx]
            cur = self.log_widget.textCursor()
            cur.setPosition(s)
            cur.setPosition(s + l, QtGui.QTextCursor.MoveMode.KeepAnchor)
            self.log_widget.setTextCursor(cur)

        total = len(self.search_matches)
        cur_n = (self.current_match_idx + 1) if self.current_match_idx != -1 else 0
        self.match_lbl.setText(f"{cur_n}/{total}")

    # ── helpers ───────────────────────────────────────────────────────────────

    def _scroll_bottom(self):
        sb = self.log_widget.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_autoscroll_toggled(self, checked: bool):
        if checked:
            self._scroll_bottom()

    def toggle_wrap(self, checked: bool):
        mode = (QtWidgets.QTextEdit.LineWrapMode.WidgetWidth if checked
                else QtWidgets.QTextEdit.LineWrapMode.NoWrap)
        self.log_widget.setLineWrapMode(mode)

    # ── user actions ──────────────────────────────────────────────────────────

    def clear_logs(self):
        self.log_widget.clear()
        self.all_logs_text = ""
        self._clear_search_highlights()
        self.status_changed.emit()

    def copy_logs(self):
        clip = QApplication.clipboard()
        if clip:
            clip.setText(self.log_widget.toPlainText())

    def save_logs(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Logs", "fadcat.txt", "Text files (*.txt);;All files (*)"
        )
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(self.log_widget.toPlainText())
            except Exception as exc:
                QMessageBox.critical(self, "Save Failed", str(exc))

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self.stop_logcat()
        super().closeEvent(event)
