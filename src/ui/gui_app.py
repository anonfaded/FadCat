"""FadCat main window."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, QSize, QRect, QPoint
from PyQt6.QtGui import QAction, QPainter, QColor, QFont, QPolygon
from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QToolBar, QStatusBar,
    QLabel, QWidget, QSizePolicy, QTabBar,
)

from src.ui import theme, icons
from src.ui.logcat_tab import LogcatTab


# ── Custom Tab Bar with proper close buttons ──────────────────────────────────
class CustomTabBar(QTabBar):
    """QTabBar with properly drawn close buttons."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._close_button_rects: dict[int, QRect] = {}
    
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
            x_pos = rect.right() - 20
            y_pos = rect.top() + (rect.height() - 14) // 2
            
            # Close button rect - larger for clickability
            close_rect = QRect(x_pos - 2, y_pos - 2, 18, 18)
            self._close_button_rects[i] = close_rect
            
            # Draw X icon (bigger)
            painter.setPen(QColor("#E8302A"))
            painter.setFont(QFont("Arial", 14, QFont.Weight.Bold))
            painter.drawText(close_rect, Qt.AlignmentFlag.AlignCenter, "×")
    
    def mouseReleaseEvent(self, event):
        """Detect clicks on close buttons."""
        pos = event.pos()
        for tab_idx, close_rect in self._close_button_rects.items():
            if close_rect.contains(pos):
                self.tabCloseRequested.emit(tab_idx)
                return
        super().mouseReleaseEvent(event)


class LogcatGUI(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("FadCat")
        self.resize(1200, 780)
        self.setMinimumSize(800, 550)
        self.setStyleSheet(theme.get_stylesheet())

        self._build_menubar()
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()

        self._status_timer = QTimer(self)
        self._status_timer.setInterval(2000)
        self._status_timer.timeout.connect(self._refresh_statusbar)
        self._status_timer.start()

        self.add_new_tab()

    # ── Menubar ───────────────────────────────────────────────────────────────

    def _build_menubar(self):
        mb = self.menuBar()

        file_menu = mb.addMenu("File")
        act_new = file_menu.addAction(icons.icon_new_tab(), "New Tab")
        act_new.setShortcut("Ctrl+T")
        act_new.triggered.connect(self.add_new_tab)
        act_close = file_menu.addAction(icons.icon_close(), "Close Tab")
        act_close.setShortcut("Ctrl+W")
        act_close.triggered.connect(self._close_current_tab)
        file_menu.addSeparator()
        act_quit = file_menu.addAction("Quit")
        act_quit.setShortcut("Ctrl+Q")
        act_quit.triggered.connect(self.close)

        view_menu = mb.addMenu("View")
        act_settings = view_menu.addAction(icons.icon_settings(), "Settings…")
        act_settings.setShortcut("Ctrl+,")
        act_settings.triggered.connect(self.open_settings)

    # ── Toolbar ───────────────────────────────────────────────────────────────

    def _build_toolbar(self):
        tb = QToolBar("Main", self)
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(tb)

        act_new = QAction(icons.icon_new_tab(), "New Tab", self)
        act_new.setToolTip("Open a new logcat tab  (Ctrl+T)")
        act_new.triggered.connect(self.add_new_tab)
        tb.addAction(act_new)

        tb.addSeparator()

        act_settings = QAction(icons.icon_settings(), "Settings", self)
        act_settings.setToolTip("Open settings  (Ctrl+,)")
        act_settings.triggered.connect(self.open_settings)
        tb.addAction(act_settings)

        # Right-align spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        self.lbl_toolbar_hint = QLabel("")
        self.lbl_toolbar_hint.setStyleSheet("color: #888888; font-size: 11px; padding-right: 8px;")
        tb.addWidget(self.lbl_toolbar_hint)

    # ── Central widget ─────────────────────────────────────────────────────────

    def _build_central(self):
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setTabsClosable(False)  # Handle close manually via custom tab bar
        self.tabs.setMovable(True)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setDocumentMode(False)
        
        # Use custom tab bar with proper close buttons
        custom_tabbar = CustomTabBar()
        custom_tabbar.tabCloseRequested.connect(self._on_tab_close_requested)
        custom_tabbar.setExpanding(False)   # Left-align tabs instead of stretching them
        self.tabs.setTabBar(custom_tabbar)
        
        self.tabs.currentChanged.connect(self._refresh_statusbar)
        self.setCentralWidget(self.tabs)

    # ── Status bar ─────────────────────────────────────────────────────────────

    def _build_statusbar(self):
        sb = QStatusBar(self)
        self.setStatusBar(sb)

        self.lbl_status_device = QLabel("No device")
        self.lbl_status_device.setStyleSheet("padding: 0 8px;")
        self.lbl_status_lines = QLabel("0 lines")
        self.lbl_status_lines.setStyleSheet("padding: 0 8px;")
        self.lbl_status_state = QLabel("Idle")
        self.lbl_status_state.setStyleSheet("padding: 0 8px;")

        sb.addWidget(self.lbl_status_state)
        sb.addWidget(self._sb_sep())
        sb.addWidget(self.lbl_status_device)
        sb.addWidget(self._sb_sep())
        sb.addPermanentWidget(self.lbl_status_lines)

    @staticmethod
    def _sb_sep() -> QLabel:
        sep = QLabel("|")
        sep.setStyleSheet("color: #333333; padding: 0 2px;")
        return sep

    def _refresh_statusbar(self):
        tab = self._current_tab()
        if tab is None:
            self.lbl_status_device.setText("No device")
            self.lbl_status_lines.setText("0 lines")
            self.lbl_status_state.setText("Idle")
            return
        self.lbl_status_device.setText(tab.current_device or "—")
        self.lbl_status_lines.setText(f"{tab.line_count:,} lines")
        self.lbl_status_state.setText(
            '<span style="color:#3CB371">● Running</span>' if tab.is_running
            else "Idle"
        )
        self.lbl_status_state.setTextFormat(Qt.TextFormat.RichText)

    # ── Tab helpers ────────────────────────────────────────────────────────────

    def add_new_tab(self):
        tab = LogcatTab()
        tab.status_changed.connect(self._refresh_statusbar)
        idx = self.tabs.count()
        self.tabs.addTab(tab, f"Session {idx + 1}")
        self.tabs.setCurrentWidget(tab)
        self._refresh_statusbar()

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

    def _current_tab(self) -> LogcatTab | None:
        w = self.tabs.currentWidget()
        return w if isinstance(w, LogcatTab) else None

    # ── Settings ───────────────────────────────────────────────────────────────

    def open_settings(self):
        from src.ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self)
        if dlg.exec():
            for i in range(self.tabs.count()):
                w = self.tabs.widget(i)
                if isinstance(w, LogcatTab):
                    w.reload_packages()

