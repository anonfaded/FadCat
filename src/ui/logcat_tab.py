"""LogcatTab — single device/package logcat session view."""
from __future__ import annotations

import os
import time
import tempfile
import shutil
import re
from datetime import datetime
from collections import deque

try:
    from rapidfuzz import fuzz as rapidfuzz_fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QPoint, QRect, QEvent, QObject, QRectF, QPointF
from PyQt6.QtGui import (
    QTextCharFormat, QColor, QFont, QTextCursor, QFontDatabase, QPainter, QPolygon,
    QBrush, QKeySequence, QShortcut, QPixmap, QTextLayout, QTextOption, QFontMetrics, QTextLine,
    QGuiApplication
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame,
    QLabel, QComboBox, QPushButton, QLineEdit,
    QTextEdit, QFileDialog, QApplication, QSizePolicy,
    QListWidget, QListWidgetItem, QMessageBox,
    QAbstractScrollArea, QScrollBar, QMenu,
)
from PyQt6.QtSvg import QSvgRenderer

from src.core.process_reader import ProcessReader
from src.utils.adb_utils import get_adb_devices
from src.core.settings import Settings
from src.ui import icons


# ── Line Number Area Widget (Production-Grade) ─────────────────────────────────
class LineNumberArea(QWidget):
    """
    Production-grade line number area using Qt's document layout API.
    
    This is the same approach used by Qt Creator, VS Code, and professional editors.
    Rather than calculating scroll positions, we iterate through document blocks and
    query their exact positions from the layout.
    
    Key properties:
    - Block-based iteration (1 line number per logical line/block)
    - Handles word wrapping correctly (wrapped visual lines don't get numbers)
    - Accounts for variable block heights
    - Uses QTextDocument.documentLayout().blockBoundingRect()
    """
    
    def __init__(self, text_edit: 'LogTextEdit'):
        super().__init__(text_edit)
        self.text_edit = text_edit
        self.setContentsMargins(0, 0, 0, 0)
        self.setStyleSheet(
            "QWidget { background-color: #1a1a1a; color: #555555; border-right: 1px solid #333333; padding: 0px; margin: 0px; }"
        )
        self.update_width()

    def update_width(self):
        doc = self.text_edit.document()
        digits = len(str(max(1, doc.blockCount())))
        fm = self.text_edit.fontMetrics()
        width = fm.horizontalAdvance("9" * digits) + 10
        self.setFixedWidth(width)
    
    def sizeHint(self) -> QSize:
        """Return fixed width, height matches parent."""
        return QSize(self.width(), self.text_edit.height())
    
    def paintEvent(self, event):
        """Paint line numbers using document blocks and cursor positioning."""
        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor("#1a1a1a"))
        
        document = self.text_edit.document()
        viewport_height = self.text_edit.viewport().height()
        painter.setFont(self.text_edit.font())
        painter.setPen(QColor("#555555"))

        layout = document.documentLayout()
        scroll_y = self.text_edit.verticalScrollBar().value()
        cursor = self.text_edit.cursorForPosition(QPoint(0, 0))
        block = cursor.block()
        line_number = block.blockNumber() + 1

        while block.isValid():
            rect = layout.blockBoundingRect(block)
            block_y = rect.top() - scroll_y
            block_height = rect.height()

            if block_y > viewport_height:
                break
            if block_y + block_height >= 0:
                line_rect = QRect(0, int(block_y), self.width() - 4, int(block_height))
                painter.drawText(
                    line_rect,
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    f"{line_number}"
                )

            block = block.next()
            line_number += 1

        painter.end()




class LogTextEdit(QTextEdit):
    """QTextEdit with SVG watermark background and optional line numbers."""
    
    # Signal: emitted when text changes (for line numbers to update)
    text_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._watermark_pixmap = None
        self._load_watermark()
        # Connect internal text change
        self.textChanged.connect(self.text_changed.emit)
    
    def _load_watermark(self):
        """Load SVG as watermark pixmap."""
        try:
            svg_path = Path(__file__).parent.parent / "icons" / "fadcat.svg"
            if not svg_path.exists():
                return
            
            # Render SVG
            renderer = QSvgRenderer(str(svg_path))
            pixmap = QPixmap(300, 300)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            self._watermark_pixmap = pixmap
        except Exception:
            pass
    
    def paintEvent(self, event):
        """Paint watermark background."""
        # Paint watermark FIRST (lower z-index)
        if self._watermark_pixmap and Settings().show_watermark:
            painter = QPainter(self.viewport())
            painter.setOpacity(Settings().watermark_opacity)
            # Center the watermark
            x = (self.viewport().width() - self._watermark_pixmap.width()) // 2
            y = (self.viewport().height() - self._watermark_pixmap.height()) // 2
            painter.drawPixmap(x, y, self._watermark_pixmap)
            painter.end()
        
        # Paint text LAST (higher z-index, on top)
        super().paintEvent(event)


# ── Virtual Log View (high-performance) ──────────────────────────────────────
class LogLine:
    __slots__ = ("text", "plain", "chunks", "tag", "level", "line_color", "layout_cache", "plain_width", "tag_width")

    def __init__(self, text: str, plain: str, chunks: list, tag: str | None, level: str | None, line_color: QColor | None):
        self.text = text
        self.plain = plain
        self.chunks = chunks
        self.tag = tag
        self.level = level
        self.line_color = line_color
        self.layout_cache: dict[tuple[int, bool], tuple[QTextLayout, int]] = {}
        self.plain_width: int | None = None
        self.tag_width: int | None = None


