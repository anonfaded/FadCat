"""Custom icons with proper dark theme colors."""
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QPolygon, QPen, QBrush
from PyQt6.QtCore import Qt, QSize, QPoint


def _create_icon(path_points, color="#E8E8E8", size=(24, 24)) -> QIcon:
    """Create an icon from polygon points."""
    pixmap = QPixmap(size[0], size[1])
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    poly = QPolygon([QPoint(x, y) for x, y in path_points])
    painter.setBrush(QBrush(QColor(color)))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawPolygon(poly)
    painter.end()
    return QIcon(pixmap)


def icon_play() -> QIcon:
    """Play triangle pointing right."""
    return _create_icon([
        (6, 4), (6, 20), (20, 12)
    ], "#E8E8E8")


def icon_stop() -> QIcon:
    """Stop square."""
    return _create_icon([
        (6, 6), (18, 6), (18, 18), (6, 18)
    ], "#E8E8E8")


def icon_refresh() -> QIcon:
    """Circular refresh arrow."""
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # Draw circular arrow
    pen = QPen(QColor("#E8E8E8"), 2.5)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawArc(4, 4, 16, 16, 30 * 16, -270 * 16)
    
    # Arrow head
    arrow = QPolygon([QPoint(18, 6), QPoint(20, 10), QPoint(15, 8)])
    painter.setBrush(QBrush(QColor("#E8E8E8")))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawPolygon(arrow)
    painter.end()
    return QIcon(pixmap)


def icon_clear() -> QIcon:
    """Trash can icon."""
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # Bin body
    painter.setBrush(QBrush(QColor("#E8E8E8")))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(5, 7, 14, 13, 2, 2)
    
    # Bin lid
    painter.drawRoundedRect(7, 4, 10, 3, 1, 1)
    
    # Handle
    pen = QPen(QColor("#E8E8E8"), 2)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawLine(QPoint(12, 2), QPoint(12, 4))
    painter.end()
    return QIcon(pixmap)


def icon_copy() -> QIcon:
    """Copy - two overlapping squares."""
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    painter.setBrush(QBrush(QColor("#E8E8E8")))
    painter.setPen(Qt.PenStyle.NoPen)
    
    # Back square
    painter.drawRoundedRect(8, 8, 12, 12, 2, 2)
    # Front square
    painter.setOpacity(0.7)
    painter.drawRoundedRect(4, 4, 12, 12, 2, 2)
    painter.end()
    return QIcon(pixmap)


def icon_save() -> QIcon:
    """Save floppy disk."""
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    painter.setBrush(QBrush(QColor("#E8E8E8")))
    painter.setPen(Qt.PenStyle.NoPen)
    
    # Disk body
    painter.drawRoundedRect(4, 3, 16, 18, 2, 2)
    
    # Label area
    painter.setBrush(QBrush(QColor("#242424")))
    painter.drawRect(7, 5, 10, 6)
    
    # Metal shutter
    painter.setBrush(QBrush(QColor("#242424")))
    painter.drawRect(6, 14, 12, 5)
    painter.end()
    return QIcon(pixmap)


def icon_settings() -> QIcon:
    """Gear/settings icon."""
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    painter.setBrush(QBrush(QColor("#E8E8E8")))
    painter.setPen(Qt.PenStyle.NoPen)
    
    # Gear body - octagon-like shape
    center = QPoint(12, 12)
    painter.drawEllipse(center, 9, 9)
    
    # Center hole - draw with background color to create cutout effect
    painter.setBrush(QBrush(QColor("#242424")))
    painter.drawEllipse(center, 4, 4)
    painter.end()
    return QIcon(pixmap)


def icon_new_tab() -> QIcon:
    """Plus sign for new tab."""
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    pen = QPen(QColor("#E8E8E8"), 3)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    
    painter.drawLine(QPoint(12, 5), QPoint(12, 19))
    painter.drawLine(QPoint(5, 12), QPoint(19, 12))
    painter.end()
    return QIcon(pixmap)


def icon_up() -> QIcon:
    """Up arrow."""
    return _create_icon([
        (12, 4), (18, 14), (12, 12), (6, 14)
    ], "#E8E8E8")


def icon_down() -> QIcon:
    """Down arrow."""
    return _create_icon([
        (12, 20), (18, 10), (12, 12), (6, 10)
    ], "#E8E8E8")


def icon_close() -> QIcon:
    """X close icon."""
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    pen = QPen(QColor("#E8E8E8"), 2.5)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    
    painter.drawLine(QPoint(6, 6), QPoint(18, 18))
    painter.drawLine(QPoint(18, 6), QPoint(6, 18))
    painter.end()
    return QIcon(pixmap)


def icon_info() -> QIcon:
    """Info i icon."""
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    painter.setBrush(QBrush(QColor("#E8E8E8")))
    painter.setPen(Qt.PenStyle.NoPen)
    
    # Circle
    painter.drawEllipse(QPoint(12, 12), 9, 9)
    
    # Dot for "i"
    painter.drawEllipse(QPoint(12, 16), 2, 2)
    
    # Line for "i"
    painter.drawRect(11, 8, 2, 4)
    painter.end()
    return QIcon(pixmap)


def icon_search() -> QIcon:
    """Magnifying glass."""
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    pen = QPen(QColor("#E8E8E8"), 2.5)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    
    painter.drawEllipse(QPoint(9, 9), 6, 6)
    painter.drawLine(QPoint(14, 14), QPoint(19, 19))
    painter.end()
    return QIcon(pixmap)


def icon_filter() -> QIcon:
    """Filter funnel."""
    return _create_icon([
        (5, 4), (19, 4), (14, 14), (14, 18), (10, 20), (10, 14)
    ], "#E8E8E8")


def icon_device() -> QIcon:
    """Device/phone icon."""
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    painter.setBrush(QBrush(QColor("#E8E8E8")))
    painter.setPen(Qt.PenStyle.NoPen)
    
    painter.drawRoundedRect(6, 2, 12, 20, 2, 2)
    painter.setBrush(QBrush(QColor("#242424")))
    painter.drawEllipse(QPoint(12, 18), 2, 2)
    painter.end()
    return QIcon(pixmap)


def icon_package() -> QIcon:
    """Package box."""
    return _create_icon([
        (12, 3), (20, 7), (20, 17), (12, 21), (4, 17), (4, 7)
    ], "#E8E8E8")
