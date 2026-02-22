"""
FadCat Theme
A single source-of-truth for all stylesheet constants and the global QSS.
"""

# ── palette ──────────────────────────────────────────────────────────────────
BG          = "#1C1C1E"
BG_ELEVATED = "#2C2C2E"
BG_WELL     = "#141416"          # log area / sunken
SEPARATOR   = "#3A3A3C"
ACCENT      = "#0A84FF"
SUCCESS     = "#30D158"
DANGER      = "#FF453A"
WARNING     = "#FFD60A"
TEXT        = "#EBEBF5"
TEXT_MUTED  = "#8E8E93"
TEXT_DIM    = "#48484A"

FONT_UI     = '".AppleSystemUIFont", "SF Pro Text", "Segoe UI", "Helvetica Neue", Arial, sans-serif'
FONT_MONO   = '"SF Mono", "JetBrains Mono", Menlo, "Courier New", monospace'


def get_stylesheet() -> str:
    return f"""
/* ─── Base ─────────────────────────────────────────────────────── */
QMainWindow, QDialog, QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: {FONT_UI};
    font-size: 13px;
}}

/* ─── MenuBar ───────────────────────────────────────────────────── */
QMenuBar {{
    background-color: {BG_ELEVATED};
    color: {TEXT};
    border-bottom: 1px solid {SEPARATOR};
    padding: 2px 0;
}}
QMenuBar::item {{
    padding: 4px 12px;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background-color: {ACCENT};
    color: #ffffff;
}}
QMenu {{
    background-color: {BG_ELEVATED};
    color: {TEXT};
    border: 1px solid {SEPARATOR};
    border-radius: 6px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: {ACCENT};
    color: #ffffff;
}}
QMenu::separator {{
    height: 1px;
    background: {SEPARATOR};
    margin: 3px 8px;
}}

/* ─── ToolBar ───────────────────────────────────────────────────── */
QToolBar {{
    background-color: {BG_ELEVATED};
    border-bottom: 1px solid {SEPARATOR};
    spacing: 4px;
    padding: 4px 8px;
}}
QToolBar::separator {{
    width: 1px;
    background: {SEPARATOR};
    margin: 4px 4px;
}}
QToolButton {{
    color: {TEXT};
    background-color: transparent;
    border: none;
    border-radius: 5px;
    padding: 5px 10px;
    font-size: 13px;
    font-family: {FONT_UI};
}}
QToolButton:hover {{
    background-color: {SEPARATOR};
}}
QToolButton:pressed {{
    background-color: {TEXT_DIM};
}}

/* ─── Tabs ──────────────────────────────────────────────────────── */
QTabWidget::pane {{
    border: none;
    background-color: {BG};
}}
QTabBar {{
    background-color: {BG_ELEVATED};
}}
QTabBar::tab {{
    background-color: transparent;
    color: {TEXT_MUTED};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 8px 20px 7px 16px;
    min-width: 100px;
    font-size: 13px;
}}
QTabBar::tab:selected {{
    color: {TEXT};
    border-bottom: 2px solid {ACCENT};
    background-color: transparent;
}}
QTabBar::tab:hover:!selected {{
    color: {TEXT};
    background-color: {SEPARATOR};
}}
QTabBar::close-button {{
    subcontrol-position: right;
}}

/* ─── Status Bar ────────────────────────────────────────────────── */
QStatusBar {{
    background-color: {BG_ELEVATED};
    color: {TEXT_MUTED};
    border-top: 1px solid {SEPARATOR};
    font-size: 12px;
    padding: 2px 8px;
}}
QStatusBar::item {{
    border: none;
}}

/* ─── Control frames inside tabs ───────────────────────────────── */
QFrame#controlBar {{
    background-color: {BG_ELEVATED};
    border-bottom: 1px solid {SEPARATOR};
}}
QFrame#searchBar {{
    background-color: {BG};
    border-bottom: 1px solid {SEPARATOR};
}}

/* ─── Buttons ───────────────────────────────────────────────────── */
QPushButton {{
    background-color: {BG_ELEVATED};
    color: {TEXT};
    border: 1px solid {SEPARATOR};
    border-radius: 5px;
    padding: 4px 12px;
    min-height: 24px;
    font-family: {FONT_UI};
    font-size: 13px;
}}
QPushButton:hover {{
    background-color: {SEPARATOR};
    border-color: #505053;
}}
QPushButton:pressed {{
    background-color: {TEXT_DIM};
}}
QPushButton:disabled {{
    color: {TEXT_DIM};
    border-color: {TEXT_DIM};
    background-color: {BG};
}}

/* start / stop accent buttons */
QPushButton[role="start"] {{
    background-color: {SUCCESS};
    border-color: {SUCCESS};
    color: #ffffff;
    font-weight: 600;
    padding: 4px 18px;
}}
QPushButton[role="start"]:hover {{
    background-color: #34c85a;
}}
QPushButton[role="start"]:pressed {{
    background-color: #28a748;
}}
QPushButton[role="start"]:disabled {{
    background-color: #2a5c38;
    border-color: #2a5c38;
    color: #5a7f63;
}}
QPushButton[role="stop"] {{
    background-color: {DANGER};
    border-color: {DANGER};
    color: #ffffff;
    font-weight: 600;
    padding: 4px 18px;
}}
QPushButton[role="stop"]:hover {{
    background-color: #ff6057;
}}
QPushButton[role="stop"]:disabled {{
    background-color: #5c2d2d;
    border-color: #5c2d2d;
    color: #8a5a5a;
}}

/* icon-only flat buttons */
QPushButton[role="icon"] {{
    background-color: transparent;
    border: none;
    border-radius: 5px;
    padding: 4px 6px;
    min-width: 28px;
    min-height: 28px;
}}
QPushButton[role="icon"]:hover {{
    background-color: {SEPARATOR};
}}
QPushButton[role="icon"]:pressed {{
    background-color: {TEXT_DIM};
}}

/* toggle buttons */
QPushButton[role="toggle"] {{
    background-color: transparent;
    border: 1px solid {SEPARATOR};
    border-radius: 5px;
    padding: 4px 10px;
    min-height: 24px;
    color: {TEXT_MUTED};
    font-size: 12px;
}}
QPushButton[role="toggle"]:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    color: #ffffff;
}}
QPushButton[role="toggle"]:hover:!checked {{
    background-color: {SEPARATOR};
    color: {TEXT};
}}

/* primary dialog button */
QPushButton[role="primary"] {{
    background-color: {ACCENT};
    border-color: {ACCENT};
    color: #ffffff;
    font-weight: 600;
}}
QPushButton[role="primary"]:hover {{
    background-color: #1a90ff;
}}

/* ─── Inputs ─────────────────────────────────────────────────────── */
QLineEdit {{
    background-color: {BG_WELL};
    color: {TEXT};
    border: 1px solid {SEPARATOR};
    border-radius: 5px;
    padding: 4px 10px;
    min-height: 24px;
    font-family: {FONT_UI};
    font-size: 13px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus {{
    border-color: {ACCENT};
    background-color: {BG};
}}
QLineEdit:disabled {{
    color: {TEXT_DIM};
    background-color: {BG};
}}

QComboBox {{
    background-color: {BG_WELL};
    color: {TEXT};
    border: 1px solid {SEPARATOR};
    border-radius: 5px;
    padding: 4px 8px;
    min-height: 24px;
    font-family: {FONT_UI};
    font-size: 13px;
    selection-background-color: {ACCENT};
}}
QComboBox:focus {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{
    width: 20px;
    border: none;
    subcontrol-origin: padding;
    subcontrol-position: right center;
}}
QComboBox::down-arrow {{
    image: none;
    width: 8px;
    height: 8px;
    border-left:  2px solid {TEXT_MUTED};
    border-bottom: 2px solid {TEXT_MUTED};
    margin-right: 6px;
    subcontrol-origin: content;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_ELEVATED};
    color: {TEXT};
    border: 1px solid {SEPARATOR};
    selection-background-color: {ACCENT};
    outline: none;
    padding: 2px;
}}

/* ─── Text Edit (log view) ──────────────────────────────────────── */
QTextEdit {{
    background-color: {BG_WELL};
    color: {TEXT};
    border: none;
    font-family: {FONT_MONO};
    font-size: 12px;
    line-height: 1.4;
    selection-background-color: {ACCENT};
}}
QTextEdit:focus {{
    outline: none;
}}

/* ─── Scroll bars ───────────────────────────────────────────────── */
QScrollBar:vertical {{
    background: {BG_WELL};
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {TEXT_DIM};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {TEXT_MUTED};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
    height: 0;
}}
QScrollBar:horizontal {{
    background: {BG_WELL};
    height: 8px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {TEXT_DIM};
    border-radius: 4px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {TEXT_MUTED};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: none;
    width: 0;
}}

/* ─── Labels ─────────────────────────────────────────────────────── */
QLabel {{
    color: {TEXT};
    font-family: {FONT_UI};
    font-size: 13px;
}}
QLabel[muted="true"] {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}

/* ─── Separators ─────────────────────────────────────────────────── */
QFrame[frameShape="5"],
QFrame[frameShape="4"] {{
    color: {SEPARATOR};
}}

/* ─── List / Tree Widgets ────────────────────────────────────────── */
QListWidget {{
    background-color: {BG_WELL};
    color: {TEXT};
    border: 1px solid {SEPARATOR};
    border-radius: 5px;
    outline: none;
    padding: 2px;
}}
QListWidget::item {{
    padding: 6px 10px;
    border-radius: 3px;
}}
QListWidget::item:selected {{
    background-color: {ACCENT};
    color: #ffffff;
}}
QListWidget::item:hover:!selected {{
    background-color: {SEPARATOR};
}}

/* ─── Group Box ──────────────────────────────────────────────────── */
QGroupBox {{
    color: {TEXT_MUTED};
    border: 1px solid {SEPARATOR};
    border-radius: 6px;
    margin-top: 12px;
    padding: 10px 8px 8px 8px;
    font-size: 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    top: -7px;
    padding: 0 4px;
    background-color: {BG};
}}

/* ─── ToolTip ─────────────────────────────────────────────────────── */
QToolTip {{
    background-color: {BG_ELEVATED};
    color: {TEXT};
    border: 1px solid {SEPARATOR};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 12px;
}}
"""
