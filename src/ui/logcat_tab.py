"""LogcatTab — single device/package logcat session view."""
from __future__ import annotations

import os
import tempfile
import shutil
import re
from datetime import datetime
from collections import deque
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QPoint, QRect, QEvent
from PyQt6.QtGui import QTextCharFormat, QColor, QFont, QTextCursor, QFontDatabase, QPainter, QPolygon, QBrush, QKeySequence, QShortcut, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QLabel, QComboBox, QPushButton, QLineEdit,
    QTextEdit, QFileDialog, QApplication, QSizePolicy,
    QListWidget, QListWidgetItem, QMessageBox,
)
from PyQt6.QtSvg import QSvgRenderer

from src.core.process_reader import ProcessReader
from src.utils.adb_utils import get_adb_devices
from src.core.settings import Settings
from src.ui import icons


# ── Line Number Area Widget (Production-Grade) ─────────────────────────────────
class LineNumberArea(QWidget):
    """
    Production-grade line number area using Qt's document layout API.
    
    This is the same approach used by Qt Creator, VS Code, and professional editors.
    Rather than calculating scroll positions, we iterate through document blocks and
    query their exact positions from the layout.
    
    Key properties:
    - Block-based iteration (1 line number per logical line/block)
    - Handles word wrapping correctly (wrapped visual lines don't get numbers)
    - Accounts for variable block heights
    - Uses QTextDocument.documentLayout().blockBoundingRect()
    """
    
    def __init__(self, text_edit: 'LogTextEdit'):
        super().__init__(text_edit)
        self.text_edit = text_edit
        self.setContentsMargins(0, 0, 0, 0)
        self.setStyleSheet(
            "QWidget { background-color: #1a1a1a; color: #555555; border-right: 1px solid #333333; padding: 0px; margin: 0px; }"
        )
        self.update_width()

    def update_width(self):
        doc = self.text_edit.document()
        digits = len(str(max(1, doc.blockCount())))
        fm = self.text_edit.fontMetrics()
        width = fm.horizontalAdvance("9" * digits) + 10
        self.setFixedWidth(width)
    
    def sizeHint(self) -> QSize:
        """Return fixed width, height matches parent."""
        return QSize(self.width(), self.text_edit.height())
    
    def paintEvent(self, event):
        """Paint line numbers using document blocks and cursor positioning."""
        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor("#1a1a1a"))
        
        document = self.text_edit.document()
        viewport_height = self.text_edit.viewport().height()
        painter.setFont(self.text_edit.font())
        painter.setPen(QColor("#555555"))

        layout = document.documentLayout()
        scroll_y = self.text_edit.verticalScrollBar().value()
        cursor = self.text_edit.cursorForPosition(QPoint(0, 0))
        block = cursor.block()
        line_number = block.blockNumber() + 1

        while block.isValid():
            rect = layout.blockBoundingRect(block)
            block_y = rect.top() - scroll_y
            block_height = rect.height()

            if block_y > viewport_height:
                break
            if block_y + block_height >= 0:
                line_rect = QRect(0, int(block_y), self.width() - 4, int(block_height))
                painter.drawText(
                    line_rect,
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    f"{line_number}"
                )

            block = block.next()
            line_number += 1

        painter.end()




class LogTextEdit(QTextEdit):
    """QTextEdit with SVG watermark background and optional line numbers."""
    
    # Signal: emitted when text changes (for line numbers to update)
    text_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._watermark_pixmap = None
        self._load_watermark()
        # Connect internal text change
        self.textChanged.connect(self.text_changed.emit)
    
    def _load_watermark(self):
        """Load SVG as watermark pixmap."""
        try:
            svg_path = Path(__file__).parent.parent / "icons" / "fadcat.svg"
            if not svg_path.exists():
                return
            
            # Render SVG
            renderer = QSvgRenderer(str(svg_path))
            pixmap = QPixmap(300, 300)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            self._watermark_pixmap = pixmap
        except Exception:
            pass
    
    def paintEvent(self, event):
        """Paint watermark background."""
        # Paint watermark FIRST (lower z-index)
        if self._watermark_pixmap and Settings().show_watermark:
            painter = QPainter(self.viewport())
            painter.setOpacity(Settings().watermark_opacity)
            # Center the watermark
            x = (self.viewport().width() - self._watermark_pixmap.width()) // 2
            y = (self.viewport().height() - self._watermark_pixmap.height()) // 2
            painter.drawPixmap(x, y, self._watermark_pixmap)
            painter.end()
        
        # Paint text LAST (higher z-index, on top)
        super().paintEvent(event)


