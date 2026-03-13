"""FadCat Theme - red accent dark palette."""

BG          = "#1A1A1A"
BG_ELEVATED = "#242424"
BG_INPUT    = "#2A2A2A"
BG_WELL     = "#141414"
SEPARATOR   = "#333333"
ACCENT      = "#E05555"
ACCENT_DARK = "#C24747"
ACCENT_SOFT = "#3B1616"
SUCCESS     = "#3CB371"
WARNING     = "#E8A020"
TEXT        = "#E8E8E8"
TEXT_MUTED  = "#888888"
TEXT_DIM    = "#444444"
FONT_MONO   = '"SF Mono", "JetBrains Mono", Menlo, Consolas, "Courier New", monospace'


def get_stylesheet() -> str:
    """Complete PyQt6 dark theme with red accent — production-quality styling."""
    return """
/* Global Reset */
* {
    outline: none;
}

QMainWindow, QDialog, QWidget {
    background-color: #1A1A1A;
    color: #E8E8E8;
    font-size: 13px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

/* MenuBar */
QMenuBar {
    background-color: #242424;
    color: #E8E8E8;
    border-bottom: 1px solid #333333;
    padding: 0 4px;
    spacing: 0;
}
QMenuBar::item {
    padding: 5px 12px;
    background: transparent;
    border-radius: 4px;
}
QMenuBar::item:selected, QMenuBar::item:pressed {
    background-color: #3D1510;
    color: #E05555;
}
QMenu {
    background-color: #242424;
    color: #E8E8E8;
    border: 1px solid #333333;
    border-radius: 6px;
    padding: 4px 0;
}
QMenu::item { padding: 6px 20px 6px 14px; }
QMenu::item:selected { background-color: #E05555; color: #fff; border-radius: 3px; }
QMenu::separator { height: 1px; background: #333333; margin: 3px 8px; }

/* ToolBar */
QToolBar {
    background-color: #242424;
    border-bottom: 1px solid #333333;
    spacing: 6px;
    padding: 4px 8px;
}
QToolBar::separator { width: 1px; background: #333333; margin: 4px 8px; }
QToolBar QPushButton {
    background: transparent;
    border: none;
    padding: 4px 8px;
    color: #E8E8E8;
    qproperty-cursor: LinkingHandCursor;
}
QToolBar QPushButton:hover {
    background-color: rgba(255, 255, 255, 0.05);
    border-radius: 4px;
}
QToolBar QPushButton::icon { padding: 4px; }

/* StatusBar */
QStatusBar {
    background-color: #242424;
    color: #888888;
    border-top: 1px solid #333333;
    font-size: 11px;
    padding: 0 8px;
}
QStatusBar::item { border: none; }

/* Tabs */
QTabWidget {
    border: none;
    background-color: #1A1A1A;
}
QTabWidget::pane {
    border: none;
    background-color: #1A1A1A;
    margin: 0;
    padding: 0;
}
QTabWidget::tab-bar {
    alignment: left;
    left: 0px;
    subcontrol-position: top left;
    subcontrol-origin: margin;
}
QTabWidget::left-corner, QTabWidget::right-corner {
    background: transparent;
    border: none;
    padding: 0;
}
QTabBar {
    background: transparent;
    border-bottom: none;
    padding: 6px 12px;
    margin: 0;
}
QTabBar::tab {
    background: #2C2C2C;
    color: #B0B0B0;
    padding: 4px 28px 4px 12px;
    margin: 6px 4px 6px 4px;
    border: 1px solid #3A3A3A;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 500;
    min-width: 100px;
    outline: none;
    qproperty-cursor: LinkingHandCursor;
}
QTabBar::tab:first {
    margin-left: 4px;
}
QTabBar::tab:last {
    margin-right: 4px;
}
QTabBar::tab:selected {
    color: #EDEDED;
    font-weight: 600;
    background-color: #343434;
    border: 1px solid #424242;
}
QTabBar::tab:hover:!selected {
    color: #D0D0D0;
    background: #2F2F2F;
}
QTabBar::close-button {
    image: none;
    subcontrol-position: right;
}
QTabBar::tear {
    width: 0px;
    border: none;
    background: transparent;
}
QTabBar::scroller {
    width: 80px;
    border: none;
    background: transparent;
    padding: 4px 6px;
    margin: 0;
    spacing: 4px;
    subcontrol-position: right;
}
QTabBar QToolButton {
    background: #2B2B2B;
    border: 1px solid #3A3A3A;
    border-radius: 3px;
    margin: 0 1px;
    padding: 2px;
    width: 18px;
    height: 18px;
    max-height: 20px;
    color: #E8E8E8;
    icon-size: 12px;
    qproperty-cursor: LinkingHandCursor;
}
QTabBar QToolButton:hover {
    background: #363636;
    border-color: #4A4A4A;
    color: #FFFFFF;
}
QTabBar QToolButton:pressed {
    background: #1E1E1E;
    border-color: #E8302A;
}
QTabBar QToolButton:disabled {
    background: #1E1E1E;
    border-color: #2A2A2A;
    color: #555555;
    qproperty-cursor: ArrowCursor;
}
QTabBar QToolButton::menu-indicator {
    width: 0;
}

/* Buttons */
QPushButton {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3A3A3A, stop:1 #2A2A2A);
    color: #E8E8E8;
    border: 1px solid #333333;
    border-radius: 5px;
    padding: 5px 14px;
    font-size: 13px;
    font-weight: 500;
    qproperty-cursor: LinkingHandCursor;
}
QPushButton:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #444444, stop:1 #333333);
    border-color: #555555;
}
QPushButton:pressed {
    background-color: #1E1E1E;
}
QPushButton:disabled {
    color: #444444;
    border-color: #333333;
    background-color: #1A1A1A;
}

QPushButton[role="primary"] {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #F06A6A, stop:1 #E05555);
    color: #FFFFFF;
    border: 1px solid #C24747;
    font-weight: 600;
}
QPushButton[role="primary"]:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #F97A7A, stop:1 #E96565);
}
QPushButton[role="primary"]:pressed {
    background-color: #C24747;
}
QPushButton[role="primary"]:disabled {
    background-color: #3D1510;
    color: #704040;
    border-color: #3D1510;
}

QPushButton[role="start"] {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3CB371, stop:1 #2E8B57);
    color: #FFFFFF;
    border: 1px solid #2A7A50;
    font-weight: 600;
}
QPushButton[role="start"]:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4CD880, stop:1 #3CB371);
}
QPushButton[role="start"]:pressed {
    background-color: #2A7A50;
}
QPushButton[role="start"]:disabled {
    background-color: #1E3A28;
    color: #3A6A48;
    border-color: #1E3A28;
}

QPushButton[role="stop"] {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #E05555, stop:1 #C24747);
    color: #FFFFFF;
    border: 1px solid #B23A3A;
    font-weight: 600;
}
QPushButton[role="stop"]:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #F07A7A, stop:1 #E05555);
}
QPushButton[role="stop"]:pressed {
    background-color: #B23A3A;
}
QPushButton[role="stop"]:disabled {
    background-color: #3D1510;
    color: #704040;
    border-color: #3D1510;
}

QPushButton[role="icon-btn"] {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #333333, stop:1 #262626);
    border: 1px solid #333333;
    border-radius: 5px;
    padding: 4px;
}
QPushButton[role="icon-btn"]:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #444444, stop:1 #333333);
    border-color: #555555;
}
QPushButton[role="icon-btn"]:pressed {
    background-color: #1E1E1E;
}

QPushButton[role="tool-text"] {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #333333, stop:1 #262626);
    color: #E8E8E8;
    border: 1px solid #333333;
    border-radius: 5px;
    padding: 0 12px;
    font-size: 12px;
    font-weight: 500;
}
QPushButton[role="tool-text"]:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #444444, stop:1 #333333);
    border-color: #555555;
}
QPushButton[role="tool-text"]:pressed {
    background-color: #1E1E1E;
}

QPushButton[role="nav-btn"] {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #333333, stop:1 #262626);
    border: 1px solid #333333;
    border-radius: 5px;
    padding: 0;
}
QPushButton[role="nav-btn"]:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #444444, stop:1 #333333);
    border-color: #555555;
}
QPushButton[role="nav-btn"]:pressed {
    background-color: #1E1E1E;
}

QPushButton[role="toggle"] {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #333333, stop:1 #262626);
    border: 1px solid #333333;
    border-radius: 5px;
    padding: 0 12px;
    font-size: 12px;
    font-weight: 500;
    color: #AAAAAA;
}
QPushButton[role="toggle"]:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #444444, stop:1 #333333);
    border-color: #555555;
    color: #E8E8E8;
}
QPushButton[role="toggle"]:checked {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #E05555, stop:1 #C24747);
    border-color: #B23A3A;
    color: #FFFFFF;
    font-weight: 600;
}

/* Inputs */
QLineEdit {
    background-color: #1E1E1E;
    color: #E8E8E8;
    border: 1px solid #333333;
    border-radius: 5px;
    padding: 6px 12px;
    font-size: 13px;
    selection-background-color: #E05555;
    selection-color: #FFFFFF;
}
QLineEdit:focus { border-color: #555555; }
QLineEdit:disabled { color: #444444; }

QComboBox {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #333333, stop:1 #262626);
    color: #E8E8E8;
    border: 1px solid #333333;
    border-radius: 5px;
    padding: 6px 32px 6px 12px;
    font-size: 13px;
    qproperty-cursor: LinkingHandCursor;
}
QComboBox:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #444444, stop:1 #333333);
    border-color: #555555;
}
QComboBox:focus { border-color: #E05555; }
QComboBox::drop-down {
    border: none;
    background: transparent;
    width: 0px;
}
QComboBox::down-arrow {
    width: 0px;
    height: 0px;
    image: none;
}
QComboBox QAbstractItemView {
    background-color: #242424;
    color: #E8E8E8;
    border: 1px solid #333333;
    border-radius: 6px;
    selection-background-color: #E05555;
    selection-color: #FFFFFF;
    padding: 4px;
    outline: none;
    qproperty-cursor: LinkingHandCursor;
}

/* Scrollbars */
QScrollBar:vertical { background: #141414; width: 12px; margin: 0; }
QScrollBar::handle:vertical { background: #333333; border-radius: 6px; min-height: 30px; margin: 2px; }
QScrollBar::handle:vertical:hover { background: #444444; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }

QScrollBar:horizontal { background: #141414; height: 12px; margin: 0; }
QScrollBar::handle:horizontal { background: #333333; border-radius: 6px; min-width: 30px; margin: 2px; }
QScrollBar::handle:horizontal:hover { background: #444444; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }

/* TextEdit (log view) */
QTextEdit, QTextEdit > QWidget {
    background-color: #000000;
    color: #E8E8E8;
    border: none;
    font-family: monospace;
    font-size: 12px;
    padding: 0px;
    margin: 0px;
}
QTextEdit {
    selection-background-color: #E05555;
    selection-color: #FFFFFF;
}

/* ListWidget */
QListWidget {
    background-color: #2A2A2A;
    color: #E8E8E8;
    border: 1px solid #333333;
    border-radius: 6px;
    padding: 4px;
    font-size: 12px;
    outline: none;
}
QListWidget::item { padding: 5px 8px; border-radius: 4px; }
QListWidget::item:selected { background-color: #E05555; color: #FFFFFF; }
QListWidget::item:hover:!selected { background-color: rgba(232, 48, 42, 0.12); }

/* GroupBox */
QGroupBox {
    border: 1px solid #333333;
    border-radius: 7px;
    margin-top: 14px;
    padding-top: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 4px;
    color: #888888;
    font-size: 11px;
    font-weight: 600;
}

/* Separators */
QFrame[frameShape="5"] { background: #333333; max-width: 1px; border: none; }
QFrame[frameShape="4"] { background: #333333; max-height: 1px; border: none; }

/* ToolTip */
QToolTip {
    background-color: #242424;
    color: #E8E8E8;
    border: 1px solid #333333;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 11px;
}

/* Dialog buttons */
QDialogButtonBox QPushButton { min-width: 80px; padding: 6px 20px; min-height: 32px; }

/* Labels */
QLabel {
    color: #E8E8E8;
    background: transparent;
}
"""