class VirtualLogView(QAbstractScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lines: list[LogLine] = []
        self._visible_indices: list[int] = []
        self._show_line_numbers = True
        self._wrap = False
        self._watermark_pixmap = None
        self._load_watermark()
        self._highlight_map: dict[int, list[tuple[int, int, bool]]] = {}
        self._current_match: tuple[int, int, int] | None = None
        self._total_height = 0
        self._prefix_heights: list[int] = []
        self._last_width = 0
        self._gutter_padding = 10
        self._max_line_width = 0
        self._line_height_cache = None
        self._tag_col_width_cache = 0
        self._selection_anchor: tuple[int, int] | None = None
        self._selection_active: tuple[int, int] | None = None
        self._last_double_time = 0.0
        self._last_double_line: int | None = None
        self._suppress_release_select = False
        self._dragging = False
        self.setViewportMargins(0, 0, 0, 0)
        self.verticalScrollBar().setSingleStep(24)
        self.horizontalScrollBar().setSingleStep(24)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.viewport().setCursor(Qt.CursorShape.IBeamCursor)

    def _load_watermark(self):
        try:
            svg_path = Path(__file__).parent.parent / "icons" / "fadcat.svg"
            if not svg_path.exists():
                return
            renderer = QSvgRenderer(str(svg_path))
            pixmap = QPixmap(300, 300)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            self._watermark_pixmap = pixmap
        except Exception:
            pass

    def set_lines(self, lines: list[LogLine], reset_visible: bool = True):
        self._lines = lines
        if reset_visible:
            self._visible_indices = list(range(len(lines)))
        else:
            self._visible_indices = [i for i in self._visible_indices if 0 <= i < len(self._lines)]
        if reset_visible:
            self._selection_anchor = None
            self._selection_active = None
        self._recompute_layout_cache()
        self.viewport().update()

    def set_visible_indices(self, indices: list[int]):
        self._visible_indices = [i for i in indices if 0 <= i < len(self._lines)]
        self._recompute_layout_cache()
        self.viewport().update()

    def sync_visible_indices(self, indices: list[int], incremental: bool = False):
        self._visible_indices = [i for i in indices if 0 <= i < len(self._lines)]
        if incremental:
            self._recompute_layout_cache(incremental=True)
        else:
            self._recompute_layout_cache()
        self.viewport().update()

    def append_visible(self):
        self._recompute_layout_cache(incremental=True)
        self.viewport().update()

    def clear(self):
        self._lines.clear()
        self._visible_indices.clear()
        self._highlight_map.clear()
        self._current_match = None
        self._selection_anchor = None
        self._selection_active = None
        self._prefix_heights = []
        self._total_height = 0
        self._update_scrollbars()
        self.viewport().update()

    def set_show_line_numbers(self, show: bool):
        self._show_line_numbers = show
        self.viewport().update()

    def set_wrap_enabled(self, enabled: bool):
        if self._wrap != enabled:
            self._wrap = enabled
            # Clear all cached layouts so they're recalculated with new wrap setting
            for line in self._lines:
                line.layout_cache.clear()
            self._recompute_layout_cache()
            self.viewport().update()

    def clear_layout_cache(self):
        for line in self._lines:
            line.layout_cache.clear()
        self._recompute_layout_cache()

    def set_highlights(self, ranges: list[tuple[int, int, int]], current_idx: int | None):
        self._highlight_map.clear()
        for idx, start, end in ranges:
            if start == end:
                continue
            self._highlight_map.setdefault(idx, []).append((start, end, False))
        if current_idx is not None and 0 <= current_idx < len(ranges):
            idx, start, end = ranges[current_idx]
            if start != end:
                self._highlight_map.setdefault(idx, []).append((start, end, True))
                self._current_match = (idx, start, end)
            else:
                self._current_match = None
        else:
            self._current_match = None
        self.viewport().update()

    def scroll_to_line(self, line_idx: int):
        if not self._visible_indices:
            return
        try:
            vis_idx = self._visible_indices.index(line_idx)
        except ValueError:
            return
        y = self._line_top(vis_idx)
        self.verticalScrollBar().setValue(max(0, min(y, self._total_height)))
        self.viewport().update()

    def scroll_to_bottom(self):
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def capture_anchor(self) -> tuple[int, int] | None:
        if not self._visible_indices:
            return None
        scroll_y = self.verticalScrollBar().value()
        vis_idx = self._find_visible_start(scroll_y)
        if vis_idx < 0 or vis_idx >= len(self._visible_indices):
            return None
        line_idx = self._visible_indices[vis_idx]
        offset = scroll_y - self._line_top(vis_idx)
        return (line_idx, offset)

    def restore_anchor(self, anchor: tuple[int, int]):
        line_idx, offset = anchor
        try:
            vis_idx = self._visible_indices.index(line_idx)
        except ValueError:
            return
        y = self._line_top(vis_idx) + offset
        self.verticalScrollBar().setValue(max(0, min(y, self.verticalScrollBar().maximum())))

    def plain_text(self, visible_only: bool = True) -> str:
        if visible_only:
            lines = [self._lines[i].plain for i in self._visible_indices]
        else:
            lines = [l.plain for l in self._lines]
        return "\n".join(lines)

    def selected_text(self) -> str:
        sel = self._normalized_selection()
        if sel is None:
            return ""
        (s_line, s_col), (e_line, e_col) = sel
        parts: list[str] = []
        for line_idx in range(s_line, e_line + 1):
            if line_idx < 0 or line_idx >= len(self._lines):
                continue
            text = self._lines[line_idx].plain
            if line_idx == s_line and line_idx == e_line:
                parts.append(text[s_col:e_col])
            elif line_idx == s_line:
                parts.append(text[s_col:])
            elif line_idx == e_line:
                parts.append(text[:e_col])
            else:
                parts.append(text)
        return "\n".join(parts)

    def _normalized_selection(self) -> tuple[tuple[int, int], tuple[int, int]] | None:
        if self._selection_anchor is None or self._selection_active is None:
            return None
        a_line, a_col = self._selection_anchor
        b_line, b_col = self._selection_active
        if (a_line, a_col) <= (b_line, b_col):
            return (a_line, a_col), (b_line, b_col)
        return (b_line, b_col), (a_line, a_col)

    def _x_to_index(self, text: str, target_x: float, fm: QFontMetrics) -> int:
        if target_x <= 0:
            return 0
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi) // 2
            w = fm.horizontalAdvance(text[:mid])
            if w < target_x:
                lo = mid + 1
            else:
                hi = mid
        return min(len(text), lo)

    def _pos_to_line_col(self, pos: QPoint) -> tuple[int, int] | None:
        if not self._visible_indices:
            return None
        scroll_y = self.verticalScrollBar().value()
        scroll_x = self.horizontalScrollBar().value()
        abs_y = pos.y() + scroll_y
        vis_idx = self._find_visible_start(abs_y)
        if vis_idx < 0:
            vis_idx = 0
        if vis_idx >= len(self._visible_indices):
            vis_idx = len(self._visible_indices) - 1
        line_idx = self._visible_indices[vis_idx]
        line = self._lines[line_idx]
        line_top = self._line_top(vis_idx)
        x0 = self._gutter_width() + 6 - scroll_x
        width = self._available_width()
        fm = self.fontMetrics()
        if self._wrap:
            layout, _h, pad_len, gap_len, tag_len = self._get_wrap_layout(line, width)
            for li in range(layout.lineCount()):
                l = layout.lineAt(li)
                y0 = line_top - scroll_y + l.y()
                if y0 <= pos.y() < y0 + l.height():
                    x_rel = pos.x() - (x0 + l.x())
                    if x_rel <= 0:
                        return (line_idx, 0)
                    col = l.xToCursor(x_rel)
                    disp_idx = l.textStart() + col
                    orig_idx = self._wrap_to_original_index(disp_idx, pad_len, gap_len, tag_len, len(line.plain))
                    return (line_idx, orig_idx)
            return (line_idx, len(line.plain))
        # Non-wrap with fixed tag column
        tag_col_w = self._tag_column_width()
        badge_idx = None
        for ci, (ct, _fg, bg, _b, _i) in enumerate(line.chunks):
            if bg != _DEFAULT_BG and ct.strip() in _LEVEL_SET:
                badge_idx = ci
                break
        if badge_idx is None:
            x_rel = pos.x() - x0
            return (line_idx, self._x_to_index(line.plain, x_rel, fm))
        tag_chunks = line.chunks[:badge_idx]
        tag_text = "".join(ct for ct, *_ in tag_chunks)
        tag_text_width = fm.horizontalAdvance(tag_text)
        tag_start_x = x0 + max(0, tag_col_w - tag_text_width)
        msg_start_x = x0 + tag_col_w + 6
        if pos.x() < msg_start_x:
            x_rel = pos.x() - tag_start_x
            return (line_idx, self._x_to_index(tag_text, x_rel, fm))
        x_rel = pos.x() - msg_start_x
        offset = len(tag_text)
        return (line_idx, offset + self._x_to_index(line.plain[offset:], x_rel, fm))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            pos = self._pos_to_line_col(event.position().toPoint())
            if pos is not None:
                self._dragging = False
                self._selection_anchor = pos
                self._selection_active = pos
                self._suppress_release_select = False
                self.viewport().update()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self._selection_anchor is not None:
            pos = self._pos_to_line_col(event.position().toPoint())
            if pos is not None:
                self._selection_active = pos
                self._dragging = True
                self.viewport().update()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._suppress_release_select:
                self._suppress_release_select = False
                self._dragging = False
                return
            pos = self._pos_to_line_col(event.position().toPoint())
            if pos is not None:
                if self._dragging:
                    self._dragging = False
                else:
                    self._selection_active = pos
                self.viewport().update()
                return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = self._pos_to_line_col(event.position().toPoint())
            if pos is None:
                return
            line_idx, col = pos
            now = time.time()
            interval = QGuiApplication.styleHints().mouseDoubleClickInterval() / 1000.0
            if self._last_double_line == line_idx and now - self._last_double_time <= interval:
                text = self._lines[line_idx].plain
                self._selection_anchor = (line_idx, 0)
                self._selection_active = (line_idx, len(text))
                self._last_double_time = 0.0
                self._last_double_line = None
            else:
                text = self._lines[line_idx].plain
                start, end = self._word_bounds(text, col)
                self._selection_anchor = (line_idx, start)
                self._selection_active = (line_idx, end)
                self._last_double_time = now
                self._last_double_line = line_idx
            self._suppress_release_select = True
            self.viewport().update()
            return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        sel_text = self.selected_text()
        act_copy = menu.addAction("Copy")
        act_copy.setEnabled(bool(sel_text))
        act_copy_all = menu.addAction("Copy All")
        act_select_all = menu.addAction("Select All")
        act_clear = menu.addAction("Clear Selection")
        act_clear.setEnabled(self._selection_anchor is not None and self._selection_active is not None)
        action = menu.exec(event.globalPos())
        if action == act_copy and sel_text:
            QApplication.clipboard().setText(sel_text)
        elif action == act_copy_all:
            QApplication.clipboard().setText(self.plain_text(visible_only=True))
        elif action == act_select_all:
            if self._visible_indices:
                first = self._visible_indices[0]
                last = self._visible_indices[-1]
                self._selection_anchor = (first, 0)
                self._selection_active = (last, len(self._lines[last].plain))
                self.viewport().update()
        elif action == act_clear:
            self._selection_anchor = None
            self._selection_active = None
            self.viewport().update()

    def _word_bounds(self, text: str, idx: int) -> tuple[int, int]:
        if not text:
            return (0, 0)
        if idx >= len(text):
            idx = len(text) - 1
        if idx < 0:
            return (0, 0)
        def is_word(c: str) -> bool:
            return c.isalnum() or c in "._:/-$@#"
        if not is_word(text[idx]):
            right = idx + 1
            while right < len(text) and not is_word(text[right]):
                right += 1
            if right < len(text):
                idx = right
            else:
                left = idx - 1
                while left >= 0 and not is_word(text[left]):
                    left -= 1
                if left < 0:
                    return (idx, min(len(text), idx + 1))
                idx = left
        start = idx
        end = idx + 1
        while start > 0 and is_word(text[start - 1]):
            start -= 1
        while end < len(text) and is_word(text[end]):
            end += 1
        return (start, end)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Copy):
            text = self.selected_text()
            if text:
                QApplication.clipboard().setText(text)
                return
        if event.key() == Qt.Key.Key_Escape:
            self._selection_anchor = None
            self._selection_active = None
            self.viewport().update()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.viewport().width() != self._last_width:
            self._last_width = self.viewport().width()
            self._line_height_cache = None
            self._recompute_layout_cache()

    def _line_height(self) -> int:
        if self._line_height_cache is None:
            fm = self.fontMetrics()
            self._line_height_cache = fm.height() + 4
        return self._line_height_cache

    def _gutter_width(self) -> int:
        if not self._show_line_numbers:
            return 0
        digits = max(1, len(str(len(self._visible_indices))))
        return self.fontMetrics().horizontalAdvance("9" * digits) + self._gutter_padding

    def _available_width(self) -> int:
        return max(10, self.viewport().width() - self._gutter_width() - 8)

    def _tag_column_width(self) -> int:
        try:
            pad = int(Settings().tag_padding)
        except Exception:
            pad = 16
        min_width = self.fontMetrics().horizontalAdvance("M" * max(4, pad))
        return max(min_width, self._tag_col_width_cache)

    def _recompute_layout_cache(self, incremental: bool = False):
        if not self._visible_indices:
            self._prefix_heights = []
            self._total_height = 0
            self._max_line_width = 0
            self._tag_col_width_cache = 0
            self._update_scrollbars()
            return

        width = self._available_width()
        heights: list[int] = []
        max_width = 0
        if incremental and self._prefix_heights:
            start = len(self._prefix_heights)
            heights = self._prefix_heights[:]
            total = heights[-1] if heights else 0
            last_line = None
            for idx in self._visible_indices[start:]:
                if idx >= len(self._lines):
                    continue
                line = self._lines[idx]
                last_line = line
                h = self._layout_height(line, width)
                total += h
                heights.append(total)
            if not self._wrap and last_line is not None:
                if not hasattr(last_line, "plain_width") or last_line.plain_width is None:
                    last_line.plain_width = self.fontMetrics().horizontalAdvance(last_line.plain)
                max_width = max(max_width, last_line.plain_width)
            # Also calculate tag column width for scrollbar in non-wrap mode
            if last_line is not None and (not hasattr(last_line, "tag_width") or last_line.tag_width is None):
                if last_line.tag:
                    last_line.tag_width = self.fontMetrics().horizontalAdvance(last_line.tag)
                else:
                    last_line.tag_width = 0
            if last_line is not None:
                self._tag_col_width_cache = max(self._tag_col_width_cache, last_line.tag_width)
            self._prefix_heights = heights
            self._total_height = total
            # When not wrapping, account for tag column width + gap for scrollbar
            if not self._wrap and max_width > 0:
                tag_col_w = self._tag_column_width()
                gap_w = self.fontMetrics().horizontalAdvance("  ")  # ~6px gap
                max_width += tag_col_w + gap_w
            if max_width:
                self._max_line_width = max(self._max_line_width, max_width)
            self._update_scrollbars()
            return

        total = 0
        self._prefix_heights = []
        for idx in self._visible_indices:
            if idx >= len(self._lines):
                continue
            line = self._lines[idx]
            h = self._layout_height(line, width)
            total += h
            self._prefix_heights.append(total)
            if not self._wrap:
                if not hasattr(line, "plain_width") or line.plain_width is None:
                    line.plain_width = self.fontMetrics().horizontalAdvance(line.plain)
                max_width = max(max_width, line.plain_width)
            if not hasattr(line, "tag_width") or line.tag_width is None:
                if line.tag:
                    line.tag_width = self.fontMetrics().horizontalAdvance(line.tag)
                else:
                    line.tag_width = 0
            self._tag_col_width_cache = max(self._tag_col_width_cache, line.tag_width)
            if not hasattr(line, "tag_width") or line.tag_width is None:
                if line.tag:
                    line.tag_width = self.fontMetrics().horizontalAdvance(line.tag)
                else:
                    line.tag_width = 0
            self._tag_col_width_cache = max(self._tag_col_width_cache, line.tag_width)
        self._total_height = total
        # When not wrapping, max_line_width should include tag column width + gap + message width
        if not self._wrap and max_width > 0:
            tag_col_w = self._tag_column_width()
            gap_w = self.fontMetrics().horizontalAdvance("  ")  # ~6px gap
            max_width += tag_col_w + gap_w
        self._max_line_width = max_width
        self._update_scrollbars()

    def _layout_height(self, line: LogLine, width: int) -> int:
        if not self._wrap:
            return self._line_height()
        key = (width, True)
        cached = line.layout_cache.get(key)
        if cached:
            return cached[1]
        layout, height, pad_len, gap_len, tag_len = self._build_layout(line, width)
        line.layout_cache[key] = (layout, height, pad_len, gap_len, tag_len)
        return height

    def _wrap_to_display_index(self, idx: int, pad_len: int, gap_len: int, tag_len: int) -> int:
        if idx <= 0:
            return max(0, pad_len)
        d = idx + pad_len
        if idx >= tag_len:
            d += gap_len
        return d

    def _wrap_to_original_index(self, idx: int, pad_len: int, gap_len: int, tag_len: int, max_len: int) -> int:
        if idx <= pad_len:
            return 0
        d = idx - pad_len
        if d <= tag_len:
            return min(max_len, d)
        if d <= tag_len + gap_len:
            return min(max_len, tag_len)
        return min(max_len, d - gap_len)

    def _cursor_x(self, line_obj: QTextLine, pos: int) -> float:
        x = line_obj.cursorToX(pos)
        if isinstance(x, tuple):
            return float(x[0])
        return float(x)

    def _get_wrap_layout(self, line: LogLine, width: int) -> tuple[QTextLayout, int, int, int, int]:
        key = (width, True)
        cached = line.layout_cache.get(key)
        if cached:
            if len(cached) == 2:
                return cached[0], cached[1], 0, 0, 0
            return cached[0], cached[1], cached[2], cached[3], cached[4]
        layout, height, pad_len, gap_len, tag_len = self._build_layout(line, width)
        line.layout_cache[key] = (layout, height, pad_len, gap_len, tag_len)
        return layout, height, pad_len, gap_len, tag_len

    def _build_layout(self, line: LogLine, width: int) -> tuple[QTextLayout, int, int, int, int]:
        display_chunks = line.chunks
        pad_len = 0
        gap_len = 0
        tag_len = 0
        indent_px = 0.0
        if self._wrap:
            badge_idx = None
            for ci, (ct, _fg, bg, _b, _i) in enumerate(line.chunks):
                if bg != _DEFAULT_BG and ct.strip() in _LEVEL_SET:
                    badge_idx = ci
                    break
            if badge_idx is not None:
                tag_chunks = line.chunks[:badge_idx]
                rest_chunks = line.chunks[badge_idx:]
                tag_text = "".join(ct for ct, *_ in tag_chunks)
                tag_len = len(tag_text)
                fm = self.fontMetrics()
                char_w = max(1, fm.horizontalAdvance("M"))
                tag_text_width = fm.horizontalAdvance(tag_text.rstrip())
                tag_col_w = self._tag_column_width()
                indent_px = float(tag_col_w + 6)
                pad_px = max(0, tag_col_w - tag_text_width)
                pad_len = max(0, int(round(pad_px / char_w)))
                gap_len = max(1, int(round(6 / char_w)))
                display_chunks = []
                if pad_len:
                    display_chunks.append((" " * pad_len, _DEFAULT_FG, _DEFAULT_BG, False, False))
                display_chunks.extend(tag_chunks)
                display_chunks.append((" " * gap_len, _DEFAULT_FG, _DEFAULT_BG, False, False))
                display_chunks.extend(rest_chunks)

        display_plain = "".join(ct for ct, *_ in display_chunks)
        layout = QTextLayout(display_plain, self.font())
        ranges = []
        pos = 0
        use_line_color = line.line_color is not None
        level = line.level
        for chunk_text, fg, bg, bold, italic in display_chunks:
            length = len(chunk_text)
            fmt = QTextCharFormat()
            token = chunk_text.strip()
            if token in _LEVEL_SET:
                level_key = level or token
                if level_key in _LEVEL_COLORS:
                    badge_bg = _LEVEL_COLORS[level_key]
                    fmt.setForeground(_contrast_color(badge_bg))
                    fmt.setBackground(badge_bg)
                else:
                    fmt.setForeground(fg)
                    if bg != _DEFAULT_BG:
                        fmt.setBackground(bg)
            elif use_line_color and bg == _DEFAULT_BG:
                fmt.setForeground(line.line_color)
            else:
                fmt.setForeground(fg)
                if bg != _DEFAULT_BG:
                    fmt.setBackground(bg)
            if bold:
                fmt.setFontWeight(QFont.Weight.Bold)
            if italic:
                fmt.setFontItalic(True)
            fr = QTextLayout.FormatRange()
            fr.start = pos
            fr.length = length
            fr.format = fmt
            ranges.append(fr)
            pos += length
        layout.setFormats(ranges)
        option = QTextOption()
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere if self._wrap else QTextOption.WrapMode.NoWrap)
        layout.setTextOption(option)
        layout.beginLayout()
        height = 0.0
        line_no = 0
        while True:
            line_obj = layout.createLine()
            if not line_obj.isValid():
                break
            indent = indent_px if line_no > 0 else 0.0
            line_obj.setLineWidth(max(10.0, float(width) - indent))
            line_obj.setPosition(QPointF(indent, height))
            height += line_obj.height()
            line_no += 1
        layout.endLayout()
        return layout, int(height) + 4, pad_len, gap_len, tag_len

    def _update_scrollbars(self):
        page = self.viewport().height()
        self.verticalScrollBar().setRange(0, max(0, self._total_height - page))
        self.verticalScrollBar().setPageStep(page)
        if self._wrap:
            self.horizontalScrollBar().setRange(0, 0)
        else:
            hmax = max(0, self._max_line_width - self._available_width())
            self.horizontalScrollBar().setRange(0, hmax)

    def _line_top(self, visible_idx: int) -> int:
        if visible_idx <= 0:
            return 0
        if visible_idx - 1 < len(self._prefix_heights):
            return self._prefix_heights[visible_idx - 1]
        return 0

    def _find_visible_start(self, scroll_y: int) -> int:
        if not self._prefix_heights:
            return 0
        lo, hi = 0, len(self._prefix_heights) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if self._prefix_heights[mid] < scroll_y:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def paintEvent(self, event):
        painter = QPainter(self.viewport())
        painter.fillRect(event.rect(), QColor("#000000"))

        if self._watermark_pixmap and Settings().show_watermark:
            painter.setOpacity(Settings().watermark_opacity)
            x = (self.viewport().width() - self._watermark_pixmap.width()) // 2
            y = (self.viewport().height() - self._watermark_pixmap.height()) // 2
            painter.drawPixmap(x, y, self._watermark_pixmap)
            painter.setOpacity(1.0)

        gutter_w = self._gutter_width()
        scroll_y = self.verticalScrollBar().value()
        scroll_x = self.horizontalScrollBar().value()
        tag_col_w = self._tag_column_width()
        x0 = gutter_w + 6
        x0 -= scroll_x
        y0 = -scroll_y
        width = self._available_width()
        fm = self.fontMetrics()

        if not self._visible_indices:
            painter.end()
            return

        start_idx = self._find_visible_start(scroll_y)
        y = self._line_top(start_idx) - scroll_y
        i = start_idx
        draw_numbers_in_loop = gutter_w == 0

        while i < len(self._visible_indices) and y < self.viewport().height():
            line_idx = self._visible_indices[i]
            line = self._lines[line_idx]
            line_h = self._layout_height(line, width)
            badge_idx = None
            tag_text = ""
            tag_text_len = 0
            tag_text_width = 0
            tag_start_x = x0
            msg_start_x = x0
            if not self._wrap:
                for ci, (ct, _fg, bg, _b, _i) in enumerate(line.chunks):
                    if bg != _DEFAULT_BG and ct.strip() in _LEVEL_SET:
                        badge_idx = ci
                        break
                if badge_idx is not None:
                    tag_chunks = line.chunks[:badge_idx]
                    tag_text = "".join(ct for ct, *_ in tag_chunks)
                    tag_text_len = len(tag_text)
                    tag_text_width = fm.horizontalAdvance(tag_text)
                    tag_start_x = x0 + max(0, tag_col_w - tag_text_width)
                    msg_start_x = x0 + tag_col_w + 6

            if self._show_line_numbers and draw_numbers_in_loop:
                painter.setPen(QColor("#555555"))
                line_rect = QRect(0, int(y), gutter_w - 4, int(line_h))
                painter.drawText(
                    line_rect,
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
                    str(i + 1),
                )

            # Selection (draw before highlights)
            selection = self._normalized_selection()
            if selection is not None:
                (s_line, s_col), (e_line, e_col) = selection
                if s_line <= line_idx <= e_line:
                    sel_start = s_col if line_idx == s_line else 0
                    sel_end = e_col if line_idx == e_line else len(line.plain)
                    if sel_start != sel_end:
                        sel_color = QColor(185, 28, 28, 180)
                        if self._wrap:
                            layout, _h, pad_len, gap_len, tag_len = self._get_wrap_layout(line, width)
                            sel_start = self._wrap_to_display_index(sel_start, pad_len, gap_len, tag_len)
                            sel_end = self._wrap_to_display_index(sel_end, pad_len, gap_len, tag_len)
                            for li in range(layout.lineCount()):
                                l = layout.lineAt(li)
                                line_start = l.textStart()
                                line_end = line_start + l.textLength()
                                s = max(sel_start, line_start)
                                e = min(sel_end, line_end)
                                if s < e:
                                    x_start = self._cursor_x(l, s - line_start)
                                    x_end = self._cursor_x(l, e - line_start)
                                    rect = QRectF(
                                        x0 + l.x() + x_start,
                                        y + l.y(),
                                        x_end - x_start,
                                        l.height(),
                                    )
                                    painter.fillRect(rect, sel_color)
                        else:
                            if badge_idx is None:
                                x_start = x0 + fm.horizontalAdvance(line.plain[:sel_start])
                                x_end = x0 + fm.horizontalAdvance(line.plain[:sel_end])
                                rect = QRect(int(x_start), int(y), int(x_end - x_start), int(line_h))
                                painter.fillRect(rect, sel_color)
                            else:
                                if sel_start < tag_text_len:
                                    s = sel_start
                                    e = min(sel_end, tag_text_len)
                                    x_start = tag_start_x + fm.horizontalAdvance(line.plain[:s])
                                    x_end = tag_start_x + fm.horizontalAdvance(line.plain[:e])
                                    rect = QRect(int(x_start), int(y), int(x_end - x_start), int(line_h))
                                    painter.fillRect(rect, sel_color)
                                if sel_end > tag_text_len:
                                    s = max(sel_start, tag_text_len)
                                    e = sel_end
                                    x_start = msg_start_x + fm.horizontalAdvance(line.plain[tag_text_len:s])
                                    x_end = msg_start_x + fm.horizontalAdvance(line.plain[tag_text_len:e])
                                    rect = QRect(int(x_start), int(y), int(x_end - x_start), int(line_h))
                                    painter.fillRect(rect, sel_color)

            # Highlights (draw first)
            if line_idx in self._highlight_map:
                highlights = self._highlight_map[line_idx]
                for start, end, is_current in highlights:
                    if start == end:
                        continue
                    # Current (active) = bright yellow background
                    # Non-current = orange/red background for better contrast
                    color = QColor(255, 200, 50, 220) if is_current else QColor(220, 100, 40, 200)
                    if self._wrap:
                        layout, _h, pad_len, gap_len, tag_len = self._get_wrap_layout(line, width)
                        start = self._wrap_to_display_index(start, pad_len, gap_len, tag_len)
                        end = self._wrap_to_display_index(end, pad_len, gap_len, tag_len)
                        for li in range(layout.lineCount()):
                            l = layout.lineAt(li)
                            line_start = l.textStart()
                            line_end = line_start + l.textLength()
                            sel_start = max(start, line_start)
                            sel_end = min(end, line_end)
                            if sel_start < sel_end:
                                x_start = self._cursor_x(l, sel_start - line_start)
                                x_end = self._cursor_x(l, sel_end - line_start)
                                rect = QRectF(
                                    x0 + l.x() + x_start,
                                    y + l.y(),
                                    x_end - x_start,
                                    l.height(),
                                )
                                painter.fillRect(rect, color)
                    else:
                        if badge_idx is None:
                            x_start = x0 + fm.horizontalAdvance(line.plain[:start])
                            x_end = x0 + fm.horizontalAdvance(line.plain[:end])
                            rect = QRect(int(x_start), int(y), int(x_end - x_start), int(line_h))
                            painter.fillRect(rect, color)
                        else:
                            if start < tag_text_len:
                                s = start
                                e = min(end, tag_text_len)
                                x_start = tag_start_x + fm.horizontalAdvance(line.plain[:s])
                                x_end = tag_start_x + fm.horizontalAdvance(line.plain[:e])
                                rect = QRect(int(x_start), int(y), int(x_end - x_start), int(line_h))
                                painter.fillRect(rect, color)
                            if end > tag_text_len:
                                s = max(start, tag_text_len)
                                e = end
                                x_start = msg_start_x + fm.horizontalAdvance(line.plain[tag_text_len:s])
                                x_end = msg_start_x + fm.horizontalAdvance(line.plain[tag_text_len:e])
                                rect = QRect(int(x_start), int(y), int(x_end - x_start), int(line_h))
                                painter.fillRect(rect, color)

            # Text
            if self._wrap:
                layout, _h, _pad_len, _gap_len, _tag_len = self._get_wrap_layout(line, width)
                layout.draw(painter, QPointF(x0, float(y)))
            else:
                x = x0
                # Build highlight ranges with type info (character indices)
                # is_current=True means yellow bg (needs dark text)
                # is_current=False means dark red bg (needs white text)
                highlight_ranges = []
                if line_idx in self._highlight_map:
                    for h_start, h_end, is_current in self._highlight_map[line_idx]:
                        if h_start != h_end:
                            highlight_ranges.append((h_start, h_end, is_current))
                
                # Track character position for highlight color override
                char_pos = 0  # Position in line.plain
                
                def _get_text_color_for_highlight(pos: int) -> QColor | None:
                    """Return text color if pos is within a highlight range, else None."""
                    for h_start, h_end, is_current in highlight_ranges:
                        if h_start <= pos < h_end:
                            # Yellow bg (current match) -> white text for contrast
                            # Orange bg (regular match) -> white text for contrast
                            return QColor("#ffffff")
                    return None
                
                # Draw tag area in fixed column (full tag, right aligned)
                if badge_idx is not None:
                    x = tag_start_x
                    for chunk_text, fg, bg, bold, italic in line.chunks[:badge_idx]:
                        token = chunk_text.strip()
                        is_level = token in _LEVEL_SET
                        fmt = QTextCharFormat()
                        use_line_color = line.line_color is not None
                        if is_level:
                            level_key = line.level or token
                            if level_key in _LEVEL_COLORS:
                                badge_bg = _LEVEL_COLORS[level_key]
                                fmt.setForeground(_contrast_color(badge_bg))
                                fmt.setBackground(badge_bg)
                            else:
                                fmt.setForeground(fg)
                                if bg != _DEFAULT_BG:
                                    fmt.setBackground(bg)
                        elif use_line_color and bg == _DEFAULT_BG:
                            fmt.setForeground(line.line_color)
                        else:
                            fmt.setForeground(fg)
                            if bg != _DEFAULT_BG:
                                fmt.setBackground(bg)
                        if bold:
                            fmt.setFontWeight(QFont.Weight.Bold)
                        if italic:
                            fmt.setFontItalic(True)
                        painter.setFont(self.font())
                        
                        # Check if this chunk is within ANY highlight and force white text
                        is_in_highlight = False
                        for h_start, h_end, is_current in highlight_ranges:
                            if char_pos < h_end and (char_pos + len(chunk_text)) > h_start:
                                is_in_highlight = True
                                break
                        
                        if is_in_highlight:
                            painter.setPen(QColor("#ffffff"))
                        else:
                            painter.setPen(fmt.foreground().color())
                        
                        if fmt.background() != QBrush():
                            bgc = fmt.background().color()
                            if bgc.isValid() and bgc != _DEFAULT_BG:
                                painter.fillRect(QRect(int(x), int(y), fm.horizontalAdvance(chunk_text), line_h), bgc)
                        painter.drawText(QPoint(int(x), int(y) + fm.ascent() + 2), chunk_text)
                        x += fm.horizontalAdvance(chunk_text)
                        char_pos += len(chunk_text)
                    x = msg_start_x
                    chunks_to_draw = line.chunks[badge_idx:]
                else:
                    chunks_to_draw = line.chunks
                # Draw badge + message
                for chunk_text, fg, bg, bold, italic in chunks_to_draw:
                    token = chunk_text.strip()
                    is_level = token in _LEVEL_SET
                    fmt = QTextCharFormat()
                    use_line_color = line.line_color is not None
                    if is_level:
                        level_key = line.level or token
                        if level_key in _LEVEL_COLORS:
                            badge_bg = _LEVEL_COLORS[level_key]
                            fmt.setForeground(_contrast_color(badge_bg))
                            fmt.setBackground(badge_bg)
                        else:
                            fmt.setForeground(fg)
                            if bg != _DEFAULT_BG:
                                fmt.setBackground(bg)
                    elif use_line_color and bg == _DEFAULT_BG:
                        fmt.setForeground(line.line_color)
                    else:
                        fmt.setForeground(fg)
                        if bg != _DEFAULT_BG:
                            fmt.setBackground(bg)
                    if bold:
                        fmt.setFontWeight(QFont.Weight.Bold)
                    if italic:
                        fmt.setFontItalic(True)
                    painter.setFont(self.font())
                    
                    # Check if any part of this chunk overlaps with highlights
                    is_in_highlight = False
                    for h_start, h_end, is_current in highlight_ranges:
                        if char_pos < h_end and (char_pos + len(chunk_text)) > h_start:
                            is_in_highlight = True
                            break
                    
                    # Force white text for highlighted text, otherwise use original color
                    if is_in_highlight:
                        painter.setPen(QColor("#ffffff"))
                    else:
                        painter.setPen(fmt.foreground().color())
                    
                    if fmt.background() != QBrush():
                        bgc = fmt.background().color()
                        if bgc.isValid() and bgc != _DEFAULT_BG:
                            painter.fillRect(QRect(int(x), int(y), fm.horizontalAdvance(chunk_text), line_h), bgc)
                    
                    painter.drawText(QPoint(int(x), int(y) + fm.ascent() + 2), chunk_text)
                    x += fm.horizontalAdvance(chunk_text)
                    char_pos += len(chunk_text)

            y += line_h
            i += 1

        if gutter_w > 0:
            painter.fillRect(QRect(0, 0, gutter_w, self.viewport().height()), QColor("#1a1a1a"))
            painter.setPen(QColor("#333333"))
            painter.drawLine(gutter_w - 1, 0, gutter_w - 1, self.viewport().height())
            if self._show_line_numbers:
                y = self._line_top(start_idx) - scroll_y
                i = start_idx
                painter.setPen(QColor("#555555"))
                while i < len(self._visible_indices) and y < self.viewport().height():
                    line_idx = self._visible_indices[i]
                    line_h = self._layout_height(self._lines[line_idx], width)
                    line_rect = QRect(0, int(y), gutter_w - 4, int(line_h))
                    painter.drawText(
                        line_rect,
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
                        str(i + 1),
                    )
                    y += line_h
                    i += 1

        painter.end()