# ── Custom ComboBox with proper dropdown arrow ────────────────────────────────
class CustomComboBox(QComboBox):
    """QComboBox with a proper Python-drawn dropdown arrow."""
    def paintEvent(self, event):
        super().paintEvent(event)
        if self.isEnabled():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            arrow_x = self.width() - 22
            arrow_y = (self.height() - 6) // 2
            points = [
                QPoint(arrow_x, arrow_y),
                QPoint(arrow_x + 8, arrow_y),
                QPoint(arrow_x + 4, arrow_y + 6),
            ]
            painter.setBrush(QBrush(QColor("#E8302A")))
            painter.setPen(QColor("#E8302A"))
            painter.drawConvexPolygon(QPolygon(points))
    
    def mousePressEvent(self, event):
        """Keep default focus handling; popup is shown on release."""
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Show dropdown menu when clicking anywhere on the combo box."""
        if event.button() == Qt.MouseButton.LeftButton:
            if not self.view().isVisible():
                self.showPopup()
            return
        super().mouseReleaseEvent(event)


class PackageComboBox(CustomComboBox):
    """ComboBox with a search bar inside the popup."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        if self.lineEdit():
            self.lineEdit().setReadOnly(True)
            self.lineEdit().installEventFilter(self)
        self._popup = QFrame(None, Qt.WindowType.Popup)
        self._popup.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._popup.setObjectName("pkgPopup")
        self._popup.setStyleSheet("QFrame#pkgPopup { background: transparent; border: none; }")

        outer = QVBoxLayout(self._popup)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._panel = QFrame(self._popup)
        self._panel.setObjectName("pkgPanel")
        self._panel.setStyleSheet(
            "QFrame#pkgPanel { background: #1E1E1E; border: 1px solid #333333; border-radius: 10px; }"
        )
        outer.addWidget(self._panel)

        layout = QVBoxLayout(self._panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        self.search_edit = QLineEdit(self._popup)
        self.search_edit.setPlaceholderText("Search packages...")
        self.search_edit.setFixedHeight(28)
        self.search_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.search_edit.setStyleSheet(
            "QLineEdit { background: #2A2A2A; color: #E8E8E8; border: 1px solid #3A3A3A; padding: 4px 8px; border-radius: 6px; }"
        )
        layout.addWidget(self.search_edit, stretch=0)

        self._list_widget = QListWidget(self._popup)
        self._list_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._list_widget.setStyleSheet(
            "QListWidget { background: #1E1E1E; color: #E8E8E8; border: 1px solid #2A2A2A; border-radius: 8px; }"
            "QListWidget::item:selected { background: #2A2A2A; }"
        )
        layout.addWidget(self._list_widget, stretch=1)

        self._list_widget.itemClicked.connect(self._on_item_clicked)
        self._all_top: list[str] = []
        self._all_lower: list[str] = []

        app = QApplication.instance()
        if app:
            app.setStyleSheet(
                app.styleSheet()
                + " QToolTip { background-color: #1A1A1A; color: #E8E8E8; border: 1px solid #333333; padding: 6px 8px; }"
            )

    def showPopup(self):
        if self._popup.isVisible():
            return
        # Size and position popup
        width = max(self.width(), 280)
        height = 320
        pos = self.mapToGlobal(self.rect().bottomLeft())
        self._popup.setGeometry(pos.x(), pos.y(), width, height)
        self._popup.show()
        # Reset filter on open so list is visible, then focus search
        if self.search_edit.text():
            self.search_edit.clear()
        self.search_edit.setFocus()

    def hidePopup(self):
        if self._popup.isVisible():
            self._popup.hide()

    def eventFilter(self, obj, event):
        if obj is self.lineEdit() and event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                if not self._popup.isVisible():
                    self.showPopup()
                return True
        return super().eventFilter(obj, event)

    def _on_item_clicked(self, item):
        if not item or item.data(Qt.ItemDataRole.UserRole) == "header":
            return
        value = item.data(Qt.ItemDataRole.UserRole)
        self.setCurrentText(value if value else item.text().strip())
        self.hidePopup()

    def set_sectioned_items(self, top_items: list[str], lower_items: list[str], filter_text: str):
        self._all_top = list(top_items)
        self._all_lower = list(lower_items)
        self.apply_filter(filter_text)

    def apply_filter(self, filter_text: str):
        ftext = (filter_text or "").strip().lower()
        self._list_widget.clear()

        def add_header(title: str, tooltip: str):
            header = QListWidgetItem(title)
            header.setData(Qt.ItemDataRole.UserRole, "header")
            header.setFlags(Qt.ItemFlag.ItemIsEnabled)
            font = header.font()
            font.setBold(True)
            header.setFont(font)
            header.setForeground(QColor("#E8302A"))
            header.setToolTip(tooltip)
            self._list_widget.addItem(header)

        def add_item(text: str):
            item = QListWidgetItem(f"  {text}")
            item.setData(Qt.ItemDataRole.UserRole, text)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            if text == "Global":
                item.setToolTip("Global: show all logs (no package filtering).")
            self._list_widget.addItem(item)

        top_total = len([p for p in self._all_top if p != "Global"])
        top_matches = [p for p in self._all_top if not ftext or ftext in p.lower()]
        if top_matches:
            add_header(
                f"FadCat Packages ({top_total})",
                "FadCat packages are saved in Settings for quick access."
            )
            for p in top_matches:
                add_item(p)

        lower_total = len(self._all_lower)
        lower_matches = [p for p in self._all_lower if not ftext or ftext in p.lower()]
        if lower_matches:
            add_header(
                f"Device Packages ({lower_total})",
                "Device packages are installed on the currently connected device."
            )
            for p in lower_matches:
                add_item(p)

# ── ANSI colour table ─────────────────────────────────────────────────────────
_ANSI_RESET = re.compile(r"\x1b\[([0-9;]*)m")
_ANSI_STRIP = re.compile(r"\x1b\[[0-9;]*m")
_TAG_RE = re.compile(r"^[A-Z]\/([^:(]+)")
_LEVEL_RE = re.compile(r"\s([VDIWEF])\s")

_FG = {
    30: "#9C9C9C", 31: "#FF5F5F", 32: "#5AF78E", 33: "#F3F99D",
    34: "#57C7FF", 35: "#D070FF", 36: "#5FFFD7", 37: "#FFFFFF",
    90: "#B0B0B0", 91: "#FF7A7A", 92: "#7CFFAA", 93: "#FFF0A6",
    94: "#7CCBFF", 95: "#E09BFF", 96: "#7CFFE6", 97: "#FFFFFF",
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


def _line_color_from_chunks(chunks: list[tuple[str, QColor, QColor, bool, bool]]) -> QColor | None:
    for chunk_text, fg, bg, _bold, _italic in chunks:
        if chunk_text.strip() and fg != _DEFAULT_FG and bg == _DEFAULT_BG:
            return fg
    return None


def _contrast_color(color: QColor) -> QColor:
    r = color.red()
    g = color.green()
    b = color.blue()
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
    return QColor("#111111") if luminance > 0.6 else QColor("#FFFFFF")


def _extract_tag(text: str) -> str | None:
    clean = _ANSI_STRIP.sub("", text).lstrip()
    m = _TAG_RE.match(clean)
    if m:
        return m.group(1).strip()
    m2 = _LEVEL_RE.search(clean)
    if m2:
        left = clean[:m2.start()].rstrip()
        if left:
            return left
    return None


def _extract_level(text: str) -> str | None:
    clean = _ANSI_STRIP.sub("", text).lstrip()
    if not clean:
        return None
    tokens = clean.split()
    for idx in range(min(2, len(tokens))):
        tok = tokens[idx]
        if tok in {"V", "D", "I", "W", "E", "F"}:
            return tok
    for tok in tokens:
        if tok in {"V", "D", "I", "W", "E", "F"}:
            return tok
    if len(clean) >= 2 and clean[0] in "VDIWEF" and clean[1] == "/":
        return clean[0]
    m = _LEVEL_RE.search(clean)
    if not m:
        return None
    return m.group(1).strip()


class LogcatTab(QWidget):
    """A single logcat capture session."""

    status_changed = pyqtSignal()
    device_selected = pyqtSignal(str) # Emitted when a device is picked

    # ── Construction ──────────────────────────────────────────────────────────

    def __init__(self, parent=None):
        super().__init__(parent)
        self._reader: ProcessReader | None = None
        self._thread: QThread | None = None
        self._running = False
        self._match_positions: list[int] = []
        self._match_idx = 0
        self._total_lines = 0
        self._settings = Settings()
        self._max_lines = max(0, int(self._settings.log_view_max_lines))
        maxlen = self._max_lines if self._max_lines > 0 else None
        self._raw_lines: deque[tuple[str, list, str | None, str | None, QColor | None]] = deque(maxlen=maxlen)
        self._pending_lines: deque[str] = deque()
        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(16)
        self._flush_timer.timeout.connect(self._flush_pending_lines)
        self._visible_line_count = 0
        self._log_path = Path(tempfile.gettempdir()) / f"fadcat_log_{id(self)}.txt"
        try:
            self._log_fp = open(self._log_path, "w", encoding="utf-8", buffering=1)
        except Exception:
            self._log_fp = None
        self._pkg_filter_text = ""
        self._pkg_settings: list[str] = []
        self._pkg_device: list[str] = []
        self._pending_restart = False
        self._last_package = ""
        self._stopping = False
        self._level_filters: set[str] = set()
        self._rebuild_timer = QTimer(self)
        self._rebuild_timer.setInterval(16)
        self._rebuild_timer.timeout.connect(self._rebuild_step)
        self._rebuild_id = 0
        self._rebuild_iter = None
        self._rebuild_query = ""
        self._rebuild_grep = False
        self._rebuild_highlight = False
        self._color_line_by_tag = self._settings.color_line_by_tag
        self._last_tag_color: QColor | None = None
        self._match_ranges: list[tuple[int, int]] = []
        self._base_selections: list[QTextEdit.ExtraSelection] = []
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(140)
        self._search_timer.timeout.connect(self._apply_search_now)

        self._build_ui()
        self._setup_shortcuts()
        self._last_package = self._selected_package()

        # Connect device change to fetching packages
        self.device_combo.currentTextChanged.connect(self._on_device_changed)
        
        # Connect package selection to save it in settings
        self.pkg_combo.currentTextChanged.connect(self._on_package_changed)

    @staticmethod
    def _hand(widget: QWidget):
        widget.setCursor(Qt.CursorShape.PointingHandCursor)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_control_bar(), stretch=0)
        root.addWidget(self._build_search_bar(), stretch=0)
        root.addWidget(self._build_log_area(), stretch=1)

    # ── Control bar ───────────────────────────────────────────────────────────

    def _build_control_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(56)
        bar.setObjectName("controlBar")
        bar.setStyleSheet("QFrame#controlBar { background: #242424; border-bottom: 1px solid #333333; }")

        h = QHBoxLayout(bar)
        h.setContentsMargins(12, 8, 12, 8)
        h.setSpacing(10)
        self._control_layout = h

        # Device
        self.lbl_device = QLabel("Device")
        self.lbl_device.setStyleSheet("color: #AAAAAA; font-size: 12px; font-weight: 500; background: transparent;")
        self.lbl_device.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        h.addWidget(self.lbl_device, stretch=0)

        self.device_combo = CustomComboBox()
        self.device_combo.setMinimumWidth(120)
        self.device_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.device_combo.setFixedHeight(34)
        self.device_combo.setToolTip("Select ADB device")
        h.addWidget(self.device_combo, stretch=2)

        btn_refresh = QPushButton()
        btn_refresh.setIcon(icons.icon_refresh())
        btn_refresh.setProperty("role", "icon-btn")
        btn_refresh.setToolTip("Refresh devices")
        btn_refresh.setFixedSize(34, 34)
        self._hand(btn_refresh)
        btn_refresh.clicked.connect(self.refresh_devices)
        h.addWidget(btn_refresh, stretch=0)

        h.addWidget(self._build_v_sep(), stretch=0)

        # Package
        self.lbl_pkg = QLabel("Package")
        self.lbl_pkg.setStyleSheet("color: #AAAAAA; font-size: 12px; font-weight: 500; background: transparent;")
        self.lbl_pkg.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        h.addWidget(self.lbl_pkg, stretch=0)

        self.pkg_combo = PackageComboBox()
        self.pkg_combo.setMinimumWidth(120)
        self.pkg_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.pkg_combo.setFixedHeight(34)
        self.pkg_combo.setToolTip("Package name (select 'Global' for all logs)")
        if self.pkg_combo.lineEdit():
            self.pkg_combo.lineEdit().setPlaceholderText("Select a package or Global")
        # Search bar lives inside popup
        self.pkg_combo.search_edit.textChanged.connect(self._on_pkg_filter_changed)
        self._load_packages()
        h.addWidget(self.pkg_combo, stretch=2)

        h.addStretch(1)

        # Start/Stop Toggle
        self.btn_toggle = QPushButton("Start")
        self.btn_toggle.setIcon(icons.icon_play())
        self.btn_toggle.setProperty("role", "start")
        self.btn_toggle.setFixedHeight(34)
        self.btn_toggle.setMinimumWidth(90)
        self.btn_toggle.setToolTip("Toggle Capture")
        self._hand(self.btn_toggle)
        self.btn_toggle.clicked.connect(self.toggle_capture)
        h.addWidget(self.btn_toggle, stretch=0)

        h.addWidget(self._build_v_sep(), stretch=0)

        # Tools
        self._btn_clear = self._icon_btn(icons.icon_clear(), "Clear", self.clear_log, "Clear log")
        h.addWidget(self._btn_clear, stretch=0)

        self._btn_copy = self._icon_btn(icons.icon_copy(), "Copy", self.copy_log, "Copy all to clipboard")
        h.addWidget(self._btn_copy, stretch=0)

        self._btn_save = self._icon_btn(icons.icon_save(), "Save", self.save_log, "Save log to file")
        h.addWidget(self._btn_save, stretch=0)

        self.refresh_devices()
        return bar

    def _icon_btn(self, icon, text, slot, tip=None) -> QPushButton:
        b = QPushButton(f" {text}")
        b.setIcon(icon)
        b.setProperty("role", "tool-text")
        b.setFixedHeight(34)
        b.setMinimumWidth(75)
        self._hand(b)
        b.clicked.connect(slot)
        if tip:
            b.setToolTip(tip)
        return b

    # ── Search bar ────────────────────────────────────────────────────────────

    def _build_search_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(54)
        bar.setObjectName("searchBar")
        bar.setStyleSheet("QFrame#searchBar { background: #1E1E1E; border-bottom: 1px solid #333333; }")

        h = QHBoxLayout(bar)
        h.setContentsMargins(12, 6, 12, 6)
        h.setSpacing(8)
        self._search_layout = h

        # Search input
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search logs... (⌘F)")
        self.search_edit.setFixedHeight(32)
        self.search_edit.setMinimumWidth(180)
        self.search_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search_changed)
        self.search_edit.returnPressed.connect(self._next_match)
        h.addWidget(self.search_edit, stretch=3)

        # Filter toggles
        self.btn_case = QPushButton("Aa")
        self.btn_case.setProperty("role", "toggle")
        self.btn_case.setCheckable(True)
        self.btn_case.setToolTip("Case sensitive: match upper/lowercase exactly.")
        self.btn_case.setFixedSize(44, 34)
        self._hand(self.btn_case)
        self.btn_case.toggled.connect(self._on_search_changed)
        h.addWidget(self.btn_case, stretch=0)

        self.btn_regex = QPushButton(".*")
        self.btn_regex.setProperty("role", "toggle")
        self.btn_regex.setCheckable(True)
        self.btn_regex.setToolTip(
            "Regular expression: match patterns, not just plain text. "
            "Examples: `error|fail`, `\\bActivity\\b`, `^E/`."
        )
        self.btn_regex.setFixedSize(44, 34)
        self._hand(self.btn_regex)
        self.btn_regex.toggled.connect(self._on_search_changed)
        h.addWidget(self.btn_regex, stretch=0)

        self.btn_grep = QPushButton("Grep ⌥G")
        self.btn_grep.setIcon(icons.icon_grep())
        self.btn_grep.setProperty("role", "toggle")
        self.btn_grep.setCheckable(True)
        self.btn_grep.setToolTip("Grep mode - hide non-matching lines (⌥G)")
        self.btn_grep.setMinimumWidth(95)
        self.btn_grep.setFixedHeight(34)
        self._hand(self.btn_grep)
        self.btn_grep.toggled.connect(self._on_search_changed)
        h.addWidget(self.btn_grep, stretch=0)

        h.addWidget(self._build_v_sep(), stretch=0)

        # Level chips (compact)
        self._level_chip_bar = QFrame()
        self._level_chip_bar.setStyleSheet("QFrame { background: transparent; }")
        chip_lay = QHBoxLayout(self._level_chip_bar)
        chip_lay.setContentsMargins(0, 0, 0, 0)
        chip_lay.setSpacing(4)
        self._level_chip_buttons: list[QPushButton] = []

        def add_level_chip(label: str, color: str, icon_fn, tooltip: str):
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFixedHeight(24)
            btn.setFixedWidth(26)
            btn.setIcon(icon_fn())
            btn.setIconSize(QSize(12, 12))
            self._hand(btn)
            btn.setStyleSheet(
                "QPushButton { background: #2A2A2A; color: #CCCCCC; border: 1px solid #3A3A3A; border-radius: 8px; padding: 0px; }"
                f"QPushButton:checked {{ background: {color}; color: #111111; border: 1px solid {color}; }}"
            )
            btn.setToolTip(tooltip)
            btn.toggled.connect(lambda checked, lvl=label: self._toggle_level_filter(lvl, checked))
            chip_lay.addWidget(btn)
            self._level_chip_buttons.append(btn)

        add_level_chip("V", "#8A8A8A", icons.icon_level_v,
                       "Verbose: extremely detailed messages. Turn this on only when you need very noisy, low-level logs.")
        add_level_chip("D", "#4A9FE8", icons.icon_level_d,
                       "Debug: developer diagnostics and troubleshooting details. Useful while investigating issues.")
        add_level_chip("I", "#3CB371", icons.icon_level_i,
                       "Info: normal app status and milestones. Good for understanding what the app is doing.")
        add_level_chip("W", "#E8A020", icons.icon_level_w,
                       "Warning: something unexpected happened, but the app can keep running.")
        add_level_chip("E", "#E8302A", icons.icon_level_e,
                       "Error: something failed. These are important when a feature is broken.")
        add_level_chip("F", "#FF2D2D", icons.icon_level_f,
                       "Fatal: serious crash or abort. These usually mean the app stopped.")

        h.addWidget(self._level_chip_bar, stretch=0)

        # Navigation
        self.btn_prev = QPushButton()
        self.btn_prev.setIcon(icons.icon_up())
        self.btn_prev.setProperty("role", "nav-btn")
        self.btn_prev.setToolTip("Previous match (⇧F3)")
        self.btn_prev.setFixedSize(34, 34)
        self._hand(self.btn_prev)
        self.btn_prev.clicked.connect(self._prev_match)
        h.addWidget(self.btn_prev, stretch=0)

        self.btn_next = QPushButton()
        self.btn_next.setIcon(icons.icon_down())
        self.btn_next.setProperty("role", "nav-btn")
        self.btn_next.setToolTip("Next match (F3)")
        self.btn_next.setFixedSize(34, 34)
        self._hand(self.btn_next)
        self.btn_next.clicked.connect(self._next_match)
        h.addWidget(self.btn_next, stretch=0)

        self.lbl_match = QLabel("0 / 0")
        self.lbl_match.setStyleSheet("color: #888888; font-size: 11px; min-width: 50px;")
        self.lbl_match.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.addWidget(self.lbl_match, stretch=0)

        h.addStretch(1)

        # Options
        self.btn_autoscroll = QPushButton()
        self.btn_autoscroll.setIcon(icons.icon_autoscroll())
        self.btn_autoscroll.setProperty("role", "toggle")
        self.btn_autoscroll.setCheckable(True)
        self.btn_autoscroll.setChecked(True)
        self.btn_autoscroll.setFixedHeight(34)
        self.btn_autoscroll.setFixedWidth(44)
        self.btn_autoscroll.setToolTip("Auto-scroll: keep the view pinned to the newest logs.")
        self._hand(self.btn_autoscroll)
        h.addWidget(self.btn_autoscroll, stretch=0)

        self.btn_wrap = QPushButton()
        self.btn_wrap.setIcon(icons.icon_wrap())
        self.btn_wrap.setProperty("role", "toggle")
        self.btn_wrap.setCheckable(True)
        self.btn_wrap.setChecked(False)
        self.btn_wrap.setFixedHeight(34)
        self.btn_wrap.setFixedWidth(44)
        self.btn_wrap.setToolTip("Wrap: wrap long lines instead of scrolling horizontally.")
        self._hand(self.btn_wrap)
        self.btn_wrap.toggled.connect(self._toggle_wrap)
        h.addWidget(self.btn_wrap, stretch=0)

        return bar

    # ── Shortcuts ─────────────────────────────────────────────────────────────

    def _setup_shortcuts(self):
        # Cmd+F - focus search
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self.search_edit.setFocus)
        
        # Alt+G - toggle grep
        QShortcut(QKeySequence("Alt+G"), self).activated.connect(self.btn_grep.toggle)
        
        # F3 / Shift+F3 - next/prev match
        QShortcut(QKeySequence("F3"), self).activated.connect(self._next_match)
        QShortcut(QKeySequence("Shift+F3"), self).activated.connect(self._prev_match)

    # ── Log area ──────────────────────────────────────────────────────────────

    def _build_log_area(self) -> QWidget:
        """Build log area with professional line numbers widget."""
        container = QWidget()
        container.setContentsMargins(0, 0, 0, 0)
        h_layout = QHBoxLayout(container)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)
        
        # Log text area (create first so line numbers can reference it)
        self.log_view = LogTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.log_view.setUndoRedoEnabled(False)
        self.log_view.document().setMaximumBlockCount(self._max_lines)
        # Set matching font for synchronization
        fixed = QFont("Menlo", 12)
        fixed.setStyleHint(QFont.StyleHint.Monospace)
        self.log_view.setFont(fixed)
        # CRITICAL: Remove all padding/margins so line numbers align perfectly
        self.log_view.setContentsMargins(0, 0, 0, 0)
        self.log_view.viewport().setContentsMargins(6, 0, 0, 0)
        self.log_view.document().setDocumentMargin(0)
        
        # Line number area widget (synchronized to text editor)
        self.line_number_area = LineNumberArea(self.log_view)
        self.line_number_area.setVisible(Settings().show_line_numbers)
        # Connect text and scroll changes to update line numbers
        self.log_view.text_changed.connect(self.line_number_area.update)
        self.log_view.text_changed.connect(self.line_number_area.update_width)
        self.log_view.verticalScrollBar().valueChanged.connect(self.line_number_area.update)
        
        # Add to layout
        h_layout.addWidget(self.line_number_area, stretch=0)
        h_layout.addWidget(self.log_view, stretch=1)
        
        return container

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_responsive_layout(event.size().width())

    def _update_responsive_layout(self, width: int):
        compact = width < 900
        tight = width < 780
        tiny = width < 700
        micro = width < 620

        self.lbl_device.setVisible(not compact)
        self.lbl_pkg.setVisible(not compact)

        if compact:
            self.device_combo.setMinimumWidth(90)
            self.pkg_combo.setMinimumWidth(90)
        else:
            self.device_combo.setMinimumWidth(120)
            self.pkg_combo.setMinimumWidth(120)

        self._btn_clear.setText("" if compact else " Clear")
        self._btn_copy.setText("" if compact else " Copy")
        self._btn_save.setText("" if compact else " Save")

        if tight:
            self.btn_toggle.setText("")
        else:
            self.btn_toggle.setText("Stop" if self._running else "Start")

        if compact:
            self.search_edit.setMinimumWidth(120)
        else:
            self.search_edit.setMinimumWidth(180)

        # Search row controls in very tight layouts
        self._level_chip_bar.setVisible(not tiny)
        self.btn_case.setVisible(not tiny)
        self.btn_regex.setVisible(not tiny)
        self.btn_grep.setVisible(not tiny)
        self.btn_prev.setVisible(not tiny)
        self.btn_next.setVisible(not tiny)
        self.lbl_match.setVisible(not tiny)

        if micro:
            self.search_edit.setMinimumWidth(80)
            if hasattr(self, "_search_layout"):
                self._search_layout.setSpacing(4)
                self._search_layout.setContentsMargins(8, 4, 8, 4)
            if hasattr(self, "_control_layout"):
                self._control_layout.setSpacing(6)
                self._control_layout.setContentsMargins(8, 6, 8, 6)
        else:
            if hasattr(self, "_search_layout"):
                self._search_layout.setSpacing(8)
                self._search_layout.setContentsMargins(12, 6, 12, 6)
            if hasattr(self, "_control_layout"):
                self._control_layout.setSpacing(10)
                self._control_layout.setContentsMargins(12, 8, 12, 8)

        # Compact chip sizing
        if tiny:
            for btn in self._level_chip_buttons:
                btn.setFixedWidth(22)
                btn.setFixedHeight(22)
                btn.setIconSize(QSize(10, 10))
        else:
            for btn in self._level_chip_buttons:
                btn.setFixedWidth(26)
                btn.setFixedHeight(24)
                btn.setIconSize(QSize(12, 12))


    # ── Separators ────────────────────────────────────────────────────────────

    @staticmethod
    def _build_v_sep() -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.VLine)
        f.setStyleSheet("background: #333333; max-width: 1px; border: none; margin: 0 4px;")
        return f

    # ── Device management ─────────────────────────────────────────────────────

    def refresh_devices(self):
        current = self.device_combo.currentText()
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        devices = get_adb_devices()
        if devices:
            self.device_combo.addItems(devices)
            idx = self.device_combo.findText(current)
            if idx >= 0:
                self.device_combo.setCurrentIndex(idx)
            else:
                self.device_combo.setCurrentIndex(0)
        else:
            self.device_combo.addItem("(no devices)")
        self.device_combo.blockSignals(False)
        self._on_device_changed(self.device_combo.currentText())
        self.status_changed.emit()

    def _on_device_changed(self, device: str):
        if not device or device == "(no devices)":
            return
        self.device_selected.emit(device)
        # Clear device packages immediately and fetch for the selected device
        self._pkg_device = []
        self._rebuild_package_model(
            settings_pkgs=self._pkg_settings,
            device_pkgs=[],
            current_pkg=self._selected_package(),
            filter_text=self._pkg_filter_text,
        )
        QTimer.singleShot(100, lambda d=device: self._fetch_device_packages(d))

    def _on_package_changed(self, package: str):
        """Save package selection to settings."""
        pkg = (package or "").strip()
        if pkg.lower() == "global":
            pkg = ""

        if pkg == self._last_package:
            return

        if self._running:
            result = QMessageBox.question(
                self,
                "Switch Package?",
                "Changing the package will clear current logs and restart capture. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if result != QMessageBox.StandardButton.Yes:
                # Revert selection
                self.pkg_combo.blockSignals(True)
                self.pkg_combo.setCurrentText(self._last_package or "Global")
                self.pkg_combo.blockSignals(False)
                return

            self.clear_log(confirm=False)
            self._pending_restart = True
            self.stop_capture()

        # Save selection
        self._settings.default_package = pkg
        self._settings.save()
        self._last_package = pkg

    def _selected_package(self) -> str:
        """Return normalized package text; empty means Global."""
        pkg = (self.pkg_combo.currentText() or "").strip()
        if not pkg or pkg.lower() == "global":
            return ""
        return pkg

    def _fetch_device_packages(self, device: str | None = None):
        device = device or self.device_combo.currentText()
        if not device or device == "(no devices)":
            return
        if device != self.device_combo.currentText():
            return
        
        try:
            import subprocess
            cmd = ["adb", "-s", device, "shell", "pm", "list", "packages"]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=3)
            if res.returncode == 0:
                pkgs = [line.split(":")[1].strip() for line in res.stdout.splitlines() if ":" in line]
                pkgs.sort()
                
                current_pkg = self._selected_package()
                from src.core.settings import Settings
                s = Settings()
                self._pkg_device = list(pkgs)
                self._rebuild_package_model(
                    settings_pkgs=s.packages,
                    device_pkgs=pkgs,
                    current_pkg=current_pkg,
                    filter_text=self._pkg_filter_text,
                )
        except Exception:
            pass

    # ── Package management ────────────────────────────────────────────────────

    def _load_packages(self):
        from src.core.settings import Settings
        s = Settings()
        self._rebuild_package_model(
            settings_pkgs=s.packages,
            device_pkgs=self._pkg_device,
            current_pkg=s.default_package,
            filter_text=self._pkg_filter_text,
        )

    def reload_packages(self):
        current = self._selected_package()
        self._load_packages()
        self.pkg_combo.setCurrentText(current or "Global")

    def _rebuild_package_model(self, settings_pkgs: list[str], device_pkgs: list[str], current_pkg: str, filter_text: str):
        self.pkg_combo.blockSignals(True)
        self._pkg_settings = list(settings_pkgs)
        self._pkg_device = list(device_pkgs)

        top_items = ["Global"] + [p for p in settings_pkgs if p and p != "Global"]
        seen = set(settings_pkgs)
        lower_items = [p for p in device_pkgs if p and p not in seen]

        self.pkg_combo.set_sectioned_items(top_items, lower_items, filter_text)

        # Restore selection or default to Global
        target = (current_pkg or "").strip()
        if not target:
            target = "Global"

        self.pkg_combo.setCurrentText(target)

        self.pkg_combo.blockSignals(False)

    def _on_pkg_filter_changed(self, text: str):
        self._pkg_filter_text = (text or "").strip()
        self._rebuild_package_model(
            settings_pkgs=self._pkg_settings,
            device_pkgs=self._pkg_device,
            current_pkg=self._selected_package(),
            filter_text=self._pkg_filter_text,
        )

    # ── Capture ───────────────────────────────────────────────────────────────

    def toggle_capture(self):
        if self._running:
            self.stop_capture()
        else:
            self.start_capture()

    def start_capture(self):
        if self._running:
            return
        if self._reader and self._reader.isRunning():
            return
        device = self.device_combo.currentText()
        if not device or device == "(no devices)":
            return
        package = self._selected_package()
        self._running = True
        
        # Update Toggle Button
        self.btn_toggle.setText("Stop")
        self.btn_toggle.setIcon(icons.icon_stop())
        self.btn_toggle.setProperty("role", "stop")
        self.btn_toggle.style().unpolish(self.btn_toggle)
        self.btn_toggle.style().polish(self.btn_toggle)
        
        self.status_changed.emit()

        from src.core.pidcat_runner import get_pidcat_path
        from src.core.settings import SettingsManager
        import sys as _sys

        pidcat_path = get_pidcat_path()
        
        # If package is empty, pidcat shows everything (no filtering)
        cmd = [_sys.executable, pidcat_path]
        if package:
            cmd.append(package)

        if device:
            cmd.extend(['-s', device])

        settings = SettingsManager.load()
        tag_padding = settings.get("tag_padding", 16)
        try:
            tag_padding = int(tag_padding)
        except Exception:
            tag_padding = 16
        if tag_padding >= 4:
            cmd.extend(['-w', str(tag_padding)])
        ignored_tags = settings.get("ignored_tags", [])
        for tag in ignored_tags:
            cmd.extend(['-i', tag])

        env = None

        self._reader = ProcessReader(cmd=cmd, env=env)
        self._reader.line_ready.connect(self._append_line)
        self._reader.finished.connect(self._on_reader_finished)
        self._reader.start()

    def stop_capture(self, wait: bool = False):
        if self._stopping:
            return
        self._stopping = True
        if self._reader:
            try:
                self._reader.stop()
            except Exception:
                pass
        if self._reader and wait:
            self._reader.wait(500)

    def _on_reader_finished(self):
        self._running = False
        self._stopping = False
        
        # Update Toggle Button
        self.btn_toggle.setText("Start")
        self.btn_toggle.setIcon(icons.icon_play())
        self.btn_toggle.setProperty("role", "start")
        self.btn_toggle.style().unpolish(self.btn_toggle)
        self.btn_toggle.style().polish(self.btn_toggle)
        
        self._thread = None
        self._reader = None
        self.status_changed.emit()

        if self._pending_restart:
            self._pending_restart = False
            self.start_capture()

    # ── Log output ────────────────────────────────────────────────────────────

    def _append_line(self, raw: str):
        self._pending_lines.append(raw)
        if not self._flush_timer.isActive():
            self._flush_timer.start()

    def _flush_pending_lines(self):
        if not self._pending_lines:
            self._flush_timer.stop()
            return

        batch = 0
        max_batch = 200
        file_buf = []
        self.log_view.setUpdatesEnabled(False)
        self.log_view.blockSignals(True)
        try:
            while self._pending_lines and batch < max_batch:
                raw = self._pending_lines.popleft()
                file_buf.append(raw)
                self._total_lines += 1
                text = raw.rstrip("\n")
                chunks = _parse_ansi(text)
                tag = _extract_tag(text)
                level = _extract_level(text)
                line_color = _line_color_from_chunks(chunks)
                if tag:
                    if line_color:
                        self._last_tag_color = line_color
                else:
                    if line_color and self._last_tag_color is None:
                        self._last_tag_color = line_color
                    if self._last_tag_color is not None:
                        line_color = self._last_tag_color
                self._raw_lines.append((text, chunks, tag, level, line_color))

                if self.btn_grep.isChecked() and self.search_edit.text():
                    if not self._line_passes_level_filter(level):
                        self._visible_line_count += 1
                        batch += 1
                        continue
                    if not self._line_matches(text, self.search_edit.text()):
                        self._visible_line_count += 1
                        batch += 1
                        continue
                    self._render_line_to_view(text, chunks, line_color)
                else:
                    if not self._line_passes_level_filter(level):
                        self._visible_line_count += 1
                        batch += 1
                        continue
                    self._render_line_to_view(text, chunks, line_color)
                batch += 1
        finally:
            self.log_view.blockSignals(False)
            self.log_view.setUpdatesEnabled(True)
            self.line_number_area.update()
            self.line_number_area.update_width()

        if file_buf and self._log_fp:
            try:
                self._log_fp.write("".join(file_buf))
            except Exception:
                pass

        if self.btn_autoscroll.isChecked():
            self.log_view.setTextCursor(self.log_view.textCursor())
            self.log_view.ensureCursorVisible()
    
    def _render_line_to_view(self, text: str, chunks: list, line_color: QColor | None = None):
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        use_line_color = self._color_line_by_tag and line_color is not None
        for chunk_text, fg, bg, bold, italic in chunks:
            fmt = QTextCharFormat()
            if use_line_color and bg != _DEFAULT_BG:
                fmt.setBackground(line_color)
                fmt.setForeground(_contrast_color(line_color))
            elif use_line_color and fg == _DEFAULT_FG and bg == _DEFAULT_BG:
                fmt.setForeground(line_color)
            else:
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
        
    
    def _line_matches(self, text: str, query: str) -> bool:
        if not query:
            return True
        clean = _ANSI_STRIP.sub("", text)
        try:
            if self.btn_regex.isChecked():
                flags = 0 if self.btn_case.isChecked() else re.IGNORECASE
                return bool(re.search(query, clean, flags))
            else:
                if self.btn_case.isChecked():
                    return query in clean
                return query.lower() in clean.lower()
        except re.error:
            return False

    def _line_passes_level_filter(self, level: str | None) -> bool:
        if not self._level_filters:
            return True
        if not level:
            return False
        return level in self._level_filters

    def _toggle_level_filter(self, level: str, enabled: bool):
        if enabled:
            self._level_filters.add(level)
        else:
            self._level_filters.discard(level)
        self._apply_grep_filter()

    def _start_rebuild_view(self, grep_mode: bool, query: str, highlight: bool):
        self._rebuild_id += 1
        self._rebuild_query = query
        self._rebuild_grep = grep_mode
        self._rebuild_highlight = highlight
        self._rebuild_iter = iter(list(self._raw_lines))

        self.log_view.blockSignals(True)
        self.log_view.clear()
        self._match_positions = []
        self._match_ranges = []
        self._match_idx = 0
        self._visible_line_count = 0

        if not self._rebuild_timer.isActive():
            self._rebuild_timer.start()

    def _rebuild_step(self):
        if self._rebuild_iter is None:
            self._rebuild_timer.stop()
            return
        batch = 0
        max_batch = 300
        while batch < max_batch:
            try:
                text, chunks, tag, level, line_color = next(self._rebuild_iter)
            except StopIteration:
                self._rebuild_iter = None
                self._rebuild_timer.stop()
                self.log_view.blockSignals(False)
                if self._rebuild_highlight:
                    self._apply_highlights(self._rebuild_query)
                self._update_line_count_label()
                if self.btn_autoscroll.isChecked():
                    scrollbar = self.log_view.verticalScrollBar()
                    scrollbar.setValue(scrollbar.maximum())
                return

            if not self._line_passes_level_filter(level):
                self._visible_line_count += 1
                batch += 1
                continue
            if self._rebuild_grep and self._rebuild_query and not self._line_matches(text, self._rebuild_query):
                self._visible_line_count += 1
                batch += 1
                continue
            self._render_line_to_view(text, chunks, line_color)
            batch += 1
    
    def _apply_grep_filter(self):
        query = self.search_edit.text()
        grep_mode = self.btn_grep.isChecked()
        self._start_rebuild_view(grep_mode=grep_mode, query=query, highlight=not grep_mode)

    def _apply_highlights(self, query: str):
        if not query:
            self.log_view.setExtraSelections([])
            self._match_positions = []
            self._match_ranges = []
            self._base_selections = []
            self._match_idx = 0
            self._update_line_count_label()
            return
        
        extra = []
        self._match_ranges = []
        self._match_positions = []
        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#3D1510"))
        fmt.setForeground(QColor("#FFD050"))

        doc = self.log_view.document()
        if self.btn_regex.isChecked():
            flags = 0 if self.btn_case.isChecked() else re.IGNORECASE
            try:
                pattern = re.compile(query, flags)
            except re.error:
                self.log_view.setExtraSelections([])
                self._match_positions = []
                self._match_ranges = []
                self._base_selections = []
                self._match_idx = 0
                self._update_line_count_label()
                return
            text = doc.toPlainText()
            for m in pattern.finditer(text):
                start, end = m.span()
                if start == end:
                    continue
                cursor = QTextCursor(doc)
                cursor.setPosition(start)
                cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
                self._match_positions.append(start)
                self._match_ranges.append((start, end))
                extra.append((cursor, fmt))
        else:
            from PyQt6.QtGui import QTextDocument
            find_flags = QTextDocument.FindFlag(0)
            if self.btn_case.isChecked():
                find_flags |= QTextDocument.FindFlag.FindCaseSensitively
            cursor = doc.find(query, 0, find_flags)
            while not cursor.isNull():
                self._match_positions.append(cursor.position())
                self._match_ranges.append((cursor.selectionStart(), cursor.selectionEnd()))
                extra.append((cursor, fmt))
                cursor = doc.find(query, cursor, find_flags)

        self._base_selections = [self._make_extra(c, f) for c, f in extra]
        self._apply_current_match_highlight()
        self._update_line_count_label()

    def _apply_current_match_highlight(self):
        if not self._base_selections:
            self.log_view.setExtraSelections([])
            return
        selections = list(self._base_selections)
        if 0 <= self._match_idx < len(self._match_ranges):
            start, end = self._match_ranges[self._match_idx]
            if start != end:
                cursor = QTextCursor(self.log_view.document())
                cursor.setPosition(start)
                cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
                fmt = QTextCharFormat()
                fmt.setBackground(QColor("#1E3A8A"))
                fmt.setForeground(QColor("#FFFFFF"))
                selections.append(self._make_extra(cursor, fmt))
        self.log_view.setExtraSelections(selections)

    def _update_line_count_label(self):
        count = len(self._match_positions)
        if count > 0:
            self.lbl_match.setText(f"{min(self._match_idx + 1, count)} / {count}")
        else:
            self.lbl_match.setText("0 / 0")
        self.status_changed.emit()

    def _restore_all_lines(self):
        query = self.search_edit.text()
        self._start_rebuild_view(grep_mode=False, query=query, highlight=True)

    # ── Search / highlight ────────────────────────────────────────────────────

    def _on_search_changed(self):
        self._search_timer.start()

    def _apply_search_now(self):
        if self.btn_grep.isChecked():
            self._apply_grep_filter()
        else:
            self._restore_all_lines()

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
        self._apply_current_match_highlight()
        count = len(self._match_positions)
        self.lbl_match.setText(f"{self._match_idx + 1} / {count}")

    def _toggle_wrap(self, checked: bool):
        mode = QTextEdit.LineWrapMode.WidgetWidth if checked else QTextEdit.LineWrapMode.NoWrap
        self.log_view.setLineWrapMode(mode)

    # ── Actions ───────────────────────────────────────────────────────────────

    def clear_log(self, confirm: bool = True):
        if confirm:
            repl = QMessageBox.question(
                self,
                "Clear Log?",
                "This will clear the visible log view. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if repl != QMessageBox.StandardButton.Yes:
                return
        self.log_view.clear()
        self._total_lines = 0
        self._raw_lines.clear()
        self._pending_lines.clear()
        if self._flush_timer.isActive():
            self._flush_timer.stop()
        if self._log_fp:
            try:
                self._log_fp.close()
            except Exception:
                pass
            try:
                self._log_fp = open(self._log_path, "w", encoding="utf-8", buffering=1)
            except Exception:
                self._log_fp = None
        self._visible_line_count = 0
        self._match_positions = []
        self._match_idx = 0
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
            if Settings().save_screen_only:
                Path(path).write_text(self.log_view.toPlainText(), encoding="utf-8")
                return
            if self._log_fp:
                try:
                    self._log_fp.flush()
                except Exception:
                    pass
            if self._log_path.exists():
                try:
                    shutil.copyfile(self._log_path, path)
                    return
                except Exception:
                    pass
            Path(path).write_text(self.log_view.toPlainText(), encoding="utf-8")

    def refresh_display(self):
        """Refresh display for settings changes (watermark opacity, line numbers)."""
        # Update line numbers visibility
        show_lines = Settings().show_line_numbers
        self.line_number_area.setVisible(show_lines)
        new_color_by_tag = Settings().color_line_by_tag
        if new_color_by_tag != self._color_line_by_tag:
            self._color_line_by_tag = new_color_by_tag
            self._start_rebuild_view(
                grep_mode=self.btn_grep.isChecked(),
                query=self.search_edit.text(),
                highlight=not self.btn_grep.isChecked()
            )
        # Update max lines for log view
        new_max = max(0, int(Settings().log_view_max_lines))
        if new_max != self._max_lines:
            self._max_lines = new_max
            maxlen = self._max_lines if self._max_lines > 0 else None
            if maxlen is not None:
                self._raw_lines = deque(list(self._raw_lines)[-maxlen:], maxlen=maxlen)
            else:
                self._raw_lines = deque(list(self._raw_lines))
            self.log_view.document().setMaximumBlockCount(self._max_lines)
        # Trigger repaint of line numbers and watermark
        self.line_number_area.update()
        self.log_view.viewport().update()

    # ── Public helpers ────────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def line_count(self) -> int:
        """Return actual line count from document text (ground truth)."""
        text = self.log_view.toPlainText()
        if text:
            lines = text.split('\n')
            # Remove empty final line if text ends with newline
            if lines[-1] == '':
                lines.pop()
            return len(lines)
        return 0

    @property
    def current_device(self) -> str:
        return self.device_combo.currentText()

    @property
    def current_package(self) -> str:
        return self._selected_package()
