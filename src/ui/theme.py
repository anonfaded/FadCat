"""FadCat Theme - red accent dark palette."""

BG          = "#1A1A1A"
BG_ELEVATED = "#242424"
BG_INPUT    = "#2A2A2A"
BG_WELL     = "#141414"
SEPARATOR   = "#333333"
ACCENT      = "#E8302A"
ACCENT_DARK = "#B02020"
ACCENT_SOFT = "#3D1510"
SUCCESS     = "#3CB371"
WARNING     = "#E8A020"
TEXT        = "#E8E8E8"
TEXT_MUTED  = "#888888"
TEXT_DIM    = "#444444"
FONT_MONO   = '"SF Mono", "JetBrains Mono", Menlo, Consolas, "Courier New", monospace'


def get_stylesheet() -> str:
    return """
* { outline: none; }

QMainWindow, QDialog, QWidget {
    background-color: #1A1A1A;
    color: #E8E8E8;
    font-size: 13px;
}

/* ── MenuBar ── */
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
    color: #E8302A;
}
QMenu {
    background-color: #242424;
    color: #E8E8E8;
    border: 1px solid #333333;
    border-radius: 6px;
    padding: 4px 0;
}
QMenu::item { padding: 6px 20px 6px 14px; }
QMenu::item:selected { background-color: #E8302A; color: #fff; border-radius: 3px; }
QMenu::separator { height: 1px; background: #333333; margin: 3px 8px; }

/* ── ToolBar ── */
QToolBar {
    background-color: #242424;
    border-bottom: 1px solid #333333;
    spacing: 2px;
    padding: 4px 8px;
}
QToolBar::separator { width: 1px; background: #333333; margin: 4px 4px; }

/* ── StatusBar ── */
QStatusBar {
    background-color: #242424;
    color: #888888;
    border-top: 1px solid #333333;
    font-size: 11px;
    padding: 0 8px;
}
QStatusBar::item { border: none; }

/* ── Tabs ── */
QTabWidget { border: none; }
QTabWidget::pane { border: none; background-color: #1A1A1A; }
QTabBar { background: #242424; }
QTabBar::tab {
    background: transparent;
    color: #888888;
    padding: 8px 20px;
    min-width: 80px;
    border-bottom: 2px solid transparent;
    font-size: 12px;
}
QTabBar::tab:selected { color: #E8E8E8; border-bottom: 2px solid #E8302A; }
QTabBar::tab:hover:!selected { color: #E8E8E8; background-color: rgba(232,48,42,0.08); }

/* ── Buttons ── */
QPushButton {
    background-color: #2A2A2A;
    color: #E8E8E8;
    border: 1px solid #333333;
    border-radius: 5px;
    padding: 4px 14px;
    font-size: 12px;
    min-height: 26px;
}
QPushButton:hover { background-color: #333333; border-color: #555555; }
QPushButton:pressed { background-color: #1E1E1E; }
QPushButton:disabled { color: #444444; border-color: #333333; }

QPushButton[role="primary"] {
    background-color: #E8302A;
    color: #fff;
    border: none;
    font-weight: 600;
}
QPushButton[role="primary"]:hover { background-color: #F04040; }
QPushButton[role="primary"]:pressed { background-color: #B02020; }

QPushButton[role="start"] {
    background-color: #3CB371;
    color: #fff;
    border: none;
    font-weight: 600;
    padding: 4px 20px;
}
QPushButton[role="start"]:hover { background-color: #4CD880; }
QPushButton[role="start"]:pressed { background-color: #2A7A50; }
QPushButton[role="start"]:disabled { background-color: #1E3A28; color: #3A6A48; border: none; }

QPushButton[role="stop"] {
    background-color: #E8302A;
    color: #fff;
    border: none;
    font-weight: 600;
    padding: 4px 20px;
}
QPushButton[role="stop"]:hover { background-color: #F04040; }
QPushButton[role="stop"]:pressed { background-color: #B02020; }
QPushButton[role="stop"]:disabled { background-color: #3D1510; color: #704040; border: none; }

QPushButton[role="tool"] {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 5px;
    padding: 3px 5px;
    min-width: 28px;
    min-height: 26px;
}
QPushButton[role="tool"]:hover { background-color: rgba(255,255,255,0.07); border-color: #333333; }
QPushButton[role="tool"]:pressed { background-color: rgba(255,255,255,0.12); }

QPushButton[role="toggle"] {
    background-color: transparent;
    border: 1px solid #333333;
    border-radius: 5px;
    padding: 3px 10px;
    font-size: 11px;
    min-height: 24px;
    color: #888888;
}
QPushButton[role="toggle"]:hover { border-color: #E8302A; color: #E8E8E8; }
QPushButton[role="toggle"]:checked {
    background-color: #3D1510;
    border-color: #E8302A;
    color: #E8302A;
    font-weight: 600;
}

/* ── Inputs ── */
QLineEdit {
    background-color: #2A2A2A;
    color: #E8E8E8;
    border: 1px solid #333333;
    border-radius: 5px;
    padding: 4px 8px;
    font-size: 12px;
    selection-background-color: #E8302A;
    min-height: 26px;
}
QLineEdit:focus { border-color: #E8302A; }
QLineEdit:disabled { color: #444444; }

QComboBox {
    background-color: #2A2A2A;
    color: #E8E8E8;
    border: 1px solid #333333;
    border-radius: 5px;
    padding: 4px 8px;
    font-size: 12px;
    min-height: 26px;
    min-width: 100px;
}
QComboBox:hover { border-color: #555555; }
QComboBox:focus { border-color: #E8302A; }
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: right center;
    width: 20px;
    border-left: 1px solid #333333;
    background: transparent;
}
QComboBox::down-arrow {
    width: 0; height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #888888;
    margin-right: 5px;
}
QComboBox QAbstractItemView {
    background-color: #242424;
    color: #E8E8E8;
    border: 1px solid #333333;
    selection-background-color: #E8302A;
    selection-color: #fff;
    padding: 2px;
    outline: 0;
}

/* ── Scrollbars ── */
QScrollBar:vertical { background: transparent; width: 8px; margin: 0; }
QScrollBar::handle:vertical { background: #3A3A3A; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #555555; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 8px; margin: 0; }
QScrollBar::handle:horizontal { background: #3A3A3A; border-radius: 4px; min-width: 30px; }
QScrollBar::handle:horizontal:hover { background: #555555; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── TextEdit (log view) ── */
QTextEdit {
    background-color: #141414;
    color: #E8E8E8;
    border: none;
    font-family: "SF Mono", "JetBrains Mono", Menlo, Consolas, "Courier New", monospace;
    font-size: 12px;
    padding: 6px;
    selection-background-color: #3D1510;
}

/* ── ListWidget ── */
QListWidget {
    background-color: #2A2A2A;
    color: #E8E8E8;
    border: 1px solid #333333;
    border-radius: 5px;
    padding: 2px;
    font-size: 12px;
    outline: 0;
}
QListWidget::item { padding: 5px 8px; border-radius: 3px; }
QListWidget::item:selected { background-color: #E8302A; color: #fff; }
QListWidget::item:hover:!selected { background-color: rgba(232,48,42,0.12); }

/* ── GroupBox ── */
QGroupBox {
    border: 1px solid #333333;
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    color: #888888;
    font-size: 11px;
}

/* ── Separators ── */
QFrame[frameShape="5"] { background: #333333; max-width: 1px; border: none; }
QFrame[frameShape="4"] { background: #333333; max-height: 1px; border: none; }

/* ── ToolTip ── */
QToolTip {
    background-color: #242424;
    color: #E8E8E8;
    border: 1px solid #333333;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 11px;
}

/* ── Dialog buttons ── */
QDialogButtonBox QPushButton { min-width: 72px; padding: 5px 16px; }
QLabel { color: #E8E8E8; }
"""