# ── Search Worker (async) ────────────────────────────────────────────────────
class _SearchWorker(QObject):
    finished = pyqtSignal(int, list)

    def __init__(self, seq: int, lines: list[str], query: str, regex: bool, case: bool, fuzzy: bool = False):
        super().__init__()
        self._seq = seq
        self._lines = lines
        self._query = query
        self._regex = regex
        self._case = case
        self._fuzzy = fuzzy

    @staticmethod
    def _fuzzy_match(text: str, needle: str, case: bool = False) -> list[tuple[int, int]]:
        """Fuzzy match using rapidfuzz or fallback to conservative algorithm.
        Returns list of (start, end) position tuples only if score >= 75%.
        """
        if not needle:
            return []
        
        text_cmp = text if case else text.lower()
        needle_cmp = needle if case else needle.lower()
        
        # Use rapidfuzz if available for better accuracy
        if HAS_RAPIDFUZZ:
            # Score the line against the query
            score = rapidfuzz_fuzz.partial_ratio(needle_cmp, text_cmp)
            
            # Only return match if score is good enough (≥75%)
            if score < 75:
                return []
            
            # Find best substring match position
            best_start = 0
            best_score = 0
            for i in range(max(0, len(text_cmp) - len(needle_cmp) + 1)):
                substring = text_cmp[i:i + len(needle_cmp)]
                sub_score = rapidfuzz_fuzz.ratio(needle_cmp, substring)
                if sub_score > best_score:
                    best_score = sub_score
                    best_start = i
            
            # Return the best matching region
            if best_score >= 50:  # Reasonable match within the substring
                return [(best_start, best_start + len(needle_cmp))]
            return []
        else:
            # Fallback: conservative character-by-character matching
            # Only match if characters are relatively close (within 2x needle length)
            ranges = []
            needle_idx = 0
            max_gap = len(needle_cmp) * 2  # Allow characters up to 2x query length apart
            
            for i, char in enumerate(text_cmp):
                if needle_idx < len(needle_cmp) and char == needle_cmp[needle_idx]:
                    if needle_idx == 0 or i - ranges[-1][1] < max_gap:
                        ranges.append((i, i + 1))
                        needle_idx += 1
            
            # Only return if all characters matched
            return ranges if needle_idx == len(needle_cmp) else []

    def run(self):
        ranges: list[tuple[int, int]] = []
        if not self._query:
            self.finished.emit(self._seq, ranges)
            return

        if self._fuzzy:
            # Fuzzy search: match all characters in order but not necessarily consecutive
            needle = self._query if self._case else self._query.lower()
            for i, line in enumerate(self._lines):
                match_ranges = self._fuzzy_match(line, needle, self._case)
                for start, end in match_ranges:
                    ranges.append((i, start, end))
        elif self._regex:
            flags = 0 if self._case else re.IGNORECASE
            try:
                pattern = re.compile(self._query, flags)
            except re.error:
                self.finished.emit(self._seq, ranges)
                return
            for i, line in enumerate(self._lines):
                for m in pattern.finditer(line):
                    start, end = m.span()
                    if start != end:
                        ranges.append((i, start, end))
        else:
            needle = self._query if self._case else self._query.lower()
            nlen = len(needle)
            if nlen == 0:
                self.finished.emit(self._seq, ranges)
                return
            for i, line in enumerate(self._lines):
                hay = line if self._case else line.lower()
                start = 0
                while True:
                    idx = hay.find(needle, start)
                    if idx == -1:
                        break
                    ranges.append((i, idx, idx + nlen))
                    start = idx + nlen

        self.finished.emit(self._seq, ranges)

