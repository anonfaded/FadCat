"""SVG icon loader for FadCat UI."""
from pathlib import Path
from PyQt6.QtGui import QIcon, QPixmap, QPainter
from PyQt6.QtCore import Qt
from PyQt6.QtSvg import QSvgRenderer


def _svg_icon(name: str, size=(24, 24)) -> QIcon:
    path = Path(__file__).parent.parent / "icons" / name
    pixmap = QPixmap(size[0], size[1])
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer = QSvgRenderer(str(path))
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def icon_play() -> QIcon:
    return _svg_icon("play.svg", size=(24, 24))


def icon_stop() -> QIcon:
    return _svg_icon("stop.svg", size=(24, 24))


def icon_refresh() -> QIcon:
    return _svg_icon("refresh.svg", size=(24, 24))


def icon_clear() -> QIcon:
    return _svg_icon("clear.svg", size=(24, 24))


def icon_copy() -> QIcon:
    return _svg_icon("copy.svg", size=(24, 24))


def icon_save() -> QIcon:
    return _svg_icon("save.svg", size=(24, 24))


def icon_settings() -> QIcon:
    return _svg_icon("settings.svg", size=(24, 24))


def icon_autoscroll() -> QIcon:
    return _svg_icon("autoscroll.svg", size=(24, 24))


def icon_wrap() -> QIcon:
    return _svg_icon("wrap.svg", size=(24, 24))


def icon_grep() -> QIcon:
    return _svg_icon("grep.svg", size=(24, 24))


def icon_new_tab() -> QIcon:
    return _svg_icon("new_tab.svg", size=(24, 24))


def icon_up() -> QIcon:
    return _svg_icon("up.svg", size=(24, 24))


def icon_down() -> QIcon:
    return _svg_icon("down.svg", size=(24, 24))


def icon_close() -> QIcon:
    return _svg_icon("close.svg", size=(24, 24))


def icon_play_small() -> QIcon:
    return _svg_icon("play_small.svg", size=(16, 16))


def icon_stop_small() -> QIcon:
    return _svg_icon("stop_small.svg", size=(16, 16))


def icon_level_v() -> QIcon:
    return _svg_icon("level_v.svg", size=(16, 16))


def icon_level_d() -> QIcon:
    return _svg_icon("level_d.svg", size=(16, 16))


def icon_level_i() -> QIcon:
    return _svg_icon("level_i.svg", size=(16, 16))


def icon_level_w() -> QIcon:
    return _svg_icon("level_w.svg", size=(16, 16))


def icon_level_e() -> QIcon:
    return _svg_icon("level_e.svg", size=(16, 16))


def icon_level_f() -> QIcon:
    return _svg_icon("level_f.svg", size=(16, 16))


def icon_status() -> QIcon:
    return _svg_icon("status.svg", size=(16, 16))


def icon_status_running() -> QIcon:
    return _svg_icon("status_running.svg", size=(16, 16))


def icon_device() -> QIcon:
    return _svg_icon("device.svg", size=(16, 16))


def icon_lines() -> QIcon:
    return _svg_icon("lines.svg", size=(16, 16))


def icon_memory() -> QIcon:
    return _svg_icon("memory.svg", size=(16, 16))


def app_icon() -> QIcon:
    """Load the main app icon from ICO (Windows compatible)."""
    # Try multiple paths to handle both development and bundled modes
    paths_to_try = [
        Path(__file__).parent.parent.parent / "icon-assets" / "fadcat.ico",  # Development mode
        Path(__file__).parent.parent / "icon-assets" / "fadcat.ico",  # Bundled by PyInstaller
        Path.cwd() / "icon-assets" / "fadcat.ico",  # Current directory
    ]
    
    for path in paths_to_try:
        if path.exists():
            return QIcon(str(path))
    
    # Fallback: return empty icon if all paths fail
    return QIcon()
