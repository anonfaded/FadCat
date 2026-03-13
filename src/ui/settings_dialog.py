"""Settings dialog — manage saved packages and ignore list."""
from __future__ import annotations

import json
import subprocess
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QListWidget, QListWidgetItem, QPushButton,
    QComboBox, QLineEdit, QLabel, QDialogButtonBox,
    QSizePolicy, QTabWidget, QWidget, QMessageBox,
    QCheckBox, QSlider, QSpinBox, QTextEdit, QScrollArea,
)

from src.core.settings import Settings, DEFAULT_SETTINGS
from src.ui import icons


class SettingsDialog(QDialog):
    # Signal to notify that display settings have changed (for real-time preview)
    settings_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(520, 500)
        self._settings = Settings()
        self.mcp_process = None  # Initialize MCP server process
        self._build_ui()
        self._populate()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        # ── Tab 1: Packages ───────────────────────────────────────────────────
        pkg_tab = QWidget()
        pkg_lay = QVBoxLayout(pkg_tab)
        
        grp_pkg = QGroupBox("Saved Packages")
        grp_pkg_lay = QVBoxLayout(grp_pkg)
        
        self.pkg_list = QListWidget()
        self.pkg_list.setFixedHeight(180)
        self.pkg_list.itemSelectionChanged.connect(self._on_pkg_selection)
        grp_pkg_lay.addWidget(self.pkg_list)

        add_row = QHBoxLayout()
        self.edit_add = QLineEdit()
        self.edit_add.setPlaceholderText("com.example.app")
        self.edit_add.returnPressed.connect(self._add_package)
        add_row.addWidget(self.edit_add, stretch=1)
        btn_add = QPushButton("Add")
        btn_add.setProperty("role", "primary")
        btn_add.setFixedWidth(64)
        btn_add.clicked.connect(self._add_package)
        add_row.addWidget(btn_add)
        grp_pkg_lay.addLayout(add_row)

        self.btn_remove_pkg = QPushButton("Remove Selected")
        self.btn_remove_pkg.setEnabled(False)
        self.btn_remove_pkg.clicked.connect(self._remove_selected_pkg)
        grp_pkg_lay.addWidget(self.btn_remove_pkg)
        
        pkg_lay.addWidget(grp_pkg)

        def_row = QHBoxLayout()
        def_row.addWidget(QLabel("Default package:"))
        self.default_combo = QComboBox()
        self.default_combo.setMinimumWidth(240)
        def_row.addWidget(self.default_combo, stretch=1)
        pkg_lay.addLayout(def_row)
        pkg_lay.addStretch()

        self.tabs.addTab(pkg_tab, "Packages")

        # ── Tab 2: Ignore List ────────────────────────────────────────────────
        ign_tab = QWidget()
        ign_lay = QVBoxLayout(ign_tab)

        help_lbl = QLabel(
            "Lines containing these tags will be hidden from the log view. "
            "Great for filtering out system noise (like GPU or Bluetooth spam)."
        )
        help_lbl.setWordWrap(True)
        help_lbl.setStyleSheet("color: #888888; font-size: 12px; margin-bottom: 8px;")
        ign_lay.addWidget(help_lbl)

        grp_ign = QGroupBox("Ignored Tags")
        grp_ign_lay = QVBoxLayout(grp_ign)

        self.ign_list = QListWidget()
        self.ign_list.itemSelectionChanged.connect(self._on_ign_selection)
        grp_ign_lay.addWidget(self.ign_list)

        ign_add_row = QHBoxLayout()
        self.edit_add_ign = QLineEdit()
        self.edit_add_ign.setPlaceholderText("TagToIgnore")
        self.edit_add_ign.returnPressed.connect(self._add_ignore)
        ign_add_row.addWidget(self.edit_add_ign, stretch=1)
        btn_add_ign = QPushButton("Add")
        btn_add_ign.setProperty("role", "primary")
        btn_add_ign.setFixedWidth(64)
        btn_add_ign.clicked.connect(self._add_ignore)
        ign_add_row.addWidget(btn_add_ign)
        grp_ign_lay.addLayout(ign_add_row)

        ign_btn_row = QHBoxLayout()
        self.btn_remove_ign = QPushButton("Remove Selected")
        self.btn_remove_ign.setEnabled(False)
        self.btn_remove_ign.clicked.connect(self._remove_selected_ign)
        ign_btn_row.addWidget(self.btn_remove_ign)
        
        ign_btn_row.addStretch()
        
        btn_reset_ign = QPushButton("Reset to Defaults")
        btn_reset_ign.clicked.connect(self._reset_ignores)
        ign_btn_row.addWidget(btn_reset_ign)
        
        grp_ign_lay.addLayout(ign_btn_row)
        ign_lay.addWidget(grp_ign)

        self.tabs.addTab(ign_tab, "Ignore List")

        # ── Tab 3: Display ────────────────────────────────────────────────────
        disp_tab = QWidget()
        disp_lay = QVBoxLayout(disp_tab)

        # Watermark settings
        grp_watermark = QGroupBox("Watermark")
        grp_watermark_lay = QVBoxLayout(grp_watermark)

        self.watermark_check = QCheckBox("Show watermark in log area")
        grp_watermark_lay.addWidget(self.watermark_check)

        opacity_row = QHBoxLayout()
        opacity_row.addWidget(QLabel("Opacity:"))
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setMinimum(0)
        self.opacity_slider.setMaximum(100)
        self.opacity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.opacity_slider.setTickInterval(10)
        opacity_row.addWidget(self.opacity_slider, stretch=1)
        self.opacity_label = QLabel("0%")
        self.opacity_label.setFixedWidth(40)
        opacity_row.addWidget(self.opacity_label)
        # Apply changes in real-time
        self.opacity_slider.valueChanged.connect(self._apply_display_changes)
        self.opacity_slider.valueChanged.connect(lambda v: self.opacity_label.setText(f"{v}%"))
        grp_watermark_lay.addLayout(opacity_row)

        self.watermark_check.stateChanged.connect(self._apply_display_changes)

        disp_lay.addWidget(grp_watermark)

        # Line numbers settings
        grp_lines = QGroupBox("Log View")
        grp_lines_lay = QVBoxLayout(grp_lines)

        self.line_numbers_check = QCheckBox("Show line numbers")
        self.line_numbers_check.stateChanged.connect(self._apply_display_changes)
        grp_lines_lay.addWidget(self.line_numbers_check)

        max_row = QHBoxLayout()
        max_row.addWidget(QLabel("Max visible lines (0 = unlimited):"))
        self.max_lines_spin = QSpinBox()
        self.max_lines_spin.setRange(0, 500000)
        self.max_lines_spin.setSingleStep(1000)
        self.max_lines_spin.setToolTip("Higher values can cause lag on older systems.")
        self.max_lines_spin.valueChanged.connect(self._apply_display_changes)
        max_row.addWidget(self.max_lines_spin, stretch=1)
        grp_lines_lay.addLayout(max_row)

        self.max_lines_warn = QLabel("Higher numbers mean more memory and I/O, which can cause lag. Default is 5,000.")
        self.max_lines_warn.setStyleSheet("color: #AA6A2E; font-size: 11px;")
        grp_lines_lay.addWidget(self.max_lines_warn)

        self.save_screen_only_check = QCheckBox("Save button: only what you can see on screen")
        self.save_screen_only_check.setToolTip(
            "This affects the Save Log button. ON = save only visible lines. OFF = save the full session log."
        )
        self.save_screen_only_check.stateChanged.connect(self._apply_display_changes)
        grp_lines_lay.addWidget(self.save_screen_only_check)

        self.color_line_by_tag_check = QCheckBox("Color entire line by tag color")
        self.color_line_by_tag_check.setToolTip(
            "When enabled, the tag color is applied to the whole line (where possible). "
            "This can improve readability but may reduce contrast for some themes."
        )
        self.color_line_by_tag_check.stateChanged.connect(self._apply_display_changes)
        grp_lines_lay.addWidget(self.color_line_by_tag_check)

        pad_row = QHBoxLayout()
        pad_label = QLabel("Tag padding (min width):")
        pad_row.addWidget(pad_label)
        self.tag_padding_slider = QSlider(Qt.Orientation.Horizontal)
        self.tag_padding_slider.setRange(4, 80)
        self.tag_padding_slider.setSingleStep(2)
        self.tag_padding_slider.setPageStep(4)
        self.tag_padding_slider.setToolTip(
            "Minimum width for the tag column. Long tags are never truncated; they just extend past this width."
        )
        self.tag_padding_slider.valueChanged.connect(self._apply_display_changes)
        pad_row.addWidget(self.tag_padding_slider, stretch=1)
        self.tag_padding_value = QLabel("16")
        self.tag_padding_value.setMinimumWidth(28)
        self.tag_padding_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        pad_row.addWidget(self.tag_padding_value)
        grp_lines_lay.addLayout(pad_row)

        disp_lay.addWidget(grp_lines)
        disp_lay.addStretch()

        self.tabs.addTab(disp_tab, "Display")

        # ── Tab 4: About ──────────────────────────────────────────────────────
        about_tab = QWidget()
        about_tab_layout = QVBoxLayout(about_tab)
        about_tab_layout.setContentsMargins(0, 0, 0, 0)
        about_tab_layout.setSpacing(0)
        
        # Scroll area for about content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")
        
        # Container widget for scroll area
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("")
        about_lay = QVBoxLayout(scroll_widget)
        about_lay.setSpacing(12)
        about_lay.setContentsMargins(20, 20, 20, 20)
        
        # Import version info
        from src.version import __version__, __app_name__, __github_url__, __website_url__, __discord_url__, __patreon_url__
        
        # ─ Header: Icon, Title, Version (centered)
        header_lay = QHBoxLayout()
        header_lay.setSpacing(12)
        header_lay.setContentsMargins(0, 0, 0, 0)
        header_lay.addStretch()
        
        # Try to load app icon
        from pathlib import Path
        from PyQt6.QtSvgWidgets import QSvgWidget
        from PyQt6.QtWidgets import QLabel as QLabel_
        from PyQt6.QtGui import QPixmap
        
        icon_loaded = False
        try:
            # Try PNG first
            icon_path = Path(__file__).parent.parent / 'icons' / 'fadcat.png'
            if not icon_path.exists():
                icon_path = Path(__file__).parent.parent.parent / 'Resources' / 'src' / 'icons' / 'fadcat.png'
            
            if icon_path.exists():
                pixmap = QPixmap(str(icon_path))
                if not pixmap.isNull():
                    scaled = pixmap.scaledToWidth(56, Qt.TransformationMode.SmoothTransformation)
                    icon_label = QLabel_()
                    icon_label.setPixmap(scaled)
                    icon_label.setFixedSize(56, 56)
                    icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    header_lay.addWidget(icon_label)
                    icon_loaded = True
        except:
            pass
        
        # Fallback to SVG
        if not icon_loaded:
            try:
                icon_path = Path(__file__).parent.parent / 'icons' / 'fadcat.svg'
                if not icon_path.exists():
                    icon_path = Path(__file__).parent.parent.parent / 'Resources' / 'src' / 'icons' / 'fadcat.svg'
                if icon_path.exists():
                    icon_widget = QSvgWidget(str(icon_path))
                    icon_widget.setFixedSize(56, 56)
                    header_lay.addWidget(icon_widget)
            except:
                pass
        
        # Title and version
        title_info_lay = QVBoxLayout()
        title_info_lay.setSpacing(2)
        title_info_lay.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel(f"<b>{__app_name__}</b>")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #f0f0f0;")
        title_info_lay.addWidget(title_label)
        
        version_label = QLabel(f"v{__version__}")
        version_label.setStyleSheet("font-size: 11px; color: #999;")
        title_info_lay.addWidget(version_label)
        
        header_lay.addLayout(title_info_lay)
        header_lay.addStretch()
        about_lay.addLayout(header_lay)
        
        # Description (centered)
        desc_label = QLabel("Advanced Logcat Viewer for Android Development")
        desc_label.setStyleSheet("color: #b0b0b0; font-size: 11px; line-height: 1.4;")
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_lay.addWidget(desc_label)
        
        about_lay.addSpacing(8)
        
        # ─ Links section (macOS style buttons)
        links_container = QWidget()
        links_container.setStyleSheet("background-color: #1e1e1e; border-radius: 6px;")
        links_lay = QVBoxLayout(links_container)
        links_lay.setSpacing(6)
        links_lay.setContentsMargins(12, 10, 12, 10)
        
        def create_link_button(text, url, color="#007AFF"):
            """Create a colored link button"""
            btn = QPushButton(text)
            # Define hover and press colors
            hover_colors = {
                "#007AFF": "#0052CC",
                "#333": "#555",
                "#5865F2": "#4752C4"
            }
            press_colors = {
                "#007AFF": "#004099",
                "#333": "#222",
                "#5865F2": "#3c3f9b"
            }
            hover_color = hover_colors.get(color, color)
            press_color = press_colors.get(color, color)
            
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    border: none;
                    border-radius: 4px;
                    padding: 8px 14px;
                    font-size: 11px;
                    color: white;
                    text-align: center;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    background-color: {hover_color};
                }}
                QPushButton:pressed {{
                    background-color: {press_color};
                }}
            """)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda: self._open_url(url))
            return btn
        
        links_lay.addWidget(create_link_button("🌐 Website", __website_url__, "#007AFF"))
        links_lay.addWidget(create_link_button("💻 GitHub Repository", __github_url__, "#333"))
        links_lay.addWidget(create_link_button("💬 Discord Community", __discord_url__, "#5865F2"))
        
        about_lay.addWidget(links_container)
        
        # ─ Donation section (prominent)
        about_lay.addSpacing(8)
        
        support_text = QLabel("💝 Support FadCat Development")
        support_text.setStyleSheet("font-size: 12px; font-weight: bold; color: #e8e8e8; text-align: center;")
        support_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_lay.addWidget(support_text)
        
        support_desc = QLabel("Help support the development and keep improving FadCat!")
        support_desc.setStyleSheet("font-size: 10px; color: #b0b0b0; text-align: center;")
        support_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        support_desc.setWordWrap(True)
        about_lay.addWidget(support_desc)
        
        patreon_btn = QPushButton("❤️ Donate on Patreon")
        patreon_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff424d;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 24px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff5563;
            }
            QPushButton:pressed {
                background-color: #e53339;
            }
        """)
        patreon_btn.setMinimumHeight(36)
        patreon_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        patreon_btn.clicked.connect(lambda: self._open_url(__patreon_url__))
        about_lay.addWidget(patreon_btn)
        
        # ─ Command reference section (dark themed, color-coded)
        about_lay.addSpacing(12)
        
        import sys
        import platform
        
        is_installed = getattr(sys, 'frozen', False)
        system = platform.system()
        
        # Generate color-coded HTML for commands with explanations
        def get_command_html():
            if system == "Darwin":  # macOS
                if is_installed:
                    return """<div style="color: #d4d4d4; font-size: 10px; line-height: 1.6;">
<span style="color: #888;"># 📱 Launch CLI Mode</span><br>
<span style="color: #4ec9b0;">fadcat</span> <span style="color: #9cdcfe;">--cli</span><br><br>
<span style="color: #888;"># ⏹ Uninstall FadCat</span><br>
<span style="color: #4ec9b0;">bash</span> <span style="color: #ce9178;\">$(/Applications/FadCat.app/Contents/Resources/build/macos/uninstall.sh)</span>
</div>"""
                else:
                    return """<div style="color: #d4d4d4; font-size: 10px; line-height: 1.6;">
<span style="color: #888;"># 📱 Launch CLI Mode (Dev)</span><br>
<span style="color: #4ec9b0;">python</span> <span style="color: #ce9178;">FadCat.py</span> <span style="color: #9cdcfe;">--cli</span>
</div>"""
            elif system == "Windows":
                if is_installed:
                    return """<div style="color: #d4d4d4; font-size: 10px; line-height: 1.6;">
<span style="color: #888;">REM 📱 Launch CLI Mode</span><br>
<span style="color: #4ec9b0;">fadcat</span> <span style="color: #9cdcfe;">--cli</span><br><br>
<span style="color: #888;">REM ⏹ Uninstall FadCat</span><br>
<span style="color: #ce9178;\">%ProgramFiles%\\FadCat\\build\\windows\\uninstall.bat</span>
</div>"""
                else:
                    return """<div style="color: #d4d4d4; font-size: 10px; line-height: 1.6;">
<span style="color: #888;">REM 📱 Launch CLI Mode (Dev)</span><br>
<span style="color: #4ec9b0;">python</span> <span style="color: #ce9178;">FadCat.py</span> <span style="color: #9cdcfe;">--cli</span>
</div>"""
            else:  # Linux
                if is_installed:
                    return """<div style="color: #d4d4d4; font-size: 10px; line-height: 1.6;">
<span style="color: #888;"># 📱 Launch CLI Mode</span><br>
<span style="color: #4ec9b0;">fadcat</span> <span style="color: #9cdcfe;">--cli</span><br><br>
<span style="color: #888;"># ⏹ Uninstall FadCat</span><br>
<span style="color: #4ec9b0;">bash</span> <span style="color: #ce9178;\">/opt/fadcat/build/linux/uninstall.sh</span>
</div>"""
                else:
                    return """<div style="color: #d4d4d4; font-size: 10px; line-height: 1.6;">
<span style="color: #888;"># 📱 Launch CLI Mode (Dev)</span><br>
<span style="color: #4ec9b0;">python</span> <span style="color: #ce9178;">FadCat.py</span> <span style="color: #9cdcfe;">--cli</span>
</div>"""
        
        # Command reference label
        cmd_label = QLabel("<b>❯_ Command Reference</b>")
        cmd_label.setStyleSheet("font-size: 11px; font-weight: bold; color: #f0f0f0;")
        about_lay.addWidget(cmd_label)
        
        cmd_display = QTextEdit()
        cmd_display.setHtml(get_command_html())
        cmd_display.setReadOnly(True)
        cmd_display.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 10px;
                margin: 0;
            }
        """)
        cmd_display.setFixedHeight(90)
        about_lay.addWidget(cmd_display)
        
        # Credits Section
        about_lay.addSpacing(16)
        
        credits_label = QLabel("Credits")
        credits_label.setStyleSheet("font-size: 11px; font-weight: bold; color: #f0f0f0;")
        about_lay.addWidget(credits_label)
        
        credits_text = QLabel("FadCat is built with:")
        credits_text.setStyleSheet("font-size: 10px; color: #aaaaaa;")
        credits_text.setWordWrap(True)
        about_lay.addWidget(credits_text)
        
        # Qt Button
        qt_btn = QPushButton("🔹 Python Qt6 (PyQt6)")
        qt_btn.setFixedHeight(28)
        qt_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                color: #d4d4d4;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 10px;
                text-align: left;
            }
            QPushButton:hover { background-color: #3a3a3a; border: 1px solid #4a4a4a; }
        """)
        def show_qt_about():
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.aboutQt(self, "About Qt")
        qt_btn.clicked.connect(show_qt_about)
        about_lay.addWidget(qt_btn)
        
        # Status indicator
        status_lay = QHBoxLayout()
        status_lay.setSpacing(6)
        status_lay.setContentsMargins(0, 4, 0, 0)
        
        if is_installed:
            status_dot = QLabel("✓")
            status_dot.setStyleSheet("color: #44dd88; font-size: 11px; font-weight: bold;")
            status_lay.addWidget(status_dot)
            status_text = QLabel("Installed")
            status_text.setStyleSheet("font-size: 10px; color: #44dd88;")
        else:
            status_dot = QLabel("⚙")
            status_dot.setStyleSheet("color: #aaa; font-size: 11px;")
            status_lay.addWidget(status_dot)
            status_text = QLabel("Development Mode")
            status_text.setStyleSheet("font-size: 10px; color: #aaa;")
        
        status_lay.addWidget(status_text)
        status_lay.addStretch()
        about_lay.addLayout(status_lay)
        
        # Made with love message
        about_lay.addSpacing(20)
        
        love_msg = QLabel("Made with ❤️ at <span style='color: #E05555; font-weight: bold;'>FadSec Lab</span> in Pakistan 🇵🇰")
        love_msg.setStyleSheet("font-size: 11px; color: #E8E8E8;")
        love_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_lay.addWidget(love_msg)
        
        about_lay.addSpacing(12)
        
        # Copyright and website footer
        footer_msg = QLabel(f"© 2024-2026 FadSec Lab • <a href='{__website_url__}' style='color: #E05555; text-decoration: none;'>{__website_url__.replace('https://', '')}</a>")
        footer_msg.setStyleSheet("font-size: 9px; color: #888888;")
        footer_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer_msg.setOpenExternalLinks(True)
        about_lay.addWidget(footer_msg)
        
        about_lay.addStretch()
        
        # Add scroll widget to scroll area
        scroll_area.setWidget(scroll_widget)
        about_tab_layout.addWidget(scroll_area)
        
        self.tabs.addTab(about_tab, "About")

        # ── Tab 5: MCP ────────────────────────────────────────────────────────
        self._build_mcp_tab()

        # Dialog buttons
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = btns.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn:
            ok_btn.setProperty("role", "primary")
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    # ── Data ──────────────────────────────────────────────────────────────────

    def _populate(self):
        # BLOCK ALL SIGNALS during populate to prevent triggering changes
        self.watermark_check.blockSignals(True)
        self.opacity_slider.blockSignals(True)
        self.line_numbers_check.blockSignals(True)
        self.max_lines_spin.blockSignals(True)
        self.save_screen_only_check.blockSignals(True)
        self.color_line_by_tag_check.blockSignals(True)
        self.tag_padding_slider.blockSignals(True)
        
        # Packages
        self.pkg_list.clear()
        for pkg in self._settings.packages:
            self.pkg_list.addItem(pkg)
        
        # Ignores
        self.ign_list.clear()
        for tag in self._settings.ignored_tags:
            self.ign_list.addItem(tag)
        
        # Display settings - LOAD CURRENT VALUES
        self.watermark_check.setChecked(self._settings.show_watermark)
        opacity_percent = int(self._settings.watermark_opacity * 100)
        self.opacity_slider.setValue(opacity_percent)
        self.opacity_label.setText(f"{opacity_percent}%")
        self.line_numbers_check.setChecked(self._settings.show_line_numbers)
        self.max_lines_spin.setValue(self._settings.log_view_max_lines)
        self.save_screen_only_check.setChecked(self._settings.save_screen_only)
        self.color_line_by_tag_check.setChecked(self._settings.color_line_by_tag)
        self.tag_padding_slider.setValue(self._settings.tag_padding)
        self.tag_padding_value.setText(str(self._settings.tag_padding))
        
        # UNBLOCK SIGNALS now that populate is done
        self.watermark_check.blockSignals(False)
        self.opacity_slider.blockSignals(False)
        self.line_numbers_check.blockSignals(False)
        self.max_lines_spin.blockSignals(False)
        self.save_screen_only_check.blockSignals(False)
        self.color_line_by_tag_check.blockSignals(False)
        self.tag_padding_slider.blockSignals(False)
            
        self._refresh_default_combo()

    def _refresh_default_combo(self):
        current = self.default_combo.currentText()
        self.default_combo.clear()
        self.default_combo.addItem("(none)")
        for i in range(self.pkg_list.count()):
            self.default_combo.addItem(self.pkg_list.item(i).text())
        idx = self.default_combo.findText(current)
        if idx > 0:
            self.default_combo.setCurrentIndex(idx)
        elif self._settings.default_package:
            idx2 = self.default_combo.findText(self._settings.default_package)
            if idx2 >= 0:
                self.default_combo.setCurrentIndex(idx2)

    def _on_pkg_selection(self):
        self.btn_remove_pkg.setEnabled(len(self.pkg_list.selectedItems()) > 0)

    def _on_ign_selection(self):
        self.btn_remove_ign.setEnabled(len(self.ign_list.selectedItems()) > 0)

    def _add_package(self):
        text = self.edit_add.text().strip()
        if not text: return
        for i in range(self.pkg_list.count()):
            if self.pkg_list.item(i).text() == text: return
        self.pkg_list.addItem(text)
        self.edit_add.clear()
        self._refresh_default_combo()

    def _remove_selected_pkg(self):
        for item in self.pkg_list.selectedItems():
            self.pkg_list.takeItem(self.pkg_list.row(item))
        self._refresh_default_combo()

    def _add_ignore(self):
        text = self.edit_add_ign.text().strip()
        if not text: return
        for i in range(self.ign_list.count()):
            if self.ign_list.item(i).text() == text: return
        self.ign_list.addItem(text)
        self.edit_add_ign.clear()

    def _remove_selected_ign(self):
        for item in self.ign_list.selectedItems():
            self.ign_list.takeItem(self.ign_list.row(item))

    def _reset_ignores(self):
        repl = QMessageBox.question(
            self, "Reset Ignores",
            "Are you sure you want to reset the ignore list to default values?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if repl == QMessageBox.StandardButton.Yes:
            self.ign_list.clear()
            for tag in DEFAULT_SETTINGS["ignored_tags"]:
                self.ign_list.addItem(tag)

    def _apply_display_changes(self):
        """Apply display settings immediately for real-time preview."""
        self._settings.show_watermark = self.watermark_check.isChecked()
        self._settings.watermark_opacity = self.opacity_slider.value() / 100.0
        self._settings.show_line_numbers = self.line_numbers_check.isChecked()
        self._settings.log_view_max_lines = self.max_lines_spin.value()
        self._settings.save_screen_only = self.save_screen_only_check.isChecked()
        self._settings.color_line_by_tag = self.color_line_by_tag_check.isChecked()
        self._settings.tag_padding = self.tag_padding_slider.value()
        self.tag_padding_value.setText(str(self.tag_padding_slider.value()))
        # SAVE IMMEDIATELY so real-time changes persist
        self._settings.save()
        self.settings_changed.emit()

    def _save(self):
        packages = [self.pkg_list.item(i).text() for i in range(self.pkg_list.count())]
        ignores = [self.ign_list.item(i).text() for i in range(self.ign_list.count())]
        
        default = self.default_combo.currentText()
        if default == "(none)":
            default = ""
            
        self._settings.packages = packages
        self._settings.ignored_tags = ignores
        self._settings.default_package = default
        
        # Save all settings including display
        self._apply_display_changes()
        self._settings.save()
        self.accept()
    
    def _open_url(self, url):
        """Open a URL in the default browser."""
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(url))

    def _build_mcp_tab(self):
        """Build the MCP (Model Context Protocol) tab."""
        from src.mcp.config import generate_mcp_config
        from src.version import __version__, __author__
        
        mcp_tab = QWidget()
        mcp_lay = QVBoxLayout(mcp_tab)
        mcp_lay.setSpacing(8)
        mcp_lay.setContentsMargins(12, 12, 12, 12)
        
        # Server Control Group
        control_grp = QGroupBox("Server Control")
        control_grp_lay = QVBoxLayout(control_grp)
        control_grp_lay.setSpacing(6)
        
        # Server control buttons and status
        control_lay = QHBoxLayout()
        self.btn_toggle_server = QPushButton("Start Server")
        self.btn_toggle_server.setProperty("role", "primary")
        self.btn_toggle_server.setFixedHeight(32)
        self.btn_toggle_server.clicked.connect(self._toggle_mcp_server)
        control_lay.addWidget(self.btn_toggle_server)
        control_lay.addStretch()
        control_lay.addWidget(QLabel("Status:"))
        self.mcp_status_label = QLabel("● Idle")
        self.mcp_status_label.setFont(QFont("monospace", 10))
        self.mcp_status_label.setFixedWidth(120)
        control_lay.addWidget(self.mcp_status_label)
        control_lay.addWidget(QLabel("Port:"))
        self.mcp_port_label = QLabel("stdio")
        self.mcp_port_label.setFont(QFont("monospace", 10))
        self.mcp_port_label.setFixedWidth(80)
        control_lay.addWidget(self.mcp_port_label)
        control_lay.addStretch()
        
        control_grp_lay.addLayout(control_lay)
        mcp_lay.addWidget(control_grp)
        
        # Scroll area for config and info
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        # Container for scrollable content
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(8)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        
        # Info Group
        info_grp = QGroupBox("Available")
        info_lay = QVBoxLayout(info_grp)
        info_lay.setSpacing(4)
        
        self.mcp_info_text = QTextEdit()
        self.mcp_info_text.setReadOnly(True)
        self.mcp_info_text.setMaximumHeight(100)
        self.mcp_info_text.setFont(QFont("monospace", 9))
        self.mcp_info_text.setPlainText(
            "Tools: 13 • Resources: 4 • Prompts: 4"
        )
        info_lay.addWidget(self.mcp_info_text)
        scroll_layout.addWidget(info_grp)
        
        # Config Group
        config_grp = QGroupBox("Configuration")
        config_lay = QVBoxLayout(config_grp)
        config_lay.setSpacing(4)
        
        self.mcp_config_text = QTextEdit()
        self.mcp_config_text.setReadOnly(True)
        self.mcp_config_text.setFont(QFont("monospace", 8))
        
        try:
            config = generate_mcp_config()
            config_text = json.dumps(config, indent=2)
        except Exception as e:
            config_text = f"Error: {e}\n\nCommand: fadcat --mcp"
        
        self.mcp_config_text.setPlainText(config_text)
        config_lay.addWidget(self.mcp_config_text)
        
        # Copy button
        btn_copy = QPushButton("Copy Config")
        btn_copy.setFixedHeight(28)
        btn_copy.clicked.connect(self._copy_mcp_config)
        config_lay.addWidget(btn_copy)
        
        scroll_layout.addWidget(config_grp)
        
        # Quick Start Group
        quickstart_grp = QGroupBox("Quick Start")
        quickstart_lay = QVBoxLayout(quickstart_grp)
        quickstart_lay.setSpacing(4)
        
        quick_text = QTextEdit()
        quick_text.setReadOnly(True)
        quick_text.setFont(QFont("sans-serif", 9))
        quick_text.setPlainText(
            "1. Copy config above\n"
            "2. Open VSCode settings.json\n"
            "3. Paste under 'mcpServers'\n"
            "4. Restart VSCode\n\n"
            "Supported: VSCode, Cursor, Windsurf, Claude Code, Cline"
        )
        quick_text.setMaximumHeight(120)
        quickstart_lay.addWidget(quick_text)
        scroll_layout.addWidget(quickstart_grp)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        mcp_lay.addWidget(scroll)
        
        self.tabs.addTab(mcp_tab, "MCP")
    
    def _copy_mcp_config(self):
        """Copy MCP config to clipboard."""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(self.mcp_config_text.toPlainText())
        QMessageBox.information(self, "Copied", "MCP config copied to clipboard!")

    def _toggle_mcp_server(self):
        """Toggle MCP server on/off."""
        if hasattr(self, 'mcp_process') and self.mcp_process and self.mcp_process.poll() is None:
            # Server is running, stop it
            self._stop_mcp_server()
        else:
            # Server is not running, start it
            self._start_mcp_server()

    def _start_mcp_server(self):
        """Start the MCP server using fadcat command."""
        import subprocess
        
        try:
            # Only use fadcat command, no fallbacks
            self.mcp_process = subprocess.Popen(
                ["fadcat", "--mcp"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            self.btn_toggle_server.setText("Stop Server")
            self.btn_toggle_server.setProperty("role", "danger")
            self.style().polish(self.btn_toggle_server)
            self.mcp_status_label.setText("● Running")
            self.mcp_port_label.setText("stdio")
            self.mcp_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            QMessageBox.information(self, "Success", "MCP server started: fadcat --mcp")
        except FileNotFoundError:
            # fadcat command not found - ask user for help
            QMessageBox.critical(
                self, 
                "fadcat Not Found", 
                "The 'fadcat' command is not available.\n\n"
                "Please ensure FadCat is properly installed:\n\n"
                "1. cd /path/to/FadCat\n"
                "2. pip install -e .\n\n"
                "Then the 'fadcat' command will be available."
            )
            self.mcp_status_label.setText("● Error")
            self.mcp_port_label.setText("-")
            self.mcp_status_label.setStyleSheet("color: #F44336;")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start server:\n{e}")
            self.mcp_status_label.setText("● Error")
            self.mcp_port_label.setText("-")
            self.mcp_status_label.setStyleSheet("color: #F44336;")
    
    def _stop_mcp_server(self):
        """Stop the MCP server."""
        try:
            if hasattr(self, 'mcp_process') and self.mcp_process:
                self.mcp_process.terminate()
                try:
                    self.mcp_process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.mcp_process.kill()
                
                self.btn_toggle_server.setText("Start Server")
                self.btn_toggle_server.setProperty("role", "primary")
                self.style().polish(self.btn_toggle_server)
                self.mcp_status_label.setText("● Stopped")
                self.mcp_port_label.setText("-")
                self.mcp_status_label.setStyleSheet("color: #FF9800;")
                QMessageBox.information(self, "Success", "MCP server stopped")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to stop server:\n{e}")
    
    def closeEvent(self, event):
        """Stop MCP server when dialog closes."""
        if hasattr(self, 'mcp_process') and self.mcp_process:
            try:
                self.mcp_process.terminate()
            except:
                pass
        super().closeEvent(event)