# ── Custom ComboBox with proper dropdown arrow ────────────────────────────────
class CustomComboBox(QComboBox):
    """QComboBox with a proper Python-drawn dropdown arrow."""
    def paintEvent(self, event):
        super().paintEvent(event)
        if self.isEnabled():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            arrow_x = self.width() - 22
            arrow_y = (self.height() - 6) // 2
            points = [
                QPoint(arrow_x, arrow_y),
                QPoint(arrow_x + 8, arrow_y),
                QPoint(arrow_x + 4, arrow_y + 6),
            ]
            painter.setBrush(QBrush(QColor("#E05555")))
            painter.setPen(QColor("#E05555"))
            painter.drawConvexPolygon(QPolygon(points))
    
    def mousePressEvent(self, event):
        """Keep default focus handling; popup is shown on release."""
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Show dropdown menu when clicking anywhere on the combo box."""
        if event.button() == Qt.MouseButton.LeftButton:
            if not self.view().isVisible():
                self.showPopup()
            return
        super().mouseReleaseEvent(event)


class PackageComboBox(CustomComboBox):
    """ComboBox with a search bar inside the popup."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        if self.lineEdit():
            self.lineEdit().setReadOnly(True)
            self.lineEdit().installEventFilter(self)
        self._popup = QFrame(None, Qt.WindowType.Popup)
        self._popup.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._popup.setObjectName("pkgPopup")
        self._popup.setStyleSheet("QFrame#pkgPopup { background: transparent; border: none; }")

        outer = QVBoxLayout(self._popup)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._panel = QFrame(self._popup)
        self._panel.setObjectName("pkgPanel")
        self._panel.setStyleSheet(
            "QFrame#pkgPanel { background: #1E1E1E; border: 1px solid #333333; border-radius: 10px; }"
        )
        outer.addWidget(self._panel)

        layout = QVBoxLayout(self._panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        self.search_edit = QLineEdit(self._popup)
        self.search_edit.setPlaceholderText("Search packages...")
        self.search_edit.setFixedHeight(28)
        self.search_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.search_edit.setStyleSheet(
            "QLineEdit { background: #2A2A2A; color: #E8E8E8; border: 1px solid #3A3A3A; padding: 4px 8px; border-radius: 6px; }"
        )
        layout.addWidget(self.search_edit, stretch=0)

        self._list_widget = QListWidget(self._popup)
        self._list_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._list_widget.setStyleSheet(
            "QListWidget { background: #1E1E1E; color: #E8E8E8; border: 1px solid #2A2A2A; border-radius: 8px; }"
            "QListWidget::item:selected { background: #2A2A2A; }"
        )
        layout.addWidget(self._list_widget, stretch=1)

        self._list_widget.itemClicked.connect(self._on_item_clicked)
        self._all_top: list[str] = []
        self._all_lower: list[str] = []

        app = QApplication.instance()
        if app:
            app.setStyleSheet(
                app.styleSheet()
                + " QToolTip { background-color: #1A1A1A; color: #E8E8E8; border: 1px solid #333333; padding: 6px 8px; }"
            )

    def showPopup(self):
        if self._popup.isVisible():
            return
        # Size and position popup
        width = max(self.width(), 280)
        height = 320
        pos = self.mapToGlobal(self.rect().bottomLeft())
        self._popup.setGeometry(pos.x(), pos.y(), width, height)
        self._popup.show()
        # Reset filter on open so list is visible, then focus search
        if self.search_edit.text():
            self.search_edit.clear()
        self.search_edit.setFocus()

    def hidePopup(self):
        if self._popup.isVisible():
            self._popup.hide()

    def eventFilter(self, obj, event):
        if obj is self.lineEdit() and event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                if not self._popup.isVisible():
                    self.showPopup()
                return True
        return super().eventFilter(obj, event)

    def _on_item_clicked(self, item):
        if not item or item.data(Qt.ItemDataRole.UserRole) == "header":
            return
        value = item.data(Qt.ItemDataRole.UserRole)
        self.setCurrentText(value if value else item.text().strip())
        self.hidePopup()

    def set_sectioned_items(self, top_items: list[str], lower_items: list[str], filter_text: str):
        self._all_top = list(top_items)
        self._all_lower = list(lower_items)
        self.apply_filter(filter_text)

    def apply_filter(self, filter_text: str):
        ftext = (filter_text or "").strip().lower()
        self._list_widget.clear()

        def add_header(title: str, tooltip: str):
            header = QListWidgetItem(title)
            header.setData(Qt.ItemDataRole.UserRole, "header")
            header.setFlags(Qt.ItemFlag.ItemIsEnabled)
            font = header.font()
            font.setBold(True)
            header.setFont(font)
            header.setForeground(QColor("#E05555"))
            header.setToolTip(tooltip)
            self._list_widget.addItem(header)

        def add_item(text: str):
            item = QListWidgetItem(f"  {text}")
            item.setData(Qt.ItemDataRole.UserRole, text)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            if text == "Global":
                item.setToolTip("Global: show all logs (no package filtering).")
            self._list_widget.addItem(item)

        # Separate Global from FadCat packages
        top_packages = [p for p in self._all_top if p != "Global"]
        top_total = len(top_packages)
        
        # Always show Global first
        global_matches = [p for p in self._all_top if p == "Global"]
        if global_matches:
            add_item("Global")
        
        # Then show FadCat packages
        top_matches = [p for p in top_packages if not ftext or ftext in p.lower()]
        if top_matches:
            add_header(
                f"FadCat Packages ({top_total})",
                "FadCat packages are saved in Settings for quick access."
            )
            for p in top_matches:
                add_item(p)

        lower_total = len(self._all_lower)
        lower_matches = [p for p in self._all_lower if not ftext or ftext in p.lower()]
        if lower_matches:
            add_header(
                f"Device Packages ({lower_total})",
                "Device packages are installed on the currently connected device."
            )
            for p in lower_matches:
                add_item(p)

# ── ANSI colour table ─────────────────────────────────────────────────────────
_ANSI_RESET = re.compile(r"\x1b\[([0-9;]*)m")
_ANSI_STRIP = re.compile(r"\x1b\[[0-9;]*m")
_TAG_RE = re.compile(r"^[A-Z]\/([^:(]+)")
_LEVEL_RE = re.compile(r"\s([VDIWEF])\s")

_FG = {
    30: "#9C9C9C", 31: "#FF5F5F", 32: "#5AF78E", 33: "#F3F99D",
    34: "#57C7FF", 35: "#D070FF", 36: "#5FFFD7", 37: "#FFFFFF",
    90: "#B0B0B0", 91: "#FF7A7A", 92: "#7CFFAA", 93: "#FFF0A6",
    94: "#7CCBFF", 95: "#E09BFF", 96: "#7CFFE6", 97: "#FFFFFF",
}
_BG = {
    40: "#2A2A2A", 41: "#8A1C1C", 42: "#0E6B3A", 43: "#8A6A1C",
    44: "#1E4E8A", 45: "#5E2A8A", 46: "#1E5E5E", 47: "#4A4A4A",
}

_DEFAULT_FG = QColor("#E8E8E8")
_DEFAULT_BG = QColor("#141414")
_LEVEL_COLORS = {
    "V": QColor("#8A8A8A"),
    "D": QColor("#4CC2FF"),
    "I": QColor("#50F0A0"),
    "W": QColor("#FFD54A"),
    "E": QColor("#FF5F5F"),
    "F": QColor("#FF3B3B"),
}

_LEVEL_SET = {"V", "D", "I", "W", "E", "F"}


def _parse_ansi(text: str) -> list[tuple[str, QColor, QColor, bool, bool]]:
    """Return list of (chunk, fg, bg, bold, italic)."""
    result: list[tuple[str, QColor, QColor, bool, bool]] = []
    fg = _DEFAULT_FG
    bg = _DEFAULT_BG
    bold = False
    italic = False
    pos = 0
    for m in _ANSI_RESET.finditer(text):
        if m.start() > pos:
            result.append((text[pos:m.start()], fg, bg, bold, italic))
        codes = [int(c) for c in m.group(1).split(";") if c.isdigit()]
        if not codes:
            codes = [0]
        for c in codes:
            if c == 0:
                fg, bg, bold, italic = _DEFAULT_FG, _DEFAULT_BG, False, False
            elif c == 1:
                bold = True
            elif c == 3:
                italic = True
            elif c in _FG:
                fg = QColor(_FG[c])
            elif c in _BG:
                bg = QColor(_BG[c])
        pos = m.end()
    if pos < len(text):
        result.append((text[pos:], fg, bg, bold, italic))
    return result


def _line_color_from_chunks(chunks: list[tuple[str, QColor, QColor, bool, bool]]) -> QColor | None:
    for chunk_text, _fg, bg, _bold, _italic in chunks:
        if bg != _DEFAULT_BG:
            t = chunk_text.strip()
            if t in {"V", "D", "I", "W", "E", "F"}:
                return bg
    for chunk_text, fg, bg, _bold, _italic in chunks:
        if chunk_text.strip() and fg != _DEFAULT_FG and bg == _DEFAULT_BG:
            return fg
    return None


def _level_from_chunks(chunks: list[tuple[str, QColor, QColor, bool, bool]]) -> str | None:
    for chunk_text, _fg, bg, _bold, _italic in chunks:
        if bg != _DEFAULT_BG:
            t = chunk_text.strip()
            if t in _LEVEL_SET:
                return t
    return None


def _contrast_color(color: QColor) -> QColor:
    r = color.red()
    g = color.green()
    b = color.blue()
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
    return QColor("#111111") if luminance > 0.6 else QColor("#FFFFFF")


def _extract_tag(text: str) -> str | None:
    clean = _ANSI_STRIP.sub("", text).lstrip()
    m = _TAG_RE.match(clean)
    if m:
        return m.group(1).strip()
    m2 = _LEVEL_RE.search(clean)
    if m2:
        left = clean[:m2.start()].rstrip()
        if left:
            return left
    return None


def _extract_level(text: str) -> str | None:
    clean = _ANSI_STRIP.sub("", text).lstrip()
    if not clean:
        return None
    tokens = clean.split()
    for idx in range(min(2, len(tokens))):
        tok = tokens[idx]
        if tok in {"V", "D", "I", "W", "E", "F"}:
            return tok
    for tok in tokens:
        if tok in {"V", "D", "I", "W", "E", "F"}:
            return tok
    if len(clean) >= 2 and clean[0] in "VDIWEF" and clean[1] == "/":
        return clean[0]
    m = _LEVEL_RE.search(clean)
    if not m:
        return None
    return m.group(1).strip()


class LogcatTab(QWidget):
    """A single logcat capture session."""

    status_changed = pyqtSignal()
    device_selected = pyqtSignal(str) # Emitted when a device is picked

    # ── Construction ──────────────────────────────────────────────────────────

    def __init__(self, parent=None):
        super().__init__(parent)
        self._reader: ProcessReader | None = None
        self._thread: QThread | None = None
        self._running = False
        self._match_positions: list[int] = []
        self._match_idx = 0
        self._total_lines = 0
        self._settings = Settings()
        self._max_lines = max(0, int(self._settings.log_view_max_lines))
        self._lines: list[LogLine] = []
        self._visible_indices: list[int] = []
        self._pending_lines: deque[str] = deque()
        self._paused_buffer: deque[str] = deque()
        self._paused_count = 0
        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(16)
        self._flush_timer.timeout.connect(self._flush_pending_lines)
        self._visible_line_count = 0
        self._log_path = Path(tempfile.gettempdir()) / f"fadcat_log_{id(self)}.txt"
        try:
            self._log_fp = open(self._log_path, "w", encoding="utf-8", buffering=1)
        except Exception:
            self._log_fp = None
        self._pkg_filter_text = ""
        self._pkg_settings: list[str] = []
        self._pkg_device: list[str] = []
        self._pending_restart = False
        self._last_package = ""
        self._stopping = False
        self._level_filters: set[str] = set()
        self._rebuild_id = 0
        self._color_line_by_tag = self._settings.color_line_by_tag
        self._last_tag_color: QColor | None = None
        self._grep_active = False
        self._match_ranges: list[tuple[int, int, int]] = []
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(140)
        self._search_timer.timeout.connect(self._apply_search_now)
        self._search_seq = 0
        self._search_thread: QThread | None = None
        self._search_worker: _SearchWorker | None = None
        self._selection_timer = QTimer(self)
        self._selection_timer.setInterval(16)
        self._selection_timer.timeout.connect(self._apply_selection_batch)
        self._pending_ranges: list[tuple[int, int]] = []
        self._applied_selections: list[tuple[int, int, int]] = []

        self._build_ui()
        self.log_view.set_lines(self._lines, reset_visible=False)
        self._setup_shortcuts()
        self._last_package = self._selected_package()

        # Connect device change to fetching packages
        self.device_combo.currentTextChanged.connect(self._on_device_changed)
        
        # Connect package selection to save it in settings
        self.pkg_combo.currentTextChanged.connect(self._on_package_changed)

    @staticmethod
    def _hand(widget: QWidget):
        widget.setCursor(Qt.CursorShape.PointingHandCursor)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_control_bar(), stretch=0)
        root.addWidget(self._build_search_bar(), stretch=0)
        root.addWidget(self._build_log_area(), stretch=1)

    # ── Control bar ───────────────────────────────────────────────────────────

    def _build_control_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(40)
        bar.setObjectName("controlBar")
        bar.setStyleSheet("QFrame#controlBar { background: #242424; border-bottom: 1px solid #333333; }")

        h = QHBoxLayout(bar)
        h.setContentsMargins(8, 4, 8, 4)
        h.setSpacing(8)
        self._control_layout = h

        # Device
        self.lbl_device = QLabel("Device")
        self.lbl_device.setStyleSheet("color: #AAAAAA; font-size: 11px; font-weight: 500; background: transparent;")
        self.lbl_device.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        h.addWidget(self.lbl_device, stretch=0)

        self.device_combo = CustomComboBox()
        self.device_combo.setMinimumWidth(120)
        self.device_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.device_combo.setFixedHeight(24)
        self.device_combo.setToolTip("Select ADB device")
        h.addWidget(self.device_combo, stretch=2)

        btn_refresh = QPushButton()
        btn_refresh.setIcon(icons.icon_refresh())
        btn_refresh.setProperty("role", "icon-btn")
        btn_refresh.setToolTip("Refresh devices")
        btn_refresh.setFixedSize(24, 24)
        self._hand(btn_refresh)
        btn_refresh.clicked.connect(self.refresh_devices)
        h.addWidget(btn_refresh, stretch=0)

        h.addWidget(self._build_v_sep(), stretch=0)

        # Package
        self.lbl_pkg = QLabel("Package")
        self.lbl_pkg.setStyleSheet("color: #AAAAAA; font-size: 11px; font-weight: 500; background: transparent;")
        self.lbl_pkg.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        h.addWidget(self.lbl_pkg, stretch=0)

        self.pkg_combo = PackageComboBox()
        self.pkg_combo.setMinimumWidth(120)
        self.pkg_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.pkg_combo.setFixedHeight(24)
        self.pkg_combo.setToolTip("Package name (select 'Global' for all logs)")
        if self.pkg_combo.lineEdit():
            self.pkg_combo.lineEdit().setPlaceholderText("Select a package or Global")
        # Search bar lives inside popup
        self.pkg_combo.search_edit.textChanged.connect(self._on_pkg_filter_changed)
        self._load_packages()
        h.addWidget(self.pkg_combo, stretch=2)

        h.addStretch(1)

        # Start/Stop Toggle
        self.btn_toggle = QPushButton("Start")
        self.btn_toggle.setIcon(icons.icon_play())
        self.btn_toggle.setProperty("role", "start")
        self.btn_toggle.setFixedHeight(24)
        self.btn_toggle.setMinimumWidth(86)
        self.btn_toggle.setToolTip("Toggle Capture")
        self._hand(self.btn_toggle)
        self.btn_toggle.clicked.connect(self.toggle_capture)
        h.addWidget(self.btn_toggle, stretch=0)

        h.addWidget(self._build_v_sep(), stretch=0)

        # Tools
        self._btn_clear = self._icon_btn(icons.icon_clear(), "Clear", self.clear_log, "Clear log")
        h.addWidget(self._btn_clear, stretch=0)

        self._btn_copy = self._icon_btn(icons.icon_copy(), "Copy", self.copy_log, "Copy all to clipboard")
        h.addWidget(self._btn_copy, stretch=0)

        self._btn_save = self._icon_btn(icons.icon_save(), "Save", self.save_log, "Save log to file")
        h.addWidget(self._btn_save, stretch=0)

        self.refresh_devices()
        return bar

    def _icon_btn(self, icon, text, slot, tip=None) -> QPushButton:
        b = QPushButton(f" {text}")
        b.setIcon(icon)
        b.setProperty("role", "tool-text")
        b.setFixedHeight(24)
        b.setMinimumWidth(68)
        self._hand(b)
        b.clicked.connect(slot)
        if tip:
            b.setToolTip(tip)
        return b

    # ── Search bar ────────────────────────────────────────────────────────────

    def _build_search_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(36)
        bar.setObjectName("searchBar")
        bar.setStyleSheet("QFrame#searchBar { background: #1E1E1E; border-bottom: 1px solid #333333; }")

        h = QHBoxLayout(bar)
        h.setContentsMargins(8, 4, 8, 4)
        h.setSpacing(8)
        self._search_layout = h

        # Search input (narrower)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search logs... (⌘F)")
        self.search_edit.setFixedHeight(24)
        self.search_edit.setMaximumWidth(280)
        self.search_edit.setMinimumWidth(140)
        self.search_edit.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setStyleSheet("QLineEdit { padding: 0 8px; font-size: 11px; }")
        self.search_edit.textChanged.connect(self._on_search_changed)
        self.search_edit.returnPressed.connect(self._next_match)
        h.addWidget(self.search_edit, stretch=0)

        # Filter toggles
        self.btn_case = QPushButton("Aa")
        self.btn_case.setProperty("role", "toggle")
        self.btn_case.setCheckable(True)
        self.btn_case.setToolTip("Case sensitive: match upper/lowercase exactly.")
        self.btn_case.setMinimumWidth(28)
        self.btn_case.setFixedHeight(24)
        self.btn_case.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self._hand(self.btn_case)
        self.btn_case.toggled.connect(self._on_search_changed)
        h.addWidget(self.btn_case, stretch=0)

        self.btn_regex = QPushButton(".*")
        self.btn_regex.setProperty("role", "toggle")
        self.btn_regex.setCheckable(True)
        self.btn_regex.setToolTip(
            "Regular expression: match patterns, not just plain text. "
            "Examples: `error|fail`, `\\bActivity\\b`, `^E/`."
        )
        self.btn_regex.setMinimumWidth(28)
        self.btn_regex.setFixedHeight(24)
        self.btn_regex.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self._hand(self.btn_regex)
        self.btn_regex.toggled.connect(self._on_search_changed)
        h.addWidget(self.btn_regex, stretch=0)

        self.btn_fuzzy = QPushButton("≈")
        self.btn_fuzzy.setProperty("role", "toggle")
        self.btn_fuzzy.setCheckable(True)
        self.btn_fuzzy.setToolTip(
            "Fuzzy search: match characters in order, but not necessarily consecutive. "
            "Example: 'ace' matches 'Application crashed everywhere'."
        )
        self.btn_fuzzy.setMinimumWidth(28)
        self.btn_fuzzy.setFixedHeight(24)
        self.btn_fuzzy.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self._hand(self.btn_fuzzy)
        self.btn_fuzzy.toggled.connect(self._on_search_changed)
        h.addWidget(self.btn_fuzzy, stretch=0)

        self.btn_grep = QPushButton("Grep ⌥G")
        self.btn_grep.setIcon(icons.icon_grep())
        self.btn_grep.setProperty("role", "toggle")
        self.btn_grep.setCheckable(True)
        self.btn_grep.setToolTip("Grep mode - hide non-matching lines (⌥G)")
        self.btn_grep.setMinimumWidth(80)
        self.btn_grep.setFixedHeight(24)
        self._hand(self.btn_grep)
        self.btn_grep.toggled.connect(self._on_search_changed)
        h.addWidget(self.btn_grep, stretch=0)

        h.addWidget(self._build_v_sep(), stretch=0)

        # Level chips (compact)
        self._level_chip_bar = QFrame()
        self._level_chip_bar.setStyleSheet("QFrame { background: transparent; }")
        chip_lay = QHBoxLayout(self._level_chip_bar)
        chip_lay.setContentsMargins(0, 0, 0, 0)
        chip_lay.setSpacing(4)
        self._level_chip_buttons: list[QPushButton] = []

        def add_level_chip(label: str, color: str, icon_fn, tooltip: str):
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFixedHeight(24)
            btn.setFixedWidth(24)
            btn.setIcon(icon_fn())
            btn.setIconSize(QSize(12, 12))
            self._hand(btn)
            btn.setStyleSheet(
                "QPushButton { background: #2A2A2A; color: #CCCCCC; border: 1px solid #3A3A3A; border-radius: 8px; padding: 0px; }"
                f"QPushButton:checked {{ background: {color}; color: #111111; border: 1px solid {color}; }}"
            )
            btn.setToolTip(tooltip)
            btn.toggled.connect(lambda checked, lvl=label: self._toggle_level_filter(lvl, checked))
            chip_lay.addWidget(btn)
            self._level_chip_buttons.append(btn)

        add_level_chip("V", "#8A8A8A", icons.icon_level_v,
                       "Verbose: extremely detailed messages. Turn this on only when you need very noisy, low-level logs.")
        add_level_chip("D", "#4A9FE8", icons.icon_level_d,
                       "Debug: developer diagnostics and troubleshooting details. Useful while investigating issues.")
        add_level_chip("I", "#3CB371", icons.icon_level_i,
                       "Info: normal app status and milestones. Good for understanding what the app is doing.")
        add_level_chip("W", "#E8A020", icons.icon_level_w,
                       "Warning: something unexpected happened, but the app can keep running.")
        add_level_chip("E", "#E05555", icons.icon_level_e,
                       "Error: something failed. These are important when a feature is broken.")
        add_level_chip("F", "#FF2D2D", icons.icon_level_f,
                       "Fatal: serious crash or abort. These usually mean the app stopped.")

        h.addWidget(self._level_chip_bar, stretch=0)

        # Navigation
        self.btn_prev = QPushButton()
        self.btn_prev.setIcon(icons.icon_up())
        self.btn_prev.setProperty("role", "nav-btn")
        self.btn_prev.setToolTip("Previous match (⇧F3)")
        self.btn_prev.setFixedSize(24, 24)
        self._hand(self.btn_prev)
        self.btn_prev.clicked.connect(self._prev_match)
        h.addWidget(self.btn_prev, stretch=0)

        self.btn_next = QPushButton()
        self.btn_next.setIcon(icons.icon_down())
        self.btn_next.setProperty("role", "nav-btn")
        self.btn_next.setToolTip("Next match (F3)")
        self.btn_next.setFixedSize(24, 24)
        self._hand(self.btn_next)
        self.btn_next.clicked.connect(self._next_match)
        h.addWidget(self.btn_next, stretch=0)

        self.lbl_match = QLabel("0 / 0")
        self.lbl_match.setStyleSheet("color: #888888; font-size: 10px; min-width: 50px;")
        self.lbl_match.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h.addWidget(self.lbl_match, stretch=0)

        h.addStretch(1)

        # Options
        self.btn_autoscroll = QPushButton()
        self.btn_autoscroll.setIcon(icons.icon_autoscroll())
        self.btn_autoscroll.setProperty("role", "toggle")
        self.btn_autoscroll.setCheckable(True)
        self.btn_autoscroll.setChecked(True)
        self.btn_autoscroll.setFixedHeight(24)
        self.btn_autoscroll.setFixedWidth(28)
        self.btn_autoscroll.setToolTip("Auto-scroll: keep the view pinned to the newest logs.")
        self._hand(self.btn_autoscroll)
        self.btn_autoscroll.toggled.connect(self._on_autoscroll_toggled)
        h.addWidget(self.btn_autoscroll, stretch=0)

        self.btn_wrap = QPushButton()
        self.btn_wrap.setIcon(icons.icon_wrap())
        self.btn_wrap.setProperty("role", "toggle")
        self.btn_wrap.setCheckable(True)
        self.btn_wrap.setChecked(False)
        self.btn_wrap.setFixedHeight(24)
        self.btn_wrap.setFixedWidth(28)
        self.btn_wrap.setToolTip("Wrap: wrap long lines instead of scrolling horizontally.")
        self._hand(self.btn_wrap)
        self.btn_wrap.toggled.connect(self._toggle_wrap)
        h.addWidget(self.btn_wrap, stretch=0)

        return bar

    # ── Shortcuts ─────────────────────────────────────────────────────────────

    def _setup_shortcuts(self):
        # Cmd+F - focus search
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self.search_edit.setFocus)
        
        # Alt+G - toggle grep
        QShortcut(QKeySequence("Alt+G"), self).activated.connect(self.btn_grep.toggle)
        
        # F3 / Shift+F3 - next/prev match
        QShortcut(QKeySequence("F3"), self).activated.connect(self._next_match)
        QShortcut(QKeySequence("Shift+F3"), self).activated.connect(self._prev_match)

    # ── Log area ──────────────────────────────────────────────────────────────

    def _build_log_area(self) -> QWidget:
        container = QWidget()
        container.setContentsMargins(0, 0, 0, 0)
        h_layout = QHBoxLayout(container)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)

        self.log_view = VirtualLogView()
        fixed = QFont("Menlo", 12)
        fixed.setStyleHint(QFont.StyleHint.Monospace)
        self.log_view.setFont(fixed)
        self.log_view.set_show_line_numbers(Settings().show_line_numbers)
        self.log_view.set_wrap_enabled(False)

        h_layout.addWidget(self.log_view, stretch=1)
        return container

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_responsive_layout(event.size().width())

    def _update_responsive_layout(self, width: int):
        compact = width < 900
        tight = width < 780
        tiny = width < 700
        micro = width < 620

        self.lbl_device.setVisible(not compact)
        self.lbl_pkg.setVisible(not compact)

        if compact:
            self.device_combo.setMinimumWidth(90)
            self.pkg_combo.setMinimumWidth(90)
        else:
            self.device_combo.setMinimumWidth(120)
            self.pkg_combo.setMinimumWidth(120)

        self._btn_clear.setText("" if compact else " Clear")
        self._btn_copy.setText("" if compact else " Copy")
        self._btn_save.setText("" if compact else " Save")

        if tight:
            self.btn_toggle.setText("")
        else:
            self.btn_toggle.setText("Stop" if self._running else "Start")

        if compact:
            self.search_edit.setMinimumWidth(120)
        else:
            self.search_edit.setMinimumWidth(180)

        # Search row controls in very tight layouts
        self._level_chip_bar.setVisible(not tiny)
        self.btn_case.setVisible(not tiny)
        self.btn_regex.setVisible(not tiny)
        self.btn_grep.setVisible(not tiny)
        self.btn_prev.setVisible(not tiny)
        self.btn_next.setVisible(not tiny)
        self.lbl_match.setVisible(not tiny)

        if micro:
            self.search_edit.setMinimumWidth(80)
            if hasattr(self, "_search_layout"):
                self._search_layout.setSpacing(4)
                self._search_layout.setContentsMargins(6, 4, 6, 4)
            if hasattr(self, "_control_layout"):
                self._control_layout.setSpacing(6)
                self._control_layout.setContentsMargins(6, 4, 6, 4)
        else:
            if hasattr(self, "_search_layout"):
                self._search_layout.setSpacing(8)
                self._search_layout.setContentsMargins(8, 4, 8, 4)
            if hasattr(self, "_control_layout"):
                self._control_layout.setSpacing(8)
                self._control_layout.setContentsMargins(8, 4, 8, 4)

        # Compact chip sizing
        if tiny:
            for btn in self._level_chip_buttons:
                btn.setFixedWidth(22)
                btn.setFixedHeight(22)
                btn.setIconSize(QSize(10, 10))
        else:
            for btn in self._level_chip_buttons:
                btn.setFixedWidth(24)
                btn.setFixedHeight(24)
                btn.setIconSize(QSize(12, 12))


    # ── Separators ────────────────────────────────────────────────────────────

    @staticmethod
    def _build_v_sep() -> QFrame:
        f = QFrame()
        f.setFrameShape(QFrame.Shape.VLine)
        f.setStyleSheet("background: #333333; max-width: 1px; border: none; margin: 0 4px;")
        return f

    # ── Device management ─────────────────────────────────────────────────────

    def refresh_devices(self):
        current = self.device_combo.currentText()
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        devices = get_adb_devices()
        if devices:
            self.device_combo.addItems(devices)
            idx = self.device_combo.findText(current)
            if idx >= 0:
                self.device_combo.setCurrentIndex(idx)
            else:
                self.device_combo.setCurrentIndex(0)
        else:
            self.device_combo.addItem("(no devices)")
        self.device_combo.blockSignals(False)
        self._on_device_changed(self.device_combo.currentText())
        self.status_changed.emit()

    def _on_device_changed(self, device: str):
        if not device or device == "(no devices)":
            return
        self.device_selected.emit(device)
        # Clear device packages immediately and fetch for the selected device
        self._pkg_device = []
        self._rebuild_package_model(
            settings_pkgs=self._pkg_settings,
            device_pkgs=[],
            current_pkg=self._selected_package(),
            filter_text=self._pkg_filter_text,
        )
        QTimer.singleShot(100, lambda d=device: self._fetch_device_packages(d))

    def _on_package_changed(self, package: str):
        """Save package selection to settings."""
        pkg = (package or "").strip()
        if pkg.lower() == "global":
            pkg = ""

        if pkg == self._last_package:
            return

        if self._running:
            result = QMessageBox.question(
                self,
                "Switch Package?",
                "Changing the package will clear current logs and restart capture. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if result != QMessageBox.StandardButton.Yes:
                # Revert selection
                self.pkg_combo.blockSignals(True)
                self.pkg_combo.setCurrentText(self._last_package or "Global")
                self.pkg_combo.blockSignals(False)
                return

            self.clear_log(confirm=False)
            self._pending_restart = True
            self.stop_capture()

        # Save selection
        self._settings.default_package = pkg
        self._settings.save()
        self._last_package = pkg

    def _selected_package(self) -> str:
        """Return normalized package text; empty means Global."""
        pkg = (self.pkg_combo.currentText() or "").strip()
        if not pkg or pkg.lower() == "global":
            return ""
        return pkg

    def _fetch_device_packages(self, device: str | None = None):
        device = device or self.device_combo.currentText()
        if not device or device == "(no devices)":
            return
        if device != self.device_combo.currentText():
            return
        
        try:
            from src.utils.adb_utils import get_adb_path
            import subprocess
            adb_path = get_adb_path()
            cmd = [adb_path, "-s", device, "shell", "pm", "list", "packages"]
            res = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=3)
            if res.returncode == 0:
                pkgs = [line.split(":")[1].strip() for line in res.stdout.splitlines() if ":" in line]
                pkgs.sort()
                
                current_pkg = self._selected_package()
                from src.core.settings import Settings
                s = Settings()
                self._pkg_device = list(pkgs)
                self._rebuild_package_model(
                    settings_pkgs=s.packages,
                    device_pkgs=pkgs,
                    current_pkg=current_pkg,
                    filter_text=self._pkg_filter_text,
                )
        except Exception:
            pass

    # ── Package management ────────────────────────────────────────────────────

    def _load_packages(self):
        from src.core.settings import Settings
        s = Settings()
        self._rebuild_package_model(
            settings_pkgs=s.packages,
            device_pkgs=self._pkg_device,
            current_pkg=s.default_package,
            filter_text=self._pkg_filter_text,
        )

    def reload_packages(self):
        current = self._selected_package()
        self._load_packages()
        self.pkg_combo.setCurrentText(current or "Global")

    def _rebuild_package_model(self, settings_pkgs: list[str], device_pkgs: list[str], current_pkg: str, filter_text: str):
        self.pkg_combo.blockSignals(True)
        self._pkg_settings = list(settings_pkgs)
        self._pkg_device = list(device_pkgs)

        top_items = ["Global"] + [p for p in settings_pkgs if p and p != "Global"]
        seen = set(settings_pkgs)
        lower_items = [p for p in device_pkgs if p and p not in seen]

        self.pkg_combo.set_sectioned_items(top_items, lower_items, filter_text)

        # Restore selection or default to Global
        target = (current_pkg or "").strip()
        if not target:
            target = "Global"

        self.pkg_combo.setCurrentText(target)

        self.pkg_combo.blockSignals(False)

    def _on_pkg_filter_changed(self, text: str):
        self._pkg_filter_text = (text or "").strip()
        self._rebuild_package_model(
            settings_pkgs=self._pkg_settings,
            device_pkgs=self._pkg_device,
            current_pkg=self._selected_package(),
            filter_text=self._pkg_filter_text,
        )

    # ── Capture ───────────────────────────────────────────────────────────────

    def toggle_capture(self):
        if self._running:
            self.stop_capture()
        else:
            self.start_capture()

    def start_capture(self):
        if self._running:
            return
        if self._reader and self._reader.isRunning():
            return
        device = self.device_combo.currentText()
        if not device or device == "(no devices)":
            return
        package = self._selected_package()
        self._running = True
        
        # Update Toggle Button
        self.btn_toggle.setText("Stop")
        self.btn_toggle.setIcon(icons.icon_stop())
        self.btn_toggle.setProperty("role", "stop")
        self.btn_toggle.style().unpolish(self.btn_toggle)
        self.btn_toggle.style().polish(self.btn_toggle)
        
        self.status_changed.emit()

        from src.core.pidcat_runner import get_pidcat_path, get_python_executable
        from src.core.settings import SettingsManager
        import sys as _sys

        pidcat_path = get_pidcat_path()
        package = self._selected_package()
        device = self.device_combo.currentText()
        settings = SettingsManager.load()

        # Build pidcat arguments in correct order:
        # pidcat.py [package] [-s device] [-w padding] [-i ignored] ...
        pidcat_args = []
        if package:
            pidcat_args.append(package)
        if device and device != "(no devices)":
            pidcat_args.extend(['-s', device])

        tag_padding = settings.get("tag_padding", 16)
        try:
            tag_padding = int(tag_padding)
        except Exception:
            tag_padding = 16
        if tag_padding >= 4:
            pidcat_args.extend(['-w', str(tag_padding)])
        ignored_tags = settings.get("ignored_tags", [])
        for tag in ignored_tags:
            pidcat_args.extend(['-i', tag])

        # Use subprocess with --child-pidcat flag for bundled mode
        # This avoids the exec() approach which can cause segfaults on Linux
        if getattr(_sys, 'frozen', False):
            # Bundled mode: use FadCat binary with --child-pidcat flag
            python_executable = get_python_executable()
            cmd = [python_executable, '--child-pidcat', '--package', pidcat_path] + pidcat_args
            # Pass environment with FORCE_COLOR_OUTPUT to ensure colors are preserved
            env = os.environ.copy()
            env['FORCE_COLOR_OUTPUT'] = '1'
            env['TERM'] = 'xterm-256color'
            env['FORCE_COLOR'] = '1'
        else:
            # Dev mode: normal subprocess with Python
            python_executable = get_python_executable()
            cmd = [python_executable, pidcat_path] + pidcat_args
            env = None

        self._reader = ProcessReader(cmd=cmd, env=env)
        self._reader.line_ready.connect(self._append_line)
        self._reader.finished.connect(self._on_reader_finished)
        self._reader.start()

    def stop_capture(self, wait: bool = True):
        """Stop logcat capture.
        
        Args:
            wait: If True, wait for thread to finish (prevents QThread crash)
        """
        if self._stopping:
            return
        self._stopping = True
        if self._reader:
            try:
                self._reader.stop()
            except Exception:
                pass
        # Always wait for thread to finish to prevent "QThread: Destroyed while thread is still running"
        if self._reader:
            self._reader.wait(1000)  # Wait up to 1 second

    def _on_reader_finished(self):
        self._running = False
        self._stopping = False
        
        # Update Toggle Button
        self.btn_toggle.setText("Start")
        self.btn_toggle.setIcon(icons.icon_play())
        self.btn_toggle.setProperty("role", "start")
        self.btn_toggle.style().unpolish(self.btn_toggle)
        self.btn_toggle.style().polish(self.btn_toggle)
        
        self._thread = None
        self._reader = None
        self.status_changed.emit()

        if self._pending_restart:
            self._pending_restart = False
            self.start_capture()

    # ── Log output ────────────────────────────────────────────────────────────

    def _append_line(self, raw: str):
        self._pending_lines.append(raw)
        if not self._flush_timer.isActive():
            self._flush_timer.start()

    def _append_parsed_line(self, text: str) -> bool:
        plain = _ANSI_STRIP.sub("", text)
        chunks = _parse_ansi(text)
        tag = _extract_tag(text)
        level = _extract_level(text)
        if level is None:
            level = _level_from_chunks(chunks)
        if level in _LEVEL_COLORS:
            line_color = _LEVEL_COLORS[level]
        else:
            line_color = _line_color_from_chunks(chunks)
            m = _LEVEL_RE.search(plain)
            if m and m.group(1) in _LEVEL_COLORS:
                line_color = _LEVEL_COLORS[m.group(1)]
        if not self._color_line_by_tag:
            line_color = None
        else:
            if tag:
                if line_color:
                    self._last_tag_color = line_color
            else:
                if level is None:
                    if line_color and self._last_tag_color is None:
                        self._last_tag_color = line_color
                    if self._last_tag_color is not None:
                        line_color = self._last_tag_color
                elif line_color:
                    self._last_tag_color = line_color
        line = LogLine(text, plain, chunks, tag, level, line_color)
        self._lines.append(line)
        idx = len(self._lines) - 1
        if self._passes_filters(line, self.search_edit.text(), self.btn_grep.isChecked()):
            self._visible_indices.append(idx)
            return True
        return False

    def _trim_if_needed(self):
        if self._max_lines > 0 and len(self._lines) > self._max_lines:
            trim = len(self._lines) - self._max_lines
            self._lines = self._lines[trim:]
            self._visible_indices = [i - trim for i in self._visible_indices if i - trim >= 0]
            if trim > 0:
                self._match_ranges = [(i - trim, s, e) for (i, s, e) in self._match_ranges if i - trim >= 0]
                if self.log_view._selection_anchor and self.log_view._selection_active:
                    a_line, a_col = self.log_view._selection_anchor
                    b_line, b_col = self.log_view._selection_active
                    a_line -= trim
                    b_line -= trim
                    if a_line < 0 or b_line < 0:
                        self.log_view._selection_anchor = None
                        self.log_view._selection_active = None
                    else:
                        self.log_view._selection_anchor = (a_line, a_col)
                        self.log_view._selection_active = (b_line, b_col)
            self.log_view.set_lines(self._lines, reset_visible=False)
            self.log_view.sync_visible_indices(self._visible_indices, incremental=False)

    def _flush_paused_buffer(self):
        new_visible_lines = False
        while self._paused_buffer:
            raw = self._paused_buffer.popleft()
            text = raw.rstrip("\n")
            if self._append_parsed_line(text):
                new_visible_lines = True
        self._trim_if_needed()
        if new_visible_lines:
            self.log_view.sync_visible_indices(self._visible_indices, incremental=False)

    def _flush_pending_lines(self):
        if not self._pending_lines:
            self._flush_timer.stop()
            return

        batch = 0
        max_batch = 200
        file_buf = []
        new_visible = False
        anchor = None
        frozen_scroll = None
        freeze_view = not self.btn_autoscroll.isChecked()
        if freeze_view:
            frozen_scroll = self.log_view.verticalScrollBar().value()
            anchor = self.log_view.capture_anchor()
        while self._pending_lines and batch < max_batch:
            raw = self._pending_lines.popleft()
            file_buf.append(raw)
            self._total_lines += 1
            if freeze_view:
                self._paused_buffer.append(raw)
                self._paused_count += 1
            else:
                text = raw.rstrip("\n")
                if self._append_parsed_line(text):
                    new_visible = True
            batch += 1

        if not freeze_view:
            self._trim_if_needed()

        if new_visible and not freeze_view:
            self.log_view.sync_visible_indices(self._visible_indices, incremental=True)

        if file_buf and self._log_fp:
            try:
                self._log_fp.write("".join(file_buf))
            except Exception:
                pass

        if self.btn_autoscroll.isChecked():
            self.log_view.scroll_to_bottom()
        elif not freeze_view:
            if anchor is not None:
                self.log_view.restore_anchor(anchor)
            if frozen_scroll is not None:
                self.log_view.verticalScrollBar().setValue(
                    max(0, min(frozen_scroll, self.log_view.verticalScrollBar().maximum()))
                )
        else:
            self._update_pause_state()
    
    def _line_matches(self, plain: str, query: str) -> bool:
        if not query:
            return True
        try:
            if self.btn_regex.isChecked():
                flags = 0 if self.btn_case.isChecked() else re.IGNORECASE
                return bool(re.search(query, plain, flags))
            else:
                if self.btn_case.isChecked():
                    return query in plain
                return query.lower() in plain.lower()
        except re.error:
            return False

    def _passes_filters(self, line: LogLine, query: str, grep_mode: bool) -> bool:
        if not self._line_passes_level_filter(line.level):
            return False
        if grep_mode and query:
            return self._line_matches(line.plain, query)
        return True

    def _line_passes_level_filter(self, level: str | None) -> bool:
        if not self._level_filters:
            return True
        if not level:
            return False
        return level in self._level_filters

    def _toggle_level_filter(self, level: str, enabled: bool):
        if enabled:
            self._level_filters.add(level)
        else:
            self._level_filters.discard(level)
        self._apply_grep_filter()

    def _apply_grep_filter(self):
        query = self.search_edit.text()
        grep_mode = self.btn_grep.isChecked()
        self._grep_active = grep_mode
        
        # Stop highlight timer and clear pending highlights
        if self._selection_timer.isActive():
            self._selection_timer.stop()
        self._pending_ranges = []
        self._applied_selections = []
        
        indices = []
        for i, line in enumerate(self._lines):
            if self._passes_filters(line, query, grep_mode):
                indices.append(i)
        self._visible_indices = indices
        self.log_view.sync_visible_indices(indices, incremental=False)
        
        # Only show highlights if there's a search query and matches exist
        if query and self._match_ranges:
            self.log_view.set_highlights(self._match_ranges, self._match_idx)
        else:
            self.log_view.set_highlights([], None)

    def _apply_highlights(self, query: str):
        if not query:
            # Stop highlight batching timer to prevent old highlights from rendering
            if self._selection_timer.isActive():
                self._selection_timer.stop()
            # Clear all highlight data
            self._match_positions = []
            self._match_ranges = []
            self._match_idx = 0
            self._pending_ranges = []
            self._applied_selections = []
            # Clear highlights from view
            self.log_view.set_highlights([], None)
            self._update_line_count_label()
            return
        self._start_async_search(query)

    def _start_async_search(self, query: str):
        self._search_seq += 1
        seq = self._search_seq
        lines = [l.plain for l in self._lines]
        fuzzy = self.btn_fuzzy.isChecked()
        regex = self.btn_regex.isChecked() and not fuzzy  # Fuzzy takes priority
        case = self.btn_case.isChecked()

        if self._search_thread:
            self._search_thread.quit()
            self._search_thread.wait(50)
        self._search_thread = QThread(self)
        self._search_worker = _SearchWorker(seq, lines, query, regex, case, fuzzy)
        self._search_worker.moveToThread(self._search_thread)
        self._search_thread.started.connect(self._search_worker.run)
        self._search_worker.finished.connect(self._on_search_results)
        self._search_worker.finished.connect(self._search_thread.quit)
        self._search_thread.start()

    def _on_search_results(self, seq: int, ranges: list[tuple[int, int, int]]):
        if seq != self._search_seq:
            return
        self._match_ranges = ranges
        self._match_positions = [s for s, _, _ in ranges]
        self._match_idx = 0 if ranges else 0

        # Stop old batching if running and reset batching state
        if self._selection_timer.isActive():
            self._selection_timer.stop()
        self._pending_ranges = ranges[:]
        self._applied_selections = []
        
        # If we have results, immediately jump to first finding and show it
        if ranges:
            line_idx, start, end = ranges[0]
            self.log_view.scroll_to_line(line_idx)
        
        # Restart batching with new ranges
        self._selection_timer.start()
        self._update_line_count_label()

    def _apply_selection_batch(self):
        if not self._pending_ranges:
            self._selection_timer.stop()
            # Always show current match highlighted (yellow) when done batching
            self.log_view.set_highlights(self._match_ranges, self._match_idx if self._match_ranges else None)
            return

        batch = 0
        max_batch = 300
        while self._pending_ranges and batch < max_batch:
            idx, start, end = self._pending_ranges.pop(0)
            if start == end:
                continue
            self._applied_selections.append((idx, start, end))
            batch += 1
        # Show current match (index 0) highlighted during batching too
        self.log_view.set_highlights(self._match_ranges, self._match_idx if self._match_ranges else None)

    def _update_line_count_label(self):
        count = len(self._match_positions)
        if count > 0:
            self.lbl_match.setText(f"{min(self._match_idx + 1, count)} / {count}")
        else:
            self.lbl_match.setText("0 / 0")
        self.status_changed.emit()

    def _restore_all_lines(self):
        self._grep_active = False
        indices = [i for i, line in enumerate(self._lines) if self._line_passes_level_filter(line.level)]
        self._visible_indices = indices
        self.log_view.sync_visible_indices(indices, incremental=False)
        if self._match_ranges:
            self.log_view.set_highlights(self._match_ranges, self._match_idx)

    # ── Search / highlight ────────────────────────────────────────────────────

    def _on_search_changed(self):
        # Make fuzzy and regex mutually exclusive
        sender = self.sender()
        if sender == self.btn_fuzzy and self.btn_fuzzy.isChecked():
            self.btn_regex.setChecked(False)
        elif sender == self.btn_regex and self.btn_regex.isChecked():
            self.btn_fuzzy.setChecked(False)
        
        self._search_timer.start()

    def _apply_search_now(self):
        query = self.search_edit.text()
        if self.btn_grep.isChecked():
            self._apply_grep_filter()
        else:
            if self._grep_active:
                self._restore_all_lines()
            self._apply_highlights(query)

    def _prev_match(self):
        if self._match_positions:
            self._match_idx = (self._match_idx - 1) % len(self._match_positions)
            self._jump_to_match()

    def _next_match(self):
        if self._match_positions:
            self._match_idx = (self._match_idx + 1) % len(self._match_positions)
            self._jump_to_match()

    def _jump_to_match(self):
        if not self._match_ranges:
            return
        line_idx, _start, _end = self._match_ranges[self._match_idx]
        self.log_view.scroll_to_line(line_idx)
        self.log_view.set_highlights(self._match_ranges, self._match_idx)
        count = len(self._match_positions)
        self.lbl_match.setText(f"{self._match_idx + 1} / {count}")

    def _toggle_wrap(self, checked: bool):
        self.log_view.set_wrap_enabled(checked)

    def _on_autoscroll_toggled(self, checked: bool):
        if checked:
            self._resume_from_pause()
            self.log_view.sync_visible_indices(self._visible_indices, incremental=False)
            self.log_view.scroll_to_bottom()
        self.status_changed.emit()

    def _update_pause_state(self):
        self.status_changed.emit()

    def _resume_from_pause(self):
        if self._paused_buffer:
            self._flush_paused_buffer()
        self._paused_count = 0
        self.status_changed.emit()
    # ── Actions ───────────────────────────────────────────────────────────────

    def clear_log(self, confirm: bool = True):
        if confirm:
            repl = QMessageBox.question(
                self,
                "Clear Log?",
                "This will clear the visible log view. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if repl != QMessageBox.StandardButton.Yes:
                return
        self.log_view.clear()
        self._total_lines = 0
        self._lines.clear()
        self._visible_indices.clear()
        self._pending_lines.clear()
        if self._flush_timer.isActive():
            self._flush_timer.stop()
        if self._log_fp:
            try:
                self._log_fp.close()
            except Exception:
                pass
            try:
                self._log_fp = open(self._log_path, "w", encoding="utf-8", buffering=1)
            except Exception:
                self._log_fp = None
        self._visible_line_count = 0
        self._match_positions = []
        self._match_idx = 0
        self.lbl_match.setText("0 / 0")
        self.status_changed.emit()

    def copy_log(self):
        QApplication.clipboard().setText(self.log_view.plain_text(visible_only=True))

    def save_log(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save log", f"logcat_{datetime.now():%Y%m%d_%H%M%S}.txt",
            "Text files (*.txt);;All files (*)"
        )
        if path:
            if Settings().save_screen_only:
                Path(path).write_text(self.log_view.plain_text(visible_only=True), encoding="utf-8")
                return
            if self._log_fp:
                try:
                    self._log_fp.flush()
                except Exception:
                    pass
            if self._log_path.exists():
                try:
                    shutil.copyfile(self._log_path, path)
                    return
                except Exception:
                    pass
            Path(path).write_text(self.log_view.plain_text(visible_only=True), encoding="utf-8")

    def refresh_display(self):
        """Refresh display for settings changes (watermark opacity, line numbers)."""
        # Update line numbers visibility
        show_lines = Settings().show_line_numbers
        self.log_view.set_show_line_numbers(show_lines)
        new_color_by_tag = Settings().color_line_by_tag
        if new_color_by_tag != self._color_line_by_tag:
            self._color_line_by_tag = new_color_by_tag
            self._recompute_line_colors()
            self.log_view.clear_layout_cache()
        # Update max lines for log view
        new_max = max(0, int(Settings().log_view_max_lines))
        if new_max != self._max_lines:
            self._max_lines = new_max
            if self._max_lines > 0 and len(self._lines) > self._max_lines:
                trim = len(self._lines) - self._max_lines
                self._lines = self._lines[trim:]
                self._visible_indices = [i - trim for i in self._visible_indices if i - trim >= 0]
        self.log_view.sync_visible_indices(self._visible_indices, incremental=False)
        self.log_view.viewport().update()

    def _recompute_line_colors(self):
        self._last_tag_color = None
        for line in self._lines:
            if not self._color_line_by_tag:
                line.line_color = None
                continue
            level = line.level
            if level is None:
                level = _level_from_chunks(line.chunks)
            if level in _LEVEL_COLORS:
                line_color = _LEVEL_COLORS[level]
            else:
                line_color = _line_color_from_chunks(line.chunks)
                m = _LEVEL_RE.search(line.plain)
                if m and m.group(1) in _LEVEL_COLORS:
                    line_color = _LEVEL_COLORS[m.group(1)]
            if line.tag:
                if line_color:
                    self._last_tag_color = line_color
            else:
                if level is None:
                    if line_color and self._last_tag_color is None:
                        self._last_tag_color = line_color
                    if self._last_tag_color is not None:
                        line_color = self._last_tag_color
                elif line_color:
                    self._last_tag_color = line_color
            line.line_color = line_color

    # ── Public helpers ────────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def line_count(self) -> int:
        if self._visible_indices:
            return len(self._visible_indices)
        return 0

    @property
    def total_line_count(self) -> int:
        return self._total_lines

    @property
    def paused_count(self) -> int:
        return self._paused_count

    @property
    def is_paused(self) -> bool:
        return not self.btn_autoscroll.isChecked()

    def resume_from_pause(self):
        self.btn_autoscroll.setChecked(True)

    @property
    def current_device(self) -> str:
        return self.device_combo.currentText()

    @property
    def current_package(self) -> str:
        return self._selected_package()
