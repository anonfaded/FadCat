"""
FadCat Icons
Programmatically drawn QPainter icons — no external files or packages needed.
"""
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QBrush, QPainterPath, QPolygonF
from PyQt6.QtCore import Qt, QRectF, QPointF


_ICON_COLOR = "#EBEBF5"
_ICON_MUTED = "#8E8E93"
_ICON_SIZE  = 18


def _make(draw_fn, size=_ICON_SIZE, color=_ICON_COLOR) -> QIcon:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    draw_fn(p, size, QColor(color))
    p.end()
    return QIcon(pix)


# ── individual draw functions ────────────────────────────────────────────────

def _draw_play(p: QPainter, s: int, c: QColor):
    path = QPainterPath()
    pad = s * 0.15
    path.moveTo(pad, pad)
    path.lineTo(s - pad, s / 2)
    path.lineTo(pad, s - pad)
    path.closeSubpath()
    p.fillPath(path, QBrush(c))


def _draw_stop(p: QPainter, s: int, c: QColor):
    pad = s * 0.22
    p.fillRect(QRectF(pad, pad, s - 2*pad, s - 2*pad), QBrush(c))


def _draw_refresh(p: QPainter, s: int, c: QColor):
    pen = QPen(c, s * 0.11, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawArc(QRectF(s*0.12, s*0.12, s*0.76, s*0.76), 30*16, 300*16)
    # arrow head
    cx, cy = s * 0.85, s * 0.26
    aw = s * 0.13
    arrow = QPainterPath()
    arrow.moveTo(cx, cy - aw)
    arrow.lineTo(cx + aw, cy + aw * 0.5)
    arrow.lineTo(cx - aw, cy + aw * 0.5)
    arrow.closeSubpath()
    p.fillPath(arrow, QBrush(c))
    p.setPen(Qt.PenStyle.NoPen)


def _draw_clear(p: QPainter, s: int, c: QColor):
    pen = QPen(c, s * 0.11, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    pad = s * 0.24
    p.drawLine(QPointF(pad, pad), QPointF(s - pad, s - pad))
    p.drawLine(QPointF(s - pad, pad), QPointF(pad, s - pad))


def _draw_copy(p: QPainter, s: int, c: QColor):
    pen = QPen(c, s * 0.09, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    # back rect
    p.drawRoundedRect(QRectF(s*0.28, s*0.05, s*0.62, s*0.62), s*0.08, s*0.08)
    # front rect
    p.drawRoundedRect(QRectF(s*0.10, s*0.30, s*0.62, s*0.62), s*0.08, s*0.08)


def _draw_save(p: QPainter, s: int, c: QColor):
    pen = QPen(c, s * 0.09, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    # outer border
    p.drawRoundedRect(QRectF(s*0.10, s*0.10, s*0.80, s*0.80), s*0.08, s*0.08)
    # top label slot
    p.drawRect(QRectF(s*0.30, s*0.10, s*0.35, s*0.25))
    # bottom storage rectangle
    p.drawRect(QRectF(s*0.22, s*0.52, s*0.56, s*0.32))


def _draw_settings(p: QPainter, s: int, c: QColor):
    pen = QPen(c, s * 0.09, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    cx, cy, r_inner, r_outer = s/2, s/2, s*0.14, s*0.27
    # outer circle
    p.drawEllipse(QPointF(cx, cy), r_outer, r_outer)
    # inner dot
    p.setBrush(QBrush(c))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QPointF(cx, cy), r_inner, r_inner)
    # spokes
    p.setPen(pen)
    import math
    for i in range(8):
        angle = math.radians(i * 45)
        x1 = cx + math.cos(angle) * r_outer
        y1 = cy + math.sin(angle) * r_outer
        x2 = cx + math.cos(angle) * (r_outer + s * 0.15)
        y2 = cy + math.sin(angle) * (r_outer + s * 0.15)
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))


def _draw_new_tab(p: QPainter, s: int, c: QColor):
    pen = QPen(c, s * 0.10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    mid = s / 2
    pad = s * 0.22
    p.drawLine(QPointF(mid, pad), QPointF(mid, s - pad))
    p.drawLine(QPointF(pad, mid), QPointF(s - pad, mid))


def _draw_arrow_up(p: QPainter, s: int, c: QColor):
    pen = QPen(c, s * 0.10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    mid = s / 2
    pad = s * 0.20
    p.drawLine(QPointF(mid, s - pad), QPointF(mid, pad))
    p.drawLine(QPointF(mid, pad), QPointF(pad, mid))
    p.drawLine(QPointF(mid, pad), QPointF(s - pad, mid))


def _draw_arrow_down(p: QPainter, s: int, c: QColor):
    pen = QPen(c, s * 0.10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    mid = s / 2
    pad = s * 0.20
    p.drawLine(QPointF(mid, pad), QPointF(mid, s - pad))
    p.drawLine(QPointF(mid, s - pad), QPointF(pad, mid))
    p.drawLine(QPointF(mid, s - pad), QPointF(s - pad, mid))


def _draw_search(p: QPainter, s: int, c: QColor):
    pen = QPen(c, s * 0.10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    r = s * 0.28
    cx, cy = s * 0.40, s * 0.40
    p.drawEllipse(QPointF(cx, cy), r, r)
    x1 = cx + r * 0.707
    y1 = cy + r * 0.707
    p.drawLine(QPointF(x1, y1), QPointF(s - s*0.12, s - s*0.12))


def _draw_filter(p: QPainter, s: int, c: QColor):
    pen = QPen(c, s * 0.09, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    pad = s * 0.12
    p.drawLine(QPointF(pad, s*0.25), QPointF(s - pad, s*0.25))
    p.drawLine(QPointF(s*0.26, s*0.50), QPointF(s - s*0.26, s*0.50))
    p.drawLine(QPointF(s*0.40, s*0.75), QPointF(s - s*0.40, s*0.75))


def _draw_device(p: QPainter, s: int, c: QColor):
    pen = QPen(c, s * 0.09, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    # phone outline
    w, h = s * 0.45, s * 0.72
    x, y = (s - w) / 2, (s - h) / 2
    p.drawRoundedRect(QRectF(x, y, w, h), s*0.06, s*0.06)
    # home button dot
    p.setBrush(QBrush(c))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QPointF(s/2, y + h - s*0.08), s*0.04, s*0.04)


def _draw_package(p: QPainter, s: int, c: QColor):
    pen = QPen(c, s * 0.09, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    # box
    pad = s * 0.12
    p.drawRect(QRectF(pad, pad + s*0.1, s - 2*pad, s - 2*pad - s*0.1))
    # flap
    p.drawLine(QPointF(pad, pad + s*0.1), QPointF(s/2, pad))
    p.drawLine(QPointF(s - pad, pad + s*0.1), QPointF(s/2, pad))
    # line
    p.drawLine(QPointF(pad, s*0.52), QPointF(s - pad, s*0.52))


def _draw_close(p: QPainter, s: int, c: QColor):
    pen = QPen(c, s * 0.09, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    pad = s * 0.28
    p.drawLine(QPointF(pad, pad), QPointF(s - pad, s - pad))
    p.drawLine(QPointF(s - pad, pad), QPointF(pad, s - pad))


def _draw_info(p: QPainter, s: int, c: QColor):
    pen = QPen(c, s * 0.09, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(QBrush(c))
    p.drawEllipse(QPointF(s/2, s*0.28), s*0.07, s*0.07)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawLine(QPointF(s/2, s*0.42), QPointF(s/2, s*0.75))


# ── public icon factories ────────────────────────────────────────────────────

def icon_play()      -> QIcon: return _make(_draw_play)
def icon_stop()      -> QIcon: return _make(_draw_stop)
def icon_refresh()   -> QIcon: return _make(_draw_refresh)
def icon_clear()     -> QIcon: return _make(_draw_clear)
def icon_copy()      -> QIcon: return _make(_draw_copy)
def icon_save()      -> QIcon: return _make(_draw_save)
def icon_settings()  -> QIcon: return _make(_draw_settings)
def icon_new_tab()   -> QIcon: return _make(_draw_new_tab)
def icon_up()        -> QIcon: return _make(_draw_arrow_up)
def icon_down()      -> QIcon: return _make(_draw_arrow_down)
def icon_search()    -> QIcon: return _make(_draw_search)
def icon_filter()    -> QIcon: return _make(_draw_filter)
def icon_device()    -> QIcon: return _make(_draw_device)
def icon_package()   -> QIcon: return _make(_draw_package)
def icon_close()     -> QIcon: return _make(_draw_close)
def icon_info()      -> QIcon: return _make(_draw_info)
