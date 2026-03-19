"""FadCat main window."""
from __future__ import annotations

import os
import sys
import ctypes
from threading import Thread

try:
    import resource
except ImportError:
    resource = None

from PyQt6.QtCore import Qt, QTimer, QSize, QRect, QPoint, pyqtSignal, QUrl
from PyQt6.QtGui import QAction, QPainter, QColor, QFont, QPolygon, QKeySequence, QCursor, QIcon
from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QToolBar, QStatusBar,
    QLabel, QWidget, QSizePolicy, QTabBar, QPushButton, QInputDialog, QFrame, QHBoxLayout,
    QMenu,
)
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtGui import QDesktopServices

from src.ui import theme, icons
from src.ui.logcat_tab import LogcatTab
from src.core.settings import Settings
from src.core.update_checker import UpdateChecker
from src.ui.update_check_dialog import UpdateCheckDialog


def _process_memory_mb() -> float:
    """Return the current process RSS in MB across supported platforms."""
    if sys.platform == "win32":
        class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = _PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(_PROCESS_MEMORY_COUNTERS)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        result = ctypes.windll.psapi.GetProcessMemoryInfo(
            handle,
            ctypes.byref(counters),
            counters.cb,
        )
        if result:
            return counters.WorkingSetSize / (1024 * 1024)
        return 0.0

    if resource is None:
        return 0.0
    try:
        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform == "darwin":
            return usage / (1024 * 1024)
        return usage / 1024.0
    except Exception:
        return 0.0


# ── Custom Tab Bar with proper close buttons ──────────────────────────────────
class CustomTabBar(QTabBar):
    """QTabBar with properly drawn close buttons and double-click to rename."""
    tabRenameRequested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._close_button_rects: dict[int, QRect] = {}
        self._hover_close_idx: int | None = None
        self.setMouseTracking(True)
        # Set compact height for the tab bar
        self.setFixedHeight(32)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    
    def paintEvent(self, event):
        super().paintEvent(event)
        # Draw close buttons on each tab
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._close_button_rects.clear()
        
        for i in range(self.count()):
            rect = self.tabRect(i)
            if rect.isNull():
                continue
            
            # Draw X button (top-right of tab)
            x_pos = rect.right() - 30
            y_pos = rect.top() + (rect.height() - 14) // 2

            # Close button rect - larger for clickability
            close_rect = QRect(x_pos - 2, y_pos - 2, 18, 18)
            self._close_button_rects[i] = close_rect

            # Hover background for close
            painter.setClipRect(rect)
            if self._hover_close_idx == i:
                painter.setBrush(QColor(255, 90, 90, 40))
                painter.setPen(QColor(255, 90, 90, 80))
                painter.drawRoundedRect(close_rect.adjusted(1, 1, -1, -1), 4, 4)

            # Draw X icon (centered)
            pen_color = QColor("#F07A7A") if self._hover_close_idx == i else QColor("#E05555")
            painter.setPen(pen_color)
            painter.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            painter.drawText(close_rect, Qt.AlignmentFlag.AlignCenter, "×")

    def mouseMoveEvent(self, event):
        pos = event.pos()
        hover_idx = None
        for tab_idx, close_rect in self._close_button_rects.items():
            if close_rect.contains(pos):
                hover_idx = tab_idx
                break
        if hover_idx != self._hover_close_idx:
            self._hover_close_idx = hover_idx
            self.setCursor(
                QCursor(Qt.CursorShape.PointingHandCursor)
                if hover_idx is not None
                else QCursor(Qt.CursorShape.ArrowCursor)
            )
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        if self._hover_close_idx is not None:
            self._hover_close_idx = None
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            self.update()
        super().leaveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Detect clicks on close buttons."""
        pos = event.pos()
        for tab_idx, close_rect in self._close_button_rects.items():
            if close_rect.contains(pos):
                self.tabCloseRequested.emit(tab_idx)
                return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Detect double-clicks to rename tab."""
        idx = self.tabAt(event.pos())
        if idx >= 0:
            self.tabRenameRequested.emit(idx)
        else:
            super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        idx = self.tabAt(event.pos())
        if idx < 0:
            super().contextMenuEvent(event)
            return
        menu = QMenu(self)
        act_rename = menu.addAction("Rename tab…")
        act_hint = menu.addAction("Tip: Double-click a tab to rename")
        act_hint.setEnabled(False)
        action = menu.exec(event.globalPos())
        if action == act_rename:
            self.tabRenameRequested.emit(idx)

    def wheelEvent(self, event):
        delta = event.angleDelta().x() or event.angleDelta().y()
        if delta == 0:
            super().wheelEvent(event)
            return
        step = -1 if delta > 0 else 1
        idx = max(0, min(self.count() - 1, self.currentIndex() + step))
        if idx != self.currentIndex():
            self.setCurrentIndex(idx)
        event.accept()


