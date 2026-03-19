"""Update checker dialog for FadCat"""

import webbrowser
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QWidget,
)
from PyQt6.QtGui import QFont

from src.core.update_checker import UpdateChecker
from src.ui import icons


class UpdateCheckDialog(QDialog):
    """Beautiful update check dialog with version comparison"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Check for Updates")
        self.setModal(True)
        self.resize(480, 300)
        self.setStyleSheet("""
            QDialog {
                color: #e0e0e0;
            }
        """)
        self._build_ui()
        self._check_updates()

    def _build_ui(self):
        """Build the update check dialog UI"""
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 30, 30, 30)
        root.setSpacing(20)
        
        # Header with icon
        header_lay = QHBoxLayout()
        header_lay.setSpacing(16)
        
        # Icon
        icon_label = QLabel()
        icon_label.setPixmap(icons.app_icon().pixmap(56, 56))
        icon_label.setFixedSize(56, 56)
        header_lay.addWidget(icon_label)
        
        # Title and status
        title_lay = QVBoxLayout()
        title_lay.setSpacing(6)
        title_label = QLabel("Check for Updates")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #f0f0f0;")
        title_lay.addWidget(title_label)
        
        self.status_label = QLabel("Checking...")
        self.status_label.setStyleSheet("color: #aaa; font-size: 11px;")
        title_lay.addWidget(self.status_label)
        
        header_lay.addLayout(title_lay)
        header_lay.addStretch()
        root.addLayout(header_lay)
        
        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("background-color: #333; border: none; margin: 5px 0;")
        divider.setFixedHeight(1)
        root.addWidget(divider)
        
        # Version info section - center aligned
        version_container = QWidget()
        self.version_lay = QVBoxLayout(version_container)
        self.version_lay.setSpacing(8)
        self.version_lay.setContentsMargins(0, 0, 0, 0)
        self.version_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(version_container, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Buttons section
        button_lay = QHBoxLayout()
        button_lay.setSpacing(10)
        
        self.primary_btn = QPushButton("Check Again")
        self.primary_btn.setMinimumHeight(36)
        self.primary_btn.setMinimumWidth(140)
        self.primary_btn.setStyleSheet("""
            QPushButton {
                background-color: #44dd88;
                color: #1a1a1a;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                padding: 8px 24px;
            }
            QPushButton:hover {
                background-color: #66ee99;
            }
            QPushButton:pressed {
                background-color: #33cc77;
            }
        """)
        self.primary_btn.clicked.connect(self._check_updates)
        button_lay.addWidget(self.primary_btn)
        
        button_lay.addStretch()
        self.close_btn = QPushButton("Close")
        self.close_btn.setMinimumHeight(36)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a2a2a;
                color: #d4d4d4;
                border: 1px solid #444;
                border-radius: 6px;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
            QPushButton:pressed {
                background-color: #1a1a1a;
            }
        """)
        self.close_btn.clicked.connect(self.accept)
        button_lay.addWidget(self.close_btn)
        
        root.addStretch()
        root.addLayout(button_lay)

    def _check_updates(self):
        """Check for updates and update UI"""
        from src.version import __version__
        
        self.status_label.setText("Checking...")
        self.primary_btn.setEnabled(False)
        self.primary_btn.setText("Checking...")
        
        # Clear previous version info
        while self.version_lay.count():
            self.version_lay.takeAt(0).widget().deleteLater()
        
        result = UpdateChecker.check_for_updates(__version__)
        
        self.primary_btn.setEnabled(True)
        self.primary_btn.setText("Check Again")
        
        if result.is_error:
            self.status_label.setText("❌ Check failed")
            self.status_label.setStyleSheet("color: #ff6b6b; font-size: 11px;")
            
            error_label = QLabel(result.error)
            error_label.setWordWrap(True)
            error_label.setMinimumWidth(350)
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            error_label.setStyleSheet("color: #ff9999; font-size: 11px;")
            self.version_lay.addWidget(error_label)
            
            # Button should retry check on error
            self.primary_btn.setText("Check Again")
            self.primary_btn.clicked.disconnect()
            self.primary_btn.clicked.connect(self._check_updates)
            return
        
        if result.has_update:
            # Update available
            self.status_label.setText("✓ Update available!")
            self.status_label.setStyleSheet("color: #44dd88; font-size: 11px; font-weight: bold;")
            
            # Current version
            current_label = QLabel("Current version: ")
            current_label.setStyleSheet("color: #aaa; font-weight: bold; text-align: center;")
            current_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            current_value = QLabel(f"v{result.current_version}")
            current_value.setStyleSheet("color: #ff9999; font-weight: bold;")
            current_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.version_lay.addWidget(current_label)
            self.version_lay.addWidget(current_value)
            
            # Arrow
            arrow_label = QLabel("↓")
            arrow_label.setStyleSheet("color: #44dd88; font-size: 20px;")
            arrow_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.version_lay.addWidget(arrow_label)
            
            # New version
            new_label = QLabel("New version: ")
            new_label.setStyleSheet("color: #aaa; font-weight: bold; text-align: center;")
            new_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            new_value = QLabel(result.latest_version)
            new_value.setStyleSheet("color: #44dd88; font-weight: bold;")
            new_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.version_lay.addWidget(new_label)
            self.version_lay.addWidget(new_value)
            
            self.primary_btn.setText("Visit Releases")
            self.primary_btn.clicked.disconnect()
            self.primary_btn.clicked.connect(self._open_releases)
        else:
            # Already up to date
            self.status_label.setText("✓ All up to date!")
            self.status_label.setStyleSheet("color: #44dd88; font-size: 11px; font-weight: bold;")
            
            version_label = QLabel("Current version: ")
            version_label.setStyleSheet("color: #aaa; font-weight: bold; text-align: center;")
            version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            version_value = QLabel(f"v{result.current_version}")
            version_value.setStyleSheet("color: #44dd88; font-weight: bold;")
            version_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.version_lay.addWidget(version_label)
            self.version_lay.addWidget(version_value)
            
            # Info message
            info_label = QLabel("You're running the latest version of FadCat.")
            info_label.setWordWrap(True)
            info_label.setMinimumWidth(350)
            info_label.setStyleSheet("color: #aaa; font-size: 11px; margin-top: 10px;")
            info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.version_lay.addWidget(info_label)
            
            self.primary_btn.setText("Check Again")
            self.primary_btn.clicked.disconnect()
            self.primary_btn.clicked.connect(self._check_updates)

    def _open_releases(self):
        """Open GitHub releases page"""
        webbrowser.open(UpdateChecker.RELEASES_URL)
