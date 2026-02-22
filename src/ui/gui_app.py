"""
FadCat — Main window
"""
import sys
from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QToolBar, QStatusBar, QLabel, QApplication,
    QDialog, QMessageBox, QSizePolicy
)
from PyQt6.QtGui import QAction, QIcon, QKeySequence
from PyQt6.QtCore import Qt, QSize, QTimer

from src.ui.logcat_tab import LogcatTab
from src.ui.settings_dialog import SettingsDialog
from src.ui.theme import get_stylesheet
from src.ui.icons import (
    icon_new_tab, icon_settings, icon_info
)


class LogcatGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FadCat")
        self.resize(1200, 780)
        self.setMinimumSize(800, 500)
        self.setStyleSheet(get_stylesheet())

        self._build_menubar()
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()

        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_statusbar)
        self._status_timer.start(2000)

        self.add_new_tab()

    # ── construction ────────────────────────────────────────────────────────

    def _build_menubar(self):
        mb = self.menuBar()

        file_menu = mb.addMenu("File")

        act_new = QAction("New Session", self)
        act_new.setShortcut(QKeySequence("Ctrl+T"))
        act_new.triggered.connect(self.add_new_tab)
        file_menu.addAction(act_new)

        act_close = QAction("Close Session", self)
        act_close.setShortcut(QKeySequence("Ctrl+W"))
        act_close.triggered.connect(lambda: self.close_tab(self.tabs.currentIndex()))
        file_menu.addAction(act_close)

        file_menu.addSeparator()

        act_settings = QAction("Settings\u2026", self)
        act_settings.setShortcut(QKeySequence("Ctrl+,"))
        act_settings.triggered.connect(self.open_settings)
        file_menu.addAction(act_settings)

        file_menu.addSeparator()

        act_quit = QAction("Quit FadCat", self)
        act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        act_quit.triggered.connect(QApplication.instance().quit)
        file_menu.addAction(act_quit)

        view_menu = mb.addMenu("View")

        self.act_autoscroll = QAction("Auto-scroll", self)
        self.act_autoscroll.setCheckable(True)
        self.act_autoscroll.setChecked(True)
        self.act_autoscroll.setShortcut(QKeySequence("Ctrl+Shift+A"))
        self.act_autoscroll.triggered.connect(self._toggle_autoscroll)
        view_menu.addAction(self.act_autoscroll)

        self.act_wrap = QAction("Wrap Lines", self)
        self.act_wrap.setCheckable(True)
        self.act_wrap.setChecked(True)
        self.act_wrap.setShortcut(QKeySequence("Ctrl+Shift+W"))
        self.act_wrap.triggered.connect(self._toggle_wrap)
        view_menu.addAction(self.act_wrap)

        view_menu.addSeparator()

        act_clear = QAction("Clear Logs", self)
        act_clear.setShortcut(QKeySequence("Ctrl+L"))
        act_clear.triggered.connect(self._clear_current)
        view_menu.addAction(act_clear)

        help_menu = mb.addMenu("Help")
        act_about = QAction("About FadCat", self)
        act_about.triggered.connect(self.show_about)
        help_menu.addAction(act_about)

    def _build_toolbar(self):
        tb = QToolBar("Main Toolbar")
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))
        self.addToolBar(tb)

        act_new = QAction(icon_new_tab(), "New Session", self)
        act_new.setToolTip("New session  Ctrl+T")
        act_new.triggered.connect(self.add_new_tab)
        tb.addAction(act_new)

        tb.addSeparator()

        act_settings = QAction(icon_settings(), "Settings", self)
        act_settings.setToolTip("Settings  Ctrl+,")
        act_settings.triggered.connect(self.open_settings)
        tb.addAction(act_settings)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        self.tb_status = QLabel("No devices")
        self.tb_status.setProperty("muted", True)
        self.tb_status.setContentsMargins(0, 0, 8, 0)
        tb.addWidget(self.tb_status)

    def _build_central(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs)

    def _build_statusbar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)
        self.sb_device  = QLabel("No device")
        self.sb_package = QLabel("")
        self.sb_lines   = QLabel("")
        self.sb_status  = QLabel("")
        for lbl in (self.sb_device, self.sb_package, self.sb_lines, self.sb_status):
            sb.addPermanentWidget(lbl)
        sb.addPermanentWidget(QLabel("FadCat v1.0"))

    # ── tab management ───────────────────────────────────────────────────────

    def add_new_tab(self):
        tab = LogcatTab(self)
        tab.status_changed.connect(self._refresh_statusbar)
        n = self.tabs.count() + 1
        idx = self.tabs.addTab(tab, f"Session {n}")
        self.tabs.setCurrentIndex(idx)
        return tab

    def close_tab(self, index: int):
        if self.tabs.count() <= 1:
            return
        widget = self.tabs.widget(index)
        widget.stop_logcat()
        self.tabs.removeTab(index)
        widget.deleteLater()

    def _on_tab_changed(self, _index: int):
        self._refresh_statusbar()

    def _current_tab(self):
        w = self.tabs.currentWidget()
        return w if isinstance(w, LogcatTab) else None

    # ── menu actions ─────────────────────────────────────────────────────────

    def open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            for i in range(self.tabs.count()):
                tab = self.tabs.widget(i)
                if isinstance(tab, LogcatTab):
                    tab.apply_settings(dlg.settings)

    def _toggle_autoscroll(self, checked: bool):
        tab = self._current_tab()
        if tab:
            tab.auto_scroll_btn.setChecked(checked)

    def _toggle_wrap(self, checked: bool):
        tab = self._current_tab()
        if tab:
            tab.wrap_btn.setChecked(checked)
            tab.toggle_wrap(checked)

    def _clear_current(self):
        tab = self._current_tab()
        if tab:
            tab.clear_logs()

    def show_about(self):
        QMessageBox.about(
            self,
            "About FadCat",
            "<h3>FadCat</h3>"
            "<p>A modern Android logcat viewer built on pidcat.</p>"
            "<p>Licensed under the Apache License 2.0.</p>"
        )

    # ── status bar refresh ───────────────────────────────────────────────────

    def _refresh_statusbar(self):
        tab = self._current_tab()
        if tab is None:
            self.sb_device.setText("No device")
            self.sb_package.setText("")
            self.sb_lines.setText("")
            self.sb_status.setText("")
            self.tb_status.setText("No devices")
            return

        device  = tab.device_cb.currentText() or "No device"
        package = tab.package_cb.currentText() or "\u2014"
        n_lines = tab.log_widget.document().blockCount()
        running = tab.reader is not None and tab.reader.isRunning()

        self.sb_device.setText(f"Device: {device}")
        self.sb_package.setText(f"   Package: {package}   ")
        self.sb_lines.setText(f"Lines: {n_lines}   ")
        self.sb_status.setText("\u25cf Running" if running else "\u25cb Idle")
        self.sb_status.setStyleSheet(
            f"color: {'#30D158' if running else '#8E8E93'};"
        )

        pkg_short = package.split(".")[-1] if "." in package else package
        self.tabs.setTabText(
            self.tabs.currentIndex(),
            pkg_short or f"Session {self.tabs.currentIndex()+1}"
        )

        devices = tab.devices
        n = len(devices)
        self.tb_status.setText(
            f"{n} device{'s' if n != 1 else ''} connected" if n else "No devices"
        )

