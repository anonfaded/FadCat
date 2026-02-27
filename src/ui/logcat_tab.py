"""LogcatTab — single device/package logcat session view."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QPoint
from PyQt6.QtGui import QTextCharFormat, QColor, QFont, QTextCursor, QFontDatabase, QPainter, QPolygon, QBrush
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QLabel, QComboBox, QPushButton, QLineEdit,
    QTextEdit, QFileDialog, QApplication, QSizePolicy,
)

from src.core.process_reader import ProcessReader
from src.utils.adb_utils import get_adb_devices
from src.ui import icons


# ── Custom ComboBox with proper dropdown arrow ────────────────────────────────
class CustomComboBox(QComboBox):
    """QComboBox with a proper Python-drawn dropdown arrow."""
    def paintEvent(self, event):
        super().paintEvent(event)
        # Draw custom dropdown arrow
        if self.isEnabled():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            # Calculate arrow position (right side of combobox) - use red accent color
            arrow_x = self.width() - 22
            arrow_y = (self.height() - 6) // 2
            # Draw downward triangle with red accent
            points = [
                QPoint(arrow_x, arrow_y),
                QPoint(arrow_x + 8, arrow_y),
                QPoint(arrow_x + 4, arrow_y + 6),
            ]
            painter.setBrush(QBrush(QColor("#E8302A")))  # Red accent
            painter.setPen(QColor("#E8302A"))
            painter.drawConvexPolygon(QPolygon(points))


# ── ANSI colour table ─────────────────────────────────────────────────────────
_ANSI_RESET = re.compile(r"\x1b\[([0-9;]*)m")

_FG = {
    30: "#3D3D3D", 31: "#E8302A", 32: "#3CB371", 33: "#E8A020",
    34: "#4A9FE8", 35: "#B05CBF", 36: "#3CB3B3", 37: "#E8E8E8",
    90: "#606060", 91: "#FF5F5F", 92: "#5FD87A", 93: "#FFD050",
    94: "#70B8FF", 95: "#D07AFF", 96: "#50D8D8", 97: "#FFFFFF",
}
_BG = {
    40: "#1A1A1A", 41: "#4A1010", 42: "#0E3820", 43: "#3A2800",
    44: "#0E2540", 45: "#2E1040", 46: "#0E2E2E", 47: "#3A3A3A",
}

_DEFAULT_FG = QColor("#E8E8E8")
_DEFAULT_BG = QColor("#141414")


def _parse_ansi(text: str) -> list[tuple[str, QColor, QColor, bool, bool]]:
    """Return list of (chunk, fg, bg, bold, italic)."""
    result: list[tuple[str, QColor, QColor, bool, bool]] = []
    fg = _DEFAULT_FG
    bg = _DEFAULT_BG
    bold = False
    italic = False
    pos = 0
    for m in _ANSI_RESET.finditer(text):
        if m.start() > pos:
            result.append((text[pos:m.start()], fg, bg, bold, italic))
        codes = [int(c) for c in m.group(1).split(";") if c.isdigit()]
        if not codes:
            codes = [0]
        for c in codes:
            if c == 0:
                fg, bg, bold, italic = _DEFAULT_FG, _DEFAULT_BG, False, False
            elif c == 1:
                bold = True
            elif c == 3:
                italic = True
            elif c in _FG:
                fg = QColor(_FG[c])
            elif c in _BG:
                bg = QColor(_BG[c])
        pos = m.end()
    if pos < len(text):
        result.append((text[pos:], fg, bg, bold, italic))
    return result


class LogcatTab(QWidget):
    """A single logcat capture session."""

    status_changed = pyqtSignal()

    # ── Construction ──────────────────────────────────────────────────────────

    def __init__(self, parent=None):
        super().__init__(parent)
        self._reader: ProcessReader | None = None
        self._thread: QThread | None = None
        self._running = False
        self._match_positions: list[int] = []
        self._match_idx = 0
        self._total_lines = 0

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Both bars already have border-bottom — no need for separator widgets
        root.addWidget(self._build_control_bar(), stretch=0)
        root.addWidget(self._build_search_bar(), stretch=0)
        root.addWidget(self._build_log_area(), stretch=1)

    # ── Control bar ───────────────────────────────────────────────────────────

    def _build_control_bar(self) -> QFrame:
        """Control bar with device/package selection, start/stop, and tools."""
        bar = QFrame()
        bar.setFixedHeight(52)
        bar.setMinimumHeight(52)
        bar.setObjectName("controlBar")
        bar.setStyleSheet("QFrame#controlBar { background: #242424; border-bottom: 1px solid #333333; }")

        h = QHBoxLayout(bar)
        h.setContentsMargins(8, 6, 8, 6)
        h.setSpacing(6)

        # Device label with styling
        lbl_device = QLabel("Device")
        lbl_device.setStyleSheet("color: #E8E8E8; font-weight: 500; font-size: 11px; padding: 0px 4px;")
        lbl_device.setMaximumWidth(50)
        lbl_device.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(lbl_device, stretch=0)
        
        self.device_combo = CustomComboBox()
        self.device_combo.setMinimumWidth(180)
        self.device_combo.setMaximumWidth(280)
        self.device_combo.setFixedHeight(30)
        self.device_combo.setToolTip("Select ADB device")
        h.addWidget(self.device_combo, stretch=1)

        btn_refresh = QPushButton()
        btn_refresh.setIcon(icons.icon_refresh())
        btn_refresh.setProperty("role", "tool")
        btn_refresh.setToolTip("Refresh devices")
        btn_refresh.setFixedSize(30, 30)
        btn_refresh.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        btn_refresh.clicked.connect(self.refresh_devices)
        h.addWidget(btn_refresh, stretch=0)

        h.addWidget(self._build_v_sep(), stretch=0)

        # Package label with styling
        lbl_pkg = QLabel("Package")
        lbl_pkg.setStyleSheet("color: #E8E8E8; font-weight: 500; font-size: 11px; padding: 0px 4px;")
        lbl_pkg.setMaximumWidth(60)
        lbl_pkg.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        h.addWidget(lbl_pkg, stretch=0)
        
        self.pkg_combo = CustomComboBox()
        self.pkg_combo.setEditable(True)
        self.pkg_combo.setMinimumWidth(180)
        self.pkg_combo.setMaximumWidth(280)
        self.pkg_combo.setFixedHeight(30)
        self.pkg_combo.setToolTip("Package name (empty = all)")
        self._load_packages()
        h.addWidget(self.pkg_combo, stretch=1)

        h.addStretch(1)

        # === Action Buttons ===
        self.btn_start = QPushButton("Start")
        self.btn_start.setIcon(icons.icon_play())
        self.btn_start.setProperty("role", "start")
        self.btn_start.setFixedHeight(30)
        self.btn_start.setMinimumWidth(70)
        self.btn_start.setMaximumWidth(90)
        self.btn_start.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.btn_start.clicked.connect(self.start_capture)
        h.addWidget(self.btn_start, stretch=0)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setIcon(icons.icon_stop())
        self.btn_stop.setProperty("role", "stop")
        self.btn_stop.setFixedHeight(30)
        self.btn_stop.setMinimumWidth(70)
        self.btn_stop.setMaximumWidth(90)
        self.btn_stop.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_capture)
        h.addWidget(self.btn_stop, stretch=0)

        h.addWidget(self._build_v_sep(), stretch=0)

        # === Tool Buttons ===
        for tip, ico, slot in [
            ("Clear log",  icons.icon_clear(), self.clear_log),
            ("Copy all",   icons.icon_copy(),  self.copy_log),
            ("Save to…",   icons.icon_save(),  self.save_log),
        ]:
            b = QPushButton()
            b.setIcon(ico)
            b.setProperty("role", "tool")
            b.setToolTip(tip)
            b.setFixedSize(30, 30)
            b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            b.clicked.connect(slot)
            h.addWidget(b, stretch=0)

        self.refresh_devices()
        return bar

    # ── Search bar ────────────────────────────────────────────────────────────

    def _build_search_bar(self) -> QFrame:
        """Search/filter bar with search input and tool buttons."""
        bar = QFrame()
        bar.setFixedHeight(44)
        bar.setMinimumHeight(44)
        bar.setObjectName("searchBar")
        bar.setStyleSheet("QFrame#searchBar { background: #1E1E1E; border-bottom: 1px solid #333333; }")

        h = QHBoxLayout(bar)
        h.setContentsMargins(8, 4, 8, 4)
        h.setSpacing(6)

        # Search input
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search / highlight…")
        self.search_edit.setFixedHeight(32)
        self.search_edit.setMinimumWidth(150)
        self.search_edit.setTextMargins(4, 2, 4, 2)
        self.search_edit.textChanged.connect(self._on_search_changed)
        h.addWidget(self.search_edit, stretch=1)

        # === Toggle Buttons ===
        for text, attr, tip in [
            ("Aa", "btn_case",  "Case sensitive"),
            (".*", "btn_regex", "Regular expression"),
            ("⌥G", "btn_grep",  "Grep mode (hide non-matching lines)"),
        ]:
            b = QPushButton(text)
            b.setProperty("role", "toggle")
            b.setCheckable(True)
            b.setToolTip(tip)
            b.setFixedSize(36, 32)
            b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            b.toggled.connect(self._on_search_changed)
            setattr(self, attr, b)
            h.addWidget(b, stretch=0)

        h.addWidget(self._build_v_sep(), stretch=0)

        # === Navigation Buttons ===
        btn_prev = QPushButton()
        btn_prev.setIcon(icons.icon_up())
        btn_prev.setProperty("role", "tool")
        btn_prev.setFixedSize(30, 32)
        btn_prev.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        btn_prev.setToolTip("Previous match")
        btn_prev.clicked.connect(self._prev_match)
        h.addWidget(btn_prev, stretch=0)

        btn_next = QPushButton()
        btn_next.setIcon(icons.icon_down())
        btn_next.setProperty("role", "tool")
        btn_next.setFixedSize(30, 32)
        btn_next.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        btn_next.setToolTip("Next match")
        btn_next.clicked.connect(self._next_match)
        h.addWidget(btn_next, stretch=0)

        self.lbl_match = QLabel("0 / 0")
        self.lbl_match.setStyleSheet("color: #888888; font-size: 11px;")
        self.lbl_match.setFixedWidth(60)
        self.lbl_match.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.addWidget(self.lbl_match)

        h.addWidget(self._build_v_sep())

        self.btn_autoscroll = QPushButton("Auto-scroll")
        self.btn_autoscroll.setProperty("role", "toggle")
        self.btn_autoscroll.setCheckable(True)
        self.btn_autoscroll.setChecked(True)
        self.btn_autoscroll.setFixedHeight(32)
        self.btn_autoscroll.setMinimumWidth(80)
        self.btn_autoscroll.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        h.addWidget(self.btn_autoscroll)

        self.btn_wrap = QPushButton("Wrap")
        self.btn_wrap.setProperty("role", "toggle")
        self.btn_wrap.setCheckable(True)
        self.btn_wrap.setChecked(False)
        self.btn_wrap.setFixedHeight(32)
        self.btn_wrap.setMinimumWidth(60)
        self.btn_wrap.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.btn_wrap.toggled.connect(self._toggle_wrap)
        h.addWidget(self.btn_wrap)

        return bar

    # ── Log area ──────────────────────────────────────────────────────────────

    def _build_log_area(self) -> QTextEdit:
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.log_view.setUndoRedoEnabled(False)
        fixed = QFont("Menlo", 12)
        fixed.setStyleHint(QFont.StyleHint.Monospace)
        self.log_view.setFont(fixed)
        return self.log_view

    # ── Separators ────────────────────────────────────────────────────────────

    @staticmethod
    def _build_v_sep() -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.VLine)
        f.setStyleSheet("background: #333333; max-width: 1px; border: none; margin: 4px 2px;")
        return f

    @staticmethod
    def _build_h_sep() -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setFixedHeight(1)
        f.setStyleSheet("background: #333333; border: none;")
        return f

    # ── Device management ─────────────────────────────────────────────────────

    def refresh_devices(self):
        current = self.device_combo.currentText()
        self.device_combo.clear()
        devices = get_adb_devices()
        if devices:
            self.device_combo.addItems(devices)
            idx = self.device_combo.findText(current)
            if idx >= 0:
                self.device_combo.setCurrentIndex(idx)
        else:
            self.device_combo.addItem("(no devices)")
        self.status_changed.emit()

    # ── Package management ────────────────────────────────────────────────────

    def _load_packages(self):
        from src.core.settings import Settings
        s = Settings()
        self.pkg_combo.clear()
        self.pkg_combo.addItem("")
        for p in s.packages:
            self.pkg_combo.addItem(p)
        if s.default_package:
            idx = self.pkg_combo.findText(s.default_package)
            if idx >= 0:
                self.pkg_combo.setCurrentIndex(idx)

    def reload_packages(self):
        current = self.pkg_combo.currentText()
        self._load_packages()
        idx = self.pkg_combo.findText(current)
        if idx >= 0:
            self.pkg_combo.setCurrentIndex(idx)

    # ── Capture ───────────────────────────────────────────────────────────────

    def start_capture(self):
        if self._running:
            return
        device = self.device_combo.currentText()
        if not device or device == "(no devices)":
            return
        package = self.pkg_combo.currentText().strip()
        self._running = True
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.status_changed.emit()

        from src.core.pidcat_runner import get_pidcat_path
        import sys as _sys
        
        pidcat_path = get_pidcat_path()
        cmd = [_sys.executable, pidcat_path, package or "com.fadcam.beta"]
        
        env = None
        if device:
            import os
            env = os.environ.copy()
            env['ANDROID_SERIAL'] = device

        self._thread = QThread()
        self._reader = ProcessReader(cmd=cmd, env=env)
        self._reader.moveToThread(self._thread)
        self._thread.started.connect(self._reader.run)
        self._reader.line_ready.connect(self._append_line)
        self._reader.finished.connect(self._on_reader_finished)
        self._thread.start()

    def stop_capture(self):
        if self._reader and self._reader.process:
            try:
                self._reader.process.terminate()
            except Exception:
                pass

    def _on_reader_finished(self):
        self._running = False
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if self._thread:
            self._thread.quit()
            self._thread.wait()
        self.status_changed.emit()

    # ── Log output ────────────────────────────────────────────────────────────

    def _append_line(self, raw: str):
        self._total_lines += 1
        text = raw.rstrip("\n")

        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        chunks = _parse_ansi(text)
        for chunk_text, fg, bg, bold, italic in chunks:
            fmt = QTextCharFormat()
            fmt.setForeground(fg)
            if bg != _DEFAULT_BG:
                fmt.setBackground(bg)
            if bold:
                fmt.setFontWeight(QFont.Weight.Bold)
            if italic:
                fmt.setFontItalic(True)
            cursor.insertText(chunk_text, fmt)

        fmt_nl = QTextCharFormat()
        cursor.insertText("\n", fmt_nl)

        if self.btn_autoscroll.isChecked():
            self.log_view.setTextCursor(cursor)
            self.log_view.ensureCursorVisible()

    # ── Search / highlight ────────────────────────────────────────────────────

    def _on_search_changed(self):
        query = self.search_edit.text()
        self._match_positions = []
        self._match_idx = 0

        extra = []
        if query:
            from PyQt6.QtGui import QTextDocument
            find_flags = QTextDocument.FindFlag(0)
            if self.btn_case.isChecked():
                find_flags |= QTextDocument.FindFlag.FindCaseSensitively

            doc = self.log_view.document()
            cursor = doc.find(query, 0, find_flags)
            while not cursor.isNull():
                fmt = QTextCharFormat()
                fmt.setBackground(QColor("#3D1510"))
                fmt.setForeground(QColor("#FFD050"))
                self._match_positions.append(cursor.position())
                extra.append((cursor, fmt))
                cursor = doc.find(query, cursor, find_flags)

        self.log_view.setExtraSelections(
            [self._make_extra(c, f) for c, f in extra]
        )
        count = len(self._match_positions)
        cur_label = f"{min(self._match_idx + 1, count)} / {count}" if count else "0 / 0"
        self.lbl_match.setText(cur_label)

    @staticmethod
    def _make_extra(cursor, fmt) -> "QTextEdit.ExtraSelection":
        sel = QTextEdit.ExtraSelection()
        sel.cursor = cursor
        sel.format = fmt
        return sel

    def _prev_match(self):
        if self._match_positions:
            self._match_idx = (self._match_idx - 1) % len(self._match_positions)
            self._jump_to_match()

    def _next_match(self):
        if self._match_positions:
            self._match_idx = (self._match_idx + 1) % len(self._match_positions)
            self._jump_to_match()

    def _jump_to_match(self):
        pos = self._match_positions[self._match_idx]
        cursor = self.log_view.textCursor()
        cursor.setPosition(pos)
        self.log_view.setTextCursor(cursor)
        self.log_view.ensureCursorVisible()
        count = len(self._match_positions)
        self.lbl_match.setText(f"{self._match_idx + 1} / {count}")

    def _toggle_wrap(self, checked: bool):
        mode = QTextEdit.LineWrapMode.WidgetWidth if checked else QTextEdit.LineWrapMode.NoWrap
        self.log_view.setLineWrapMode(mode)

    # ── Actions ───────────────────────────────────────────────────────────────

    def clear_log(self):
        self.log_view.clear()
        self._total_lines = 0
        self._match_positions = []
        self.lbl_match.setText("0 / 0")
        self.status_changed.emit()

    def copy_log(self):
        QApplication.clipboard().setText(self.log_view.toPlainText())

    def save_log(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save log", f"logcat_{datetime.now():%Y%m%d_%H%M%S}.txt",
            "Text files (*.txt);;All files (*)"
        )
        if path:
            Path(path).write_text(self.log_view.toPlainText(), encoding="utf-8")

    # ── Public helpers ────────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def line_count(self) -> int:
        return self._total_lines

    @property
    def current_device(self) -> str:
        return self.device_combo.currentText()

    @property
    def current_package(self) -> str:
        return self.pkg_combo.currentText().strip()
