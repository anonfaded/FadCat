"""Custom icons with macOS-style design."""
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QPolygon, QPen, QBrush, QFont, QPainterPath
from PyQt6.QtCore import Qt, QSize, QPoint, QPointF, QRectF


def _create_icon(draw_func, size=(24, 24)) -> QIcon:
    """Create an icon from a drawing function."""
    pixmap = QPixmap(size[0], size[1])
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    draw_func(painter)
    painter.end()
    return QIcon(pixmap)


def icon_play() -> QIcon:
    """Play triangle - white."""
    def draw(painter):
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.setPen(Qt.PenStyle.NoPen)
        path = QPainterPath()
        path.moveTo(8, 5)
        path.lineTo(8, 19)
        path.lineTo(20, 12)
        path.closeSubpath()
        painter.drawPath(path)
    return _create_icon(draw)


def icon_stop() -> QIcon:
    """Stop square - white."""
    def draw(painter):
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(6, 6, 12, 12, 2, 2)
    return _create_icon(draw)


def icon_refresh() -> QIcon:
    """Circular refresh arrow - better gap and head."""
    def draw(painter):
        pen = QPen(QColor("#FFFFFF"), 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        # Draw arc with clear gap
        painter.drawArc(4, 4, 16, 16, 40 * 16, 280 * 16)
        # Arrow head
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.setPen(Qt.PenStyle.NoPen)
        head = QPolygon([QPoint(16, 4), QPoint(22, 6), QPoint(18, 10)])
        painter.drawPolygon(head)
    return _create_icon(draw)


def icon_clear() -> QIcon:
    """Modern trash can - filled style."""
    def draw(painter):
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.setPen(Qt.PenStyle.NoPen)
        # Main bin body (slightly tapered)
        path = QPainterPath()
        path.moveTo(7, 7)
        path.lineTo(17, 7)
        path.lineTo(16, 20)
        path.lineTo(8, 20)
        path.closeSubpath()
        painter.drawPath(path)
        # Lid
        painter.drawRoundedRect(5, 5, 14, 2, 1, 1)
        painter.drawRoundedRect(10, 3, 4, 2, 1, 1)
        # Stripes (cutouts)
        painter.setBrush(QBrush(QColor("#2A2A2A")))
        painter.drawRect(QRectF(9, 9, 1.5, 9))
        painter.drawRect(QRectF(12, 9, 1.5, 9))
        painter.drawRect(QRectF(15, 9, 1.5, 9))
    return _create_icon(draw)


def icon_copy() -> QIcon:
    """Copy - two overlapping squares."""
    def draw(painter):
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.setPen(Qt.PenStyle.NoPen)
        # Back square
        painter.setOpacity(0.6)
        painter.drawRoundedRect(8, 8, 12, 12, 2, 2)
        # Front square
        painter.setOpacity(1.0)
        painter.drawRoundedRect(4, 4, 12, 12, 2, 2)
    return _create_icon(draw)


def icon_save() -> QIcon:
    """Modern save icon - high contrast."""
    def draw(painter):
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.setPen(Qt.PenStyle.NoPen)
        # Disk body
        path = QPainterPath()
        path.moveTo(4, 3)
        path.lineTo(17, 3)
        path.lineTo(20, 6)
        path.lineTo(20, 21)
        path.lineTo(4, 21)
        path.closeSubpath()
        painter.drawPath(path)
        # Cutouts for detail
        painter.setBrush(QBrush(QColor("#2A2A2A")))
        painter.drawRoundedRect(7, 3, 10, 6, 1, 1) # Top shutter
        painter.drawRoundedRect(7, 14, 10, 7, 1, 1) # Bottom label
        # Shutter notch
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.drawRect(QRectF(13, 4, 2, 3))
    return _create_icon(draw)


def icon_settings() -> QIcon:
    """Modern gear icon - more standard look."""
    def draw(painter):
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.setPen(Qt.PenStyle.NoPen)
        # Outer teeth
        for i in range(8):
            painter.save()
            painter.translate(12, 12)
            painter.rotate(i * 45)
            painter.drawRoundedRect(-3, -10, 6, 4, 1, 1)
            painter.restore()
        # Main body
        painter.drawEllipse(QPoint(12, 12), 7, 7)
        # Hole
        painter.setBrush(QBrush(QColor("#242424")))
        painter.drawEllipse(QPoint(12, 12), 3, 3)
    return _create_icon(draw)


def icon_autoscroll() -> QIcon:
    """Down arrow with a stop line."""
    def draw(painter):
        pen = QPen(QColor("#FFFFFF"), 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        # Arrow shaft
        painter.drawLine(12, 4, 12, 16)
        # Arrow head
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(QPolygon([QPoint(8, 12), QPoint(16, 12), QPoint(12, 18)]))
        # Stop line
        painter.setPen(pen)
        painter.drawLine(6, 20, 18, 20)
    return _create_icon(draw)


def icon_wrap() -> QIcon:
    """Return arrow for line wrap."""
    def draw(painter):
        pen = QPen(QColor("#FFFFFF"), 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        # Path: straight then curves back
        path = QPainterPath()
        path.moveTo(4, 8)
        path.lineTo(16, 8)
        path.arcTo(QRectF(12, 8, 8, 8), 90, -180)
        path.lineTo(6, 16)
        painter.drawPath(path)
        # Arrow head at end of return
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(QPolygon([QPoint(8, 13), QPoint(8, 19), QPoint(4, 16)]))
    return _create_icon(draw)


def icon_grep() -> QIcon:
    """Filter/Funnel icon for Grep."""
    def draw(painter):
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.setPen(Qt.PenStyle.NoPen)
        path = QPainterPath()
        path.moveTo(4, 6)
        path.lineTo(20, 6)
        path.lineTo(14, 13)
        path.lineTo(14, 19)
        path.lineTo(10, 19)
        path.lineTo(10, 13)
        path.closeSubpath()
        painter.drawPath(path)
    return _create_icon(draw)


def icon_new_tab() -> QIcon:
    """Plus sign for new tab."""
    def draw(painter):
        pen = QPen(QColor("#FFFFFF"), 2.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QPoint(12, 5), QPoint(12, 19))
        painter.drawLine(QPoint(5, 12), QPoint(19, 12))
    return _create_icon(draw)


def icon_up() -> QIcon:
    """Up arrow - chevron style."""
    def draw(painter):
        pen = QPen(QColor("#FFFFFF"), 2.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPolyline(QPolygon([QPoint(6, 15), QPoint(12, 9), QPoint(18, 15)]))
    return _create_icon(draw)


def icon_down() -> QIcon:
    """Down arrow - chevron style."""
    def draw(painter):
        pen = QPen(QColor("#FFFFFF"), 2.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPolyline(QPolygon([QPoint(6, 9), QPoint(12, 15), QPoint(18, 9)]))
    return _create_icon(draw)


def icon_close() -> QIcon:
    """X close icon."""
    def draw(painter):
        pen = QPen(QColor("#FFFFFF"), 2.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QPoint(6, 6), QPoint(18, 18))
        painter.drawLine(QPoint(18, 6), QPoint(6, 18))
    return _create_icon(draw)


def icon_play_small() -> QIcon:
    """Small play for combined button."""
    def draw(painter):
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.setPen(Qt.PenStyle.NoPen)
        path = QPainterPath()
        path.moveTo(6, 4)
        path.lineTo(6, 12)
        path.lineTo(14, 8)
        path.closeSubpath()
        painter.drawPath(path)
    return _create_icon(draw, (16, 16))


def icon_stop_small() -> QIcon:
    """Small stop for combined button."""
    def draw(painter):
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(4, 4, 8, 8, 1, 1)
    return _create_icon(draw, (16, 16))