class ClickableLabel(QLabel):
    """QLabel that handles clicks and opens URLs."""
    
    def __init__(self, text: str, url: str, parent=None):
        super().__init__(text, parent)
        self.url = url
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    
    def mousePressEvent(self, event):
        """Open URL when clicked."""
        QDesktopServices.openUrl(QUrl(self.url))


class LogcatGUI(QMainWindow):
    """Main application window."""
    
    update_available = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("FadCat")
        self.setWindowIcon(icons.app_icon())
        self.resize(980, 640)
        self.setMinimumSize(800, 550)
        self.setStyleSheet(theme.get_stylesheet())
        self._center_on_screen()

        # Initialize update state
        self._update_available = False
        self._latest_version = None

        self._build_menubar()
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()

        # Status refresh timer
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(2000)
        self._status_timer.timeout.connect(self._refresh_statusbar)
        self._status_timer.start()

        # Restore previous sessions or start fresh
        self._load_sessions()
        
        # Connect update signal to show badge
        self.update_available.connect(self._show_update_badge)
        
        # Check for updates asynchronously (non-blocking)
        self._check_updates_async()

    def _center_on_screen(self):
        screen = self.screen()
        if screen is None:
            return
        geom = screen.availableGeometry()
        size = self.size()
        x = geom.x() + (geom.width() - size.width()) // 2
        y = geom.y() + (geom.height() - size.height()) // 2
        self.move(x, y)

    # ── Menubar ───────────────────────────────────────────────────────────────

    def _build_menubar(self):
        mb = self.menuBar()

        # File Menu
        file_menu = mb.addMenu("File")
        act_new = file_menu.addAction(icons.icon_new_tab(), "New Tab\t⌘T")
        act_new.setShortcut(QKeySequence("Ctrl+T"))
        act_new.triggered.connect(self.add_new_tab)
        act_close = file_menu.addAction(icons.icon_close(), "Close Tab\t⌘W")
        act_close.setShortcut(QKeySequence("Ctrl+W"))
        act_close.triggered.connect(self._close_current_tab)
        file_menu.addSeparator()
        act_quit = file_menu.addAction("Quit\t⌘Q")
        act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        act_quit.triggered.connect(self.close)

        # View Menu
        view_menu = mb.addMenu("View")
        act_settings = view_menu.addAction(icons.icon_settings(), "Settings…\t⌘,")
        act_settings.setShortcut(QKeySequence("Ctrl+,"))
        act_settings.triggered.connect(self.open_settings)

    # ── Toolbar ───────────────────────────────────────────────────────────────

    def _build_toolbar(self):
        tb = QToolBar("Main", self)
        tb.setMovable(False)
        tb.setStyleSheet("QToolBar { background: #242424; border-bottom: 1px solid #333333; padding: 6px 10px; spacing: 10px; }")
        self.addToolBar(tb)

        # New Tab Button
        btn_new = QPushButton("New Tab")
        btn_new.setIcon(icons.icon_new_tab())
        btn_new.setToolTip("New Tab (⌘T)")
        btn_new.clicked.connect(self.add_new_tab)
        btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        tb.addWidget(btn_new)

        # Left divider line (expandable)
        left_divider = QFrame()
        left_divider.setFrameShape(QFrame.Shape.HLine)
        left_divider.setFrameShadow(QFrame.Shadow.Plain)
        left_divider.setStyleSheet("color: #444444;")
        left_divider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        tb.addWidget(left_divider)

        # Branding / Logo area - centered
        # Resolve icon path for bundled or dev environments
        import os
        from pathlib import Path
        icon_dir = Path(__file__).parent.parent / 'icons'
        logo_path = str(icon_dir / 'fadcat-logo.svg')
        
        # Fallback if not found
        if not Path(logo_path).exists():
            # Try alternative path for bundled app
            logo_path = str(Path(__file__).parent.parent.parent / 'Resources' / 'src' / 'icons' / 'fadcat-logo.svg')
        
        svg_logo = QSvgWidget(logo_path)
        svg_logo.setFixedSize(100, 33)
        svg_logo.setStyleSheet("background: transparent;")
        tb.addWidget(svg_logo)

        # Right divider line (expandable)
        right_divider = QFrame()
        right_divider.setFrameShape(QFrame.Shape.HLine)
        right_divider.setFrameShadow(QFrame.Shadow.Plain)
        right_divider.setStyleSheet("color: #444444;")
        right_divider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        tb.addWidget(right_divider)

        # Settings Button
        btn_settings = QPushButton("Settings")
        btn_settings.setIcon(icons.icon_settings())
        btn_settings.setToolTip("Settings (⌘,)")
        btn_settings.clicked.connect(self.open_settings)
        btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        tb.addWidget(btn_settings)

    def _create_toolbar_spacer(self) -> QWidget:
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        return spacer

    # ── Central widget ─────────────────────────────────────────────────────────

    def _build_central(self):
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setTabsClosable(False)  # Close handled by CustomTabBar
        self.tabs.setMovable(True)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setDocumentMode(True)
        self.tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self.tabs.setTabBarAutoHide(False)
        
        # Custom tab bar for better aesthetics and functionality
        custom_tabbar = CustomTabBar()
        custom_tabbar.tabCloseRequested.connect(self._on_tab_close_requested)
        custom_tabbar.tabRenameRequested.connect(self._on_tab_rename_requested)
        custom_tabbar.setUsesScrollButtons(True)
        custom_tabbar.setExpanding(False)
        custom_tabbar.setDrawBase(False)
        self.tabs.setTabBar(custom_tabbar)

        # Clear corner widgets to allow built-in scrollers to show correctly
        self.tabs.setCornerWidget(None, Qt.Corner.TopLeftCorner)
        self.tabs.setCornerWidget(None, Qt.Corner.TopRightCorner)
        
        self.tabs.currentChanged.connect(self._refresh_statusbar)
        self.tabs.currentChanged.connect(self._save_sessions)
        self.setCentralWidget(self.tabs)

    # ── Status bar ─────────────────────────────────────────────────────────────

    def _build_statusbar(self):
        sb = QStatusBar(self)
        self.setStatusBar(sb)
        sb.setStyleSheet("QStatusBar { background: #242424; border-top: 1px solid #444444; }")

        self.lbl_status_state = QLabel("Idle")
        self.lbl_status_state.setStyleSheet("color: #888888; padding: 0 2px; font-size: 12px; background: transparent;")
        self.lbl_status_device = QLabel("No device")
        self.lbl_status_device.setStyleSheet("color: #888888; padding: 0 2px; font-size: 12px; background: transparent;")
        self.lbl_status_lines = QLabel("0 lines")
        self.lbl_status_lines.setStyleSheet("color: #888888; padding: 0 1px; font-size: 12px; background: transparent;")
        self.lbl_status_lines.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.lbl_status_lines.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_status_mem = QLabel("— MB")
        self.lbl_status_mem.setStyleSheet("color: #888888; padding: 0 2px; font-size: 12px; background: transparent;")
        fm = self.lbl_status_lines.fontMetrics()
        self.lbl_status_lines.setMinimumWidth(fm.horizontalAdvance("88.8k / 88.8k lines") + 4)
        self.lbl_status_mem.setFixedWidth(fm.horizontalAdvance("888.8 MB") + 4)

        self._sb_state_icon, state_item = self._sb_item(icons.icon_status(), self.lbl_status_state, left_margin=12)
        sb.addWidget(state_item)
        
        # Small divider after status state
        sb.addWidget(self._sb_sep_small())
        
        self._sb_device_icon, device_item = self._sb_item(icons.icon_device(), self.lbl_status_device)
        sb.addWidget(device_item)
        
        # Full height divider after device
        full_divider = QFrame()
        full_divider.setFrameShape(QFrame.Shape.VLine)
        full_divider.setFrameShadow(QFrame.Shadow.Plain)
        full_divider.setStyleSheet("color: #333333;")
        sb.addWidget(full_divider)
        
        self._sb_pause_badge = QPushButton("Paused")
        self._sb_pause_badge.setObjectName("pauseBadge")
        self._sb_pause_badge.setFixedHeight(22)
        self._sb_pause_badge.setVisible(False)
        self._sb_pause_badge.setToolTip("Auto-scroll is off. New logs are buffering. Click to resume.")
        self._sb_pause_badge.setStyleSheet(
            "QPushButton#pauseBadge { background: #2B1A1A; color: #FF6B6B; border: 1px solid #7A2A2A; "
            "border-radius: 9px; padding: 1px 6px; font-size: 10px; }"
            "QPushButton#pauseBadge:hover { background: #331C1C; }"
        )
        self._sb_pause_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sb_pause_badge.clicked.connect(self._resume_from_pause)
        
        # Small divider after pause badge (only visible when pause badge is visible)
        self._sb_pause_divider = QLabel("|")
        self._sb_pause_divider.setStyleSheet("color: #333333; padding: 0 1px;")
        self._sb_pause_divider.setVisible(False)
        
        # Update available badge
        self._sb_update_badge = QPushButton("⬆ Update Available")
        self._sb_update_badge.setObjectName("updateBadge")
        self._sb_update_badge.setFixedHeight(22)
        self._sb_update_badge.setVisible(False)
        self._sb_update_badge.setToolTip("New version available. Click to update.")
        self._sb_update_badge.setStyleSheet(
            "QPushButton#updateBadge { background: #1a2b2a; color: #44dd88; border: 1px solid #2a7a3a; "
            "border-radius: 9px; padding: 1px 6px; font-size: 10px; }"
            "QPushButton#updateBadge:hover { background: #1c331c; }"
        )
        self._sb_update_badge.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sb_update_badge.clicked.connect(self._on_update_badge_clicked)
        
        # Small divider after update badge (only visible when update badge is visible)
        self._sb_update_divider = QLabel("|")
        self._sb_update_divider.setStyleSheet("color: #333333; padding: 0 1px;")
        self._sb_update_divider.setVisible(False)
        
        # Copyright and website link (left side)
        copyright_label = QLabel("© 2024–2026")
        copyright_label.setStyleSheet("color: #666666; padding: 0 2px; font-size: 10px;")
        self._sb_copyright = copyright_label
        sb.addWidget(copyright_label)
        dot_sep = QLabel("•")
        dot_sep.setStyleSheet("color: #444444; padding: 0 2px;")
        self._sb_copyright_dot = dot_sep
        sb.addWidget(dot_sep)
        website_label = ClickableLabel("fadseclab.com", "https://fadseclab.com")
        website_label.setStyleSheet("color: #ff6b6b; padding: 0 2px; font-size: 10px;")
        self._sb_website = website_label
        sb.addWidget(website_label)
        
        self._sb_lines_icon, lines_item = self._sb_item(icons.icon_lines(), self.lbl_status_lines)
        sb.addPermanentWidget(self._sb_pause_badge)
        sb.addPermanentWidget(self._sb_pause_divider)
        sb.addPermanentWidget(self._sb_update_badge)
        sb.addPermanentWidget(self._sb_update_divider)
        sb.addPermanentWidget(lines_item)
        sb.addPermanentWidget(self._sb_sep())
        self._sb_mem_icon, mem_item = self._sb_item(icons.icon_memory(), self.lbl_status_mem)
        sb.addPermanentWidget(mem_item)
        self._update_statusbar_layout(self.width())

    @staticmethod
    def _sb_sep() -> QLabel:
        sep = QLabel("|")
        sep.setStyleSheet("color: #333333; padding: 0 1px;")
        return sep

    @staticmethod
    def _sb_sep_small() -> QLabel:
        sep = QLabel("•")
        sep.setStyleSheet("color: #333333; padding: 0 2px;")
        return sep

    @staticmethod
    def _sb_item(icon: QIcon, label: QLabel, left_margin: int = 6) -> tuple[QLabel, QWidget]:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(left_margin, 0, 0, 0)
        lay.setSpacing(2)
        ic = QLabel()
        ic.setPixmap(icon.pixmap(14, 14))
        lay.addWidget(ic)
        lay.addWidget(label)
        return ic, w

    def _refresh_statusbar(self):
        tab = self._current_tab()
        if tab is None:
            self.lbl_status_device.setText("No device")
            self.lbl_status_lines.setText("0 lines")
            self.lbl_status_state.setText("Idle")
            self.lbl_status_mem.setText("— MB")
            if hasattr(self, "_sb_pause_badge"):
                self._sb_pause_badge.setVisible(False)
            return
        self.lbl_status_device.setText(tab.current_device or "—")
        total = tab.total_line_count
        visible = tab.line_count
        def _fmt(n: int) -> str:
            if n >= 1_000_000:
                return f"{n/1_000_000:.1f}M".rstrip("0").rstrip(".")
            if n >= 1000:
                return f"{n/1000:.1f}k".rstrip("0").rstrip(".")
            return str(n)
        if total >= visible:
            self.lbl_status_lines.setText(f"{_fmt(visible)} / {_fmt(total)} lines")
            self.lbl_status_lines.setToolTip(f"Visible lines: {visible:,}\nTotal captured lines: {total:,}")
        else:
            self.lbl_status_lines.setText(f"{_fmt(visible)} lines")
            self.lbl_status_lines.setToolTip(f"Visible lines: {visible:,}")
        self.lbl_status_state.setText("Running" if tab.is_running else "Idle")
        self.lbl_status_state.setTextFormat(Qt.TextFormat.PlainText)
        # Update running icon color
        status_icon = icons.icon_status_running() if tab.is_running else icons.icon_status()
        if hasattr(self, "_sb_state_icon"):
            self._sb_state_icon.setPixmap(status_icon.pixmap(14, 14))
        mem_mb = self._mem_mb()
        self.lbl_status_mem.setText(f"{mem_mb:.1f} MB")
        self.lbl_status_mem.setToolTip(f"Memory used by FadCat: {mem_mb:.1f} MB")
        if hasattr(self, "_sb_state_icon"):
            self._sb_state_icon.setToolTip("Status: Running" if tab.is_running else "Status: Idle")
        if hasattr(self, "_sb_device_icon"):
            self._sb_device_icon.setToolTip(f"Device: {tab.current_device or '—'}")
        if hasattr(self, "_sb_pause_badge"):
            if tab.is_paused:
                def _fmt_small(n: int) -> str:
                    if n >= 1_000_000:
                        return f"{n/1_000_000:.1f}M".rstrip("0").rstrip(".")
                    if n >= 100_000:
                        return f"{n/1000:.0f}k"
                    if n >= 1000:
                        return f"{n/1000:.1f}k".rstrip("0").rstrip(".")
                    return str(n)
                text = f"Paused • {_fmt_small(tab.paused_count)} new" if tab.paused_count else "Paused"
                self._sb_pause_badge.setText(text)
                self._sb_pause_badge.setVisible(True)
                self._sb_pause_divider.setVisible(True)
            else:
                self._sb_pause_badge.setVisible(False)
                self._sb_pause_divider.setVisible(False)
        self._update_statusbar_layout(self.width())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_statusbar_layout(event.size().width())

    def _update_statusbar_layout(self, width: int):
        compact = width < 860
        tight = width < 720
        if compact:
            self.lbl_status_state.setText("")
            self.lbl_status_device.setText("")
        else:
            if not self.lbl_status_state.text():
                self.lbl_status_state.setText("Running" if (self._current_tab() and self._current_tab().is_running) else "Idle")
            if not self.lbl_status_device.text():
                self.lbl_status_device.setText(self._current_tab().current_device if self._current_tab() else "—")
        self.lbl_status_state.setVisible(not tight)
        self.lbl_status_device.setVisible(not tight)
        if hasattr(self, "_sb_copyright"):
            self._sb_copyright.setVisible(not tight)
        if hasattr(self, "_sb_copyright_dot"):
            self._sb_copyright_dot.setVisible(not tight)
        if hasattr(self, "_sb_website"):
            self._sb_website.setVisible(not tight)

    def _resume_from_pause(self):
        tab = self._current_tab()
        if tab is not None:
            tab.resume_from_pause()

    @staticmethod
    def _mem_mb() -> float:
        return _process_memory_mb()

    # ── Tab helpers ────────────────────────────────────────────────────────────

    def add_new_tab(self, _: bool | None = None, title: str | None = None):
        """Creates a new logcat capture session in a new tab."""
        tab = LogcatTab()
        tab.status_changed.connect(self._refresh_statusbar)
        tab.device_selected.connect(lambda d: self._on_tab_device_selected(tab, d))
        
        idx = self.tabs.count()
        if title is None:
            title = f"Session {idx + 1}"
        
        self.tabs.addTab(tab, title)
        self.tabs.setCurrentWidget(tab)
        self._refresh_statusbar()
        self._save_sessions()

    def _on_tab_device_selected(self, tab: LogcatTab, device: str):
        """When a device is selected, update tab title if a custom name exists."""
        idx = self.tabs.indexOf(tab)
        if idx < 0: return
        
        s = Settings()
        dev_names = s.device_names
        if device in dev_names:
            self.tabs.setTabText(idx, dev_names[device])

    def _close_current_tab(self):
        idx = self.tabs.currentIndex()
        if idx >= 0:
            self._on_tab_close_requested(idx)

    def _on_tab_close_requested(self, idx: int):
        tab = self.tabs.widget(idx)
        if isinstance(tab, LogcatTab) and tab.is_running:
            tab.stop_capture()
        self.tabs.removeTab(idx)
        if self.tabs.count() == 0:
            self.add_new_tab()
        self._save_sessions()

    def _on_tab_rename_requested(self, idx: int):
        """User double-clicked tab to rename it."""
        old_title = self.tabs.tabText(idx)
        new_title, ok = QInputDialog.getText(
            self, "Rename Session", "Enter new session name:",
            text=old_title
        )
        if ok and new_title.strip():
            title = new_title.strip()
            self.tabs.setTabText(idx, title)
            
            # Associate this title with current device if possible
            tab = self.tabs.widget(idx)
            if isinstance(tab, LogcatTab):
                dev = tab.current_device
                if dev and dev != "(no devices)":
                    s = Settings()
                    names = s.device_names
                    names[dev] = title
                    s.device_names = names
                    s.save()
            
            self._save_sessions()



    def _save_sessions(self):
        """Persist current session titles to settings."""
        titles = [self.tabs.tabText(i) for i in range(self.tabs.count())]
        s = Settings()
        s.session_titles = titles
        s.save()

    def _load_sessions(self):
        """Restore sessions from settings."""
        s = Settings()
        titles = s.session_titles
        if not titles:
            self.add_new_tab()
        else:
            for t in titles:
                self.add_new_tab(title=t)
            # Switch back to first tab
            self.tabs.setCurrentIndex(0)

    def _current_tab(self) -> LogcatTab | None:
        w = self.tabs.currentWidget()
        return w if isinstance(w, LogcatTab) else None

    # ── Settings ───────────────────────────────────────────────────────────────

    def open_settings(self):
        """Open the application settings dialog."""
        print("[FadCat] open_settings() called")
        from src.ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self)
        
        # Connect real-time preview updates
        def on_settings_changed():
            print("[FadCat] on_settings_changed() triggered")
            for i in range(self.tabs.count()):
                w = self.tabs.widget(i)
                if isinstance(w, LogcatTab):
                    w.refresh_display()
        
        dlg.settings_changed.connect(on_settings_changed)
        
        if dlg.exec():
            print("[FadCat] Settings dialog accepted, saving...")
            # Refresh all tabs with new settings
            for i in range(self.tabs.count()):
                w = self.tabs.widget(i)
                if isinstance(w, LogcatTab):
                    w.reload_packages()

    def _check_updates_async(self):
        """Check for updates in background without blocking UI"""
        from src.version import __version__
        
        def check():
            try:
                result = UpdateChecker.check_for_updates(__version__)
                # Only proceed if no error
                if not result.is_error and result.has_update:
                    self._update_available = True
                    self._latest_version = result.latest_version
                    # Emit signal to update badge on main thread
                    self.update_available.emit()
            except (OSError, ValueError, AttributeError):
                # Silently ignore any exception during background check
                pass
        
        # Run check in background thread
        thread = Thread(target=check, daemon=True)
        thread.start()

    def _show_update_badge(self):
        """Show the update available badge in statusbar"""
        if hasattr(self, "_sb_update_badge"):
            self._sb_update_badge.setVisible(True)
            self._sb_update_divider.setVisible(True)

    def _on_update_badge_clicked(self):
        """When update badge is clicked, open update check dialog"""
        dlg = UpdateCheckDialog(self)
        dlg.exec()
