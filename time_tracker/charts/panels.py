"""
charts/panels.py — All chart widgets rendered with QPainter.
No matplotlib; everything is native Qt for performance and crisp scaling.
"""

from __future__ import annotations
import math
from datetime import date, timedelta
from typing import Optional

from PyQt5.QtCore import Qt, QRect, QRectF, QPointF, QSizeF
from PyQt5.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QFontMetrics,
    QPainterPath, QLinearGradient,
)
from PyQt5.QtWidgets import QWidget, QSizePolicy

from ..core.analytics import RangeStats, WeeklyComparison, date_range, TaskSessionStats
from ..core.models import Task, GoalSpec, fmt_dur
from ..ui.theme import (
    BG2, BG3, BG4, BORDER, BORDER2,
    TEXT, MUTED, FAINT, ACCENT, SUCCESS, WARNING, DANGER,
    WEEKDAY_SHORT,
)


# ──────────────────────────────────────────────────────────
# Drawing helpers
# ──────────────────────────────────────────────────────────

def _font(size: int = 9, bold: bool = False) -> QFont:
    f = QFont("Segoe UI", size)
    f.setBold(bold)
    f.setHintingPreference(QFont.PreferFullHinting)
    return f


def _nice_ticks(max_val: float, n: int = 5) -> list[float]:
    if max_val <= 0:
        return [0.0]
    raw = max_val / n
    mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    for ns in [0.1, 0.2, 0.25, 0.5, 1, 2, 2.5, 5, 10]:
        if ns * mag >= raw:
            step = ns * mag
            break
    else:
        step = mag
    ticks = []
    v = 0.0
    while v <= max_val * 1.05:
        ticks.append(round(v, 8))
        v += step
    return ticks


def _smart_date_ticks(days: list[date],
                      max_n: int = 8) -> list[tuple[int, str]]:
    n = len(days)
    if n == 0:
        return []
    if n <= max_n:
        return [(i, days[i].strftime("%d %b")) for i in range(n)]
    result, seen = [], set()
    for i, d in enumerate(days):
        label = None
        if i == 0:
            label = d.strftime("%d %b")
        elif i == n - 1:
            label = d.strftime("%d %b")
        elif d.day == 1:
            label = d.strftime("%b '%y")
        if label is not None and i not in seen:
            result.append((i, label))
            seen.add(i)
    return result


# ──────────────────────────────────────────────────────────
# Base chart widget
# ──────────────────────────────────────────────────────────

class NativeChart(QWidget):
    """Base for all QPainter charts."""

    _PAD = (20, 16, 48, 56)   # top, right, bottom, left

    def __init__(self, fixed_height: int = 280, parent=None):
        super().__init__(parent)
        self._stats: Optional[RangeStats] = None
        self._default_h = fixed_height
        self.setMinimumHeight(fixed_height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAttribute(Qt.WA_OpaquePaintEvent)

    def sizeHint(self):
        from PyQt5.QtCore import QSize
        return QSize(400, self._default_h)

    def _plot_rect(self) -> QRect:
        pt, pr, pb, pl = self._PAD
        return QRect(pl, pt, self.width() - pl - pr, self.height() - pt - pb)

    def refresh(self, stats: RangeStats) -> None:
        self._stats = stats
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(BG2))
        if self._stats is None:
            self._draw_no_data(p)
            return
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        self._paint(p)
        p.end()

    def _paint(self, p: QPainter) -> None:
        raise NotImplementedError

    def _draw_no_data(self, p: QPainter) -> None:
        p.setPen(QColor(FAINT))
        p.setFont(_font(10))
        p.drawText(self.rect(), Qt.AlignCenter, "No data in range")

    # ── Shared drawing utilities ─────────────────────────

    def _draw_h_grid(self, p: QPainter, rect: QRect,
                     ticks: list[float], max_val: float) -> None:
        p.setPen(QPen(QColor(BORDER), 1, Qt.SolidLine))
        for t in ticks:
            if max_val <= 0:
                break
            y = rect.bottom() - t / max_val * rect.height()
            p.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))

    def _draw_y_labels(self, p: QPainter, rect: QRect,
                       ticks: list[float], max_val: float,
                       unit: str = "h") -> None:
        p.setFont(_font(9))
        p.setPen(QColor(MUTED))
        fm = QFontMetrics(_font(9))
        for t in ticks:
            if max_val <= 0:
                break
            y = rect.bottom() - t / max_val * rect.height()
            lbl = f"{t:.1f}{unit}" if t != int(t) else f"{int(t)}{unit}"
            tw = fm.horizontalAdvance(lbl)
            p.drawText(QRectF(rect.left() - tw - 6, y - 9, tw, 18),
                       Qt.AlignRight | Qt.AlignVCenter, lbl)

    def _draw_x_date_labels(self, p: QPainter, rect: QRect,
                             days: list[date]) -> None:
        p.setFont(_font(9))
        p.setPen(QColor(MUTED))
        for idx, lbl in _smart_date_ticks(days):
            x = rect.x() + idx / max(1, len(days) - 1) * rect.width()
            p.drawText(QRectF(x - 28, rect.bottom() + 5, 56, 16),
                       Qt.AlignCenter, lbl)

    def _draw_axes(self, p: QPainter, rect: QRect) -> None:
        p.setPen(QPen(QColor(BORDER2), 1))
        p.drawLine(rect.bottomLeft(), rect.bottomRight())
        p.drawLine(rect.topLeft(), rect.bottomLeft())

    def _draw_legend(self, p: QPainter, tasks: list[Task],
                     x0: int, y0: int, max_w: int,
                     font_size: int = 9, max_rows: int = 2) -> None:
        """Horizontal wrapping legend, capped at max_rows."""
        f = _font(font_size)
        p.setFont(f)
        fm = QFontMetrics(f)
        DOT, GAP_TEXT, GAP_ITEM, ITEM_H = 8, 4, 16, 18
        x, y, row = x0, y0, 0
        for task in tasks:
            name = task.name if len(task.name) <= 16 else task.name[:14] + "…"
            item_w = DOT + GAP_TEXT + fm.horizontalAdvance(name) + GAP_ITEM
            if x + item_w > x0 + max_w and x > x0:
                row += 1
                if row >= max_rows:
                    p.setPen(QColor(MUTED))
                    p.drawText(QRectF(x, y, 20, ITEM_H), Qt.AlignVCenter, "…")
                    break
                x = x0
                y += ITEM_H
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(task.colour))
            p.drawRoundedRect(
                QRectF(x, y + (ITEM_H - DOT) / 2, DOT, DOT), 2, 2)
            p.setBrush(Qt.NoBrush)
            p.setPen(QColor(MUTED))
            p.drawText(QRectF(x + DOT + GAP_TEXT, y, item_w, ITEM_H),
                       Qt.AlignVCenter, name)
            x += item_w


# ──────────────────────────────────────────────────────────
# 1. Stacked area — daily totals with task breakdown
# ──────────────────────────────────────────────────────────

class StackedAreaChart(NativeChart):
    """Daily tracked time as stacked filled areas per task.

    Optional overlays (set via ``refresh(stats, goals)``):
    - 7-day rolling average line (dashed, ACCENT colour)
    - Required h/day horizontal reference line (dotted, WARNING colour)
    """
    _PAD = (20, 16, 80, 56)  # extra bottom padding for 2-row legend

    _PAD = (20, 16, 56, 56)   # extra bottom for legend

    def __init__(self, parent=None):
        super().__init__(fixed_height=300, parent=parent)
        self._goals: dict[str, GoalSpec] = {}

    def refresh(self, stats: RangeStats,            # type: ignore[override]
                goals: dict | None = None) -> None:
        self._stats = stats
        self._goals = goals or {}
        self.update()

    def _paint(self, p: QPainter) -> None:
        stats  = self._stats
        days   = date_range(stats.start, stats.end)
        active = sorted(stats.active_tasks,
                        key=lambda t: stats.task_seconds.get(t.name, 0))
        if not active or not days:
            self._draw_no_data(p)
            return

        rect = self._plot_rect()
        n    = len(days)

        # Max total stack per day
        day_totals = [
            sum(stats.daily.get(d, {}).get(t.name, 0) / 3600 for t in active)
            for d in days
        ]
        max_h = max(day_totals) if day_totals else 1.0
        max_h = max(max_h, 0.01)

        ticks = _nice_ticks(max_h)

        def mx(i: int) -> float:
            if n == 1:
                return rect.x() + rect.width() / 2
            return rect.x() + i / (n - 1) * rect.width()

        def my(h: float) -> float:
            return rect.bottom() - h / max_h * rect.height()

        # Grid
        self._draw_h_grid(p, rect, ticks, max_h)
        self._draw_axes(p, rect)

        # Stacked areas — paint smallest-first so largest covers gaps
        cumul = [0.0] * n
        for task in active:
            top_pts: list[QPointF] = []
            bot_pts: list[QPointF] = []
            for i, d in enumerate(days):
                h = stats.daily.get(d, {}).get(task.name, 0) / 3600
                top_pts.append(QPointF(mx(i), my(cumul[i] + h)))
                bot_pts.append(QPointF(mx(i), my(cumul[i])))
                cumul[i] += h

            # Fill polygon — fully opaque so lower bands aren't hidden
            path = QPainterPath()
            path.moveTo(top_pts[0])
            for pt in top_pts[1:]:
                path.lineTo(pt)
            for pt in reversed(bot_pts):
                path.lineTo(pt)
            path.closeSubpath()
            p.fillPath(path, QBrush(QColor(task.colour)))

            # Thin dark separator line along the top edge for band visibility
            sep = QColor(0, 0, 0, 80)
            pen = QPen(sep, 1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            p.setPen(pen)
            for i in range(1, len(top_pts)):
                p.drawLine(top_pts[i - 1], top_pts[i])

        # ── Rolling 7-day average overlay ─────────────────
        if n >= 2:
            window = 7
            rolling = []
            for i in range(n):
                chunk = day_totals[max(0, i - window + 1): i + 1]
                rolling.append(sum(chunk) / len(chunk))
            roll_pen = QPen(QColor(ACCENT), 1.5, Qt.DashLine,
                            Qt.RoundCap, Qt.RoundJoin)
            p.setPen(roll_pen)
            roll_pts = [QPointF(mx(i), my(v)) for i, v in enumerate(rolling)]
            for i in range(1, len(roll_pts)):
                p.drawLine(roll_pts[i - 1], roll_pts[i])
            # Label at end
            p.setFont(_font(8))
            p.setPen(QColor(ACCENT))
            lp = roll_pts[-1]
            p.drawText(QRectF(lp.x() + 4, lp.y() - 9, 60, 18),
                       Qt.AlignVCenter, "7d avg")

        # ── Goal pace horizontal line ──────────────────────
        req_hpd = self._compute_required_hpd(stats)
        if 0 < req_hpd <= max_h * 1.5:
            y_req = my(req_hpd)
            if rect.top() <= y_req <= rect.bottom():
                pace_pen = QPen(QColor(WARNING), 1, Qt.DotLine)
                p.setPen(pace_pen)
                p.drawLine(QPointF(rect.left(), y_req),
                           QPointF(rect.right(), y_req))
                p.setFont(_font(8))
                p.setPen(QColor(WARNING))
                p.drawText(QRectF(rect.right() + 2, y_req - 9, 60, 18),
                           Qt.AlignVCenter, f"{req_hpd:.1f}h/d")

        # Axes labels
        self._draw_y_labels(p, rect, ticks, max_h)
        self._draw_x_date_labels(p, rect, days)

        # Legend below x-axis
        pt, pr, pb, pl = self._PAD
        self._draw_legend(p, list(reversed(active)),
                          pl, self.height() - pb + 24,
                          self.width() - pl - pr)

    def _compute_required_hpd(self, stats: RangeStats) -> float:
        """Sum of (remaining hours / days to deadline) across all active goals."""
        from datetime import date as _date
        today = _date.today()
        total_req = 0.0
        for task in stats.tasks:
            gs = self._goals.get(task.name)
            if gs and gs.hours > 0:
                remaining = max(0.0, gs.hours - task.total_hours)
                if remaining <= 0:
                    continue
                if gs.deadline and gs.deadline > today:
                    days = (gs.deadline - today).days
                    total_req += remaining / days
                else:
                    # No deadline: spread over range duration
                    days = max(1, (stats.end - stats.start).days + 1)
                    total_req += remaining / days
        return total_req


# ──────────────────────────────────────────────────────────
# 2. Category breakdown — horizontal bar per category
# ──────────────────────────────────────────────────────────

class CategoryBreakdownChart(NativeChart):
    """Horizontal bar chart showing total hours per category for the range."""

    _PAD = (8, 70, 8, 140)   # top, right, bottom, left (left for labels)

    def __init__(self, parent=None):
        super().__init__(fixed_height=160, parent=parent)

    def refresh(self, stats: RangeStats) -> None:  # type: ignore[override]
        self._stats = stats
        # Resize height to fit categories
        cats = set(t.tag for t in stats.active_tasks)
        n = max(1, len(cats))
        self.setMinimumHeight(self._PAD[0] + n * 38 + self._PAD[2])
        self.update()

    def _paint(self, p: QPainter) -> None:
        stats = self._stats
        if not stats.active_tasks:
            self._draw_no_data(p)
            return

        # Group tasks by category — pick the first task's colour as category colour
        cat_data: dict[str, list] = {}  # name → [hours, representative_colour]
        for task in stats.active_tasks:
            cat = task.tag
            h = stats.task_seconds.get(task.name, 0) / 3600
            if cat not in cat_data:
                cat_data[cat] = [0.0, task.colour]
            cat_data[cat][0] += h

        if not cat_data:
            self._draw_no_data(p)
            return

        sorted_cats = sorted(cat_data.items(),
                             key=lambda x: x[1][0], reverse=True)
        max_h = sorted_cats[0][1][0]
        if max_h <= 0:
            self._draw_no_data(p)
            return

        pt, pr, pb, pl = self._PAD
        n = len(sorted_cats)
        total_h = self.height() - pt - pb
        row_h = total_h / n
        bar_h = min(22, row_h * 0.55)
        bar_area_w = self.width() - pl - pr

        p.setFont(_font(10))
        for i, (cat_name, (hours, colour)) in enumerate(sorted_cats):
            yc = pt + (i + 0.5) * row_h
            bar_w = hours / max_h * bar_area_w

            # Bar
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(colour))
            p.drawRoundedRect(QRectF(pl, yc - bar_h / 2, bar_w, bar_h), 3, 3)

            # Category label (left-aligned in the reserved area)
            display = cat_name if cat_name != "none" else "Uncategorised"
            p.setPen(QColor(TEXT))
            p.drawText(QRectF(0, yc - 10, pl - 10, 20),
                       Qt.AlignRight | Qt.AlignVCenter, display)

            # Value label (right of bar)
            p.setPen(QColor(MUTED))
            p.setFont(_font(9))
            p.drawText(QRectF(pl + bar_w + 6, yc - 9, 60, 18),
                       Qt.AlignLeft | Qt.AlignVCenter, f"{hours:.1f}h")
            p.setFont(_font(10))


# ──────────────────────────────────────────────────────────
# 3. Weekday pattern — avg hours per weekday, stacked
# ──────────────────────────────────────────────────────────

class WeekdayBarChart(NativeChart):
    _PAD = (20, 16, 36, 56)

    def __init__(self, parent=None):
        super().__init__(fixed_height=270, parent=parent)

    def _paint(self, p: QPainter) -> None:
        stats  = self._stats
        active = sorted(stats.active_tasks,
                        key=lambda t: stats.task_seconds.get(t.name, 0))
        if not active:
            self._draw_no_data(p)
            return

        rect  = self._plot_rect()
        BAR_W = max(20, int(rect.width() / 7 * 0.55))
        GAP   = rect.width() / 7

        # Find max total height per weekday
        wd_totals = [
            sum(stats.avg_by_weekday.get(wd, {}).get(t.name, 0) / 3600
                for t in active)
            for wd in range(7)
        ]
        max_h  = max(wd_totals) if wd_totals else 1.0
        max_h  = max(max_h, 0.01)
        best   = wd_totals.index(max(wd_totals)) if wd_totals else -1
        ticks  = _nice_ticks(max_h)

        self._draw_h_grid(p, rect, ticks, max_h)
        self._draw_axes(p, rect)

        def bar_cx(wd: int) -> float:
            return rect.x() + wd * GAP + GAP / 2

        for wd in range(7):
            cx = bar_cx(wd)
            x0 = cx - BAR_W / 2
            cumul_h = 0.0
            for task in active:
                h = stats.avg_by_weekday.get(wd, {}).get(task.name, 0) / 3600
                if h <= 0:
                    continue
                bar_h = h / max_h * rect.height()
                y0 = rect.bottom() - (cumul_h + h) / max_h * rect.height()
                r = QRectF(x0, y0, BAR_W, bar_h)
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(task.colour))
                p.drawRoundedRect(r, 3, 3) if cumul_h == 0 else p.fillRect(r, QColor(task.colour))
                cumul_h += h

            # Best-day accent line
            if wd == best and wd_totals[wd] > 0:
                top_y = rect.bottom() - wd_totals[wd] / max_h * rect.height()
                p.setPen(QPen(QColor(ACCENT), 2))
                p.drawLine(QPointF(x0 - 2, top_y), QPointF(x0 + BAR_W + 2, top_y))

            # Value above bar
            if wd_totals[wd] > 0:
                top_y = rect.bottom() - wd_totals[wd] / max_h * rect.height()
                p.setFont(_font(8))
                p.setPen(QColor(MUTED))
                lbl = f"{wd_totals[wd]:.1f}h"
                p.drawText(QRectF(cx - 18, top_y - 16, 36, 14),
                           Qt.AlignCenter, lbl)

        # Y labels
        self._draw_y_labels(p, rect, ticks, max_h)

        # X weekday labels
        p.setFont(_font(9))
        p.setPen(QColor(TEXT))
        for wd in range(7):
            cx = bar_cx(wd)
            lbl = WEEKDAY_SHORT[wd]
            if wd == best:
                p.setPen(QColor(ACCENT))
                p.setFont(_font(9, bold=True))
            else:
                p.setPen(QColor(MUTED))
                p.setFont(_font(9))
            p.drawText(QRectF(cx - 20, rect.bottom() + 4, 40, 16),
                       Qt.AlignCenter, lbl)


# ──────────────────────────────────────────────────────────
# 3. Hour heatmap — task × hour grid
# ──────────────────────────────────────────────────────────

class HourHeatmap(NativeChart):
    _PAD = (36, 12, 28, 0)   # top for hour labels, bottom for label

    def __init__(self, parent=None):
        super().__init__(fixed_height=200, parent=parent)

    def refresh(self, stats: RangeStats) -> None:
        self._stats = stats
        n = len(stats.active_tasks)
        self.setMinimumHeight(max(160, self._PAD[0] + n * 30 + self._PAD[2]))
        self.update()

    def _paint(self, p: QPainter) -> None:
        stats  = self._stats
        active = stats.active_tasks
        if not active:
            self._draw_no_data(p)
            return

        pt, pr, pb, pl = self._PAD
        n_tasks  = len(active)
        CELL_H   = 30
        name_w   = 110   # width reserved for task names

        chart_x  = pl + name_w + 8
        chart_w  = self.width() - chart_x - pr
        cell_w   = chart_w / 24

        # Compute max hours across all cells for color scaling
        all_vals = [stats.by_hour.get(h, {}).get(t.name, 0) / 3600
                    for t in active for h in range(24)]
        max_v    = max(all_vals) if all_vals else 1.0
        max_v    = max(max_v, 0.01)

        # Hour column headers
        p.setFont(_font(8))
        p.setPen(QColor(MUTED))
        for h in range(0, 24, 2):
            cx = chart_x + (h + 0.5) * cell_w
            p.drawText(QRectF(cx - 12, 4, 24, 18),
                       Qt.AlignCenter, f"{h:02d}")

        for row, task in enumerate(active):
            y0 = pt + row * CELL_H

            # Task name
            p.setFont(_font(9))
            p.setPen(QColor(TEXT))
            name = task.name if len(task.name) <= 14 else task.name[:13] + "…"
            # Colored dot
            p.setBrush(QColor(task.colour))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QRectF(pl, y0 + (CELL_H - 8) / 2, 8, 8))
            p.setPen(QColor(TEXT))
            p.drawText(QRectF(pl + 12, y0, name_w - 12, CELL_H),
                       Qt.AlignVCenter, name)

            for h in range(24):
                val    = stats.by_hour.get(h, {}).get(task.name, 0) / 3600
                ratio  = val / max_v if max_v > 0 else 0

                # Color: blend from BG3 → task colour
                base = QColor(BG3)
                tc   = QColor(task.colour)
                r = int(base.red()   + ratio * (tc.red()   - base.red()))
                g = int(base.green() + ratio * (tc.green() - base.green()))
                b = int(base.blue()  + ratio * (tc.blue()  - base.blue()))

                cx   = chart_x + h * cell_w
                cell = QRectF(cx + 1, y0 + 2, cell_w - 2, CELL_H - 4)
                p.setBrush(QColor(r, g, b))
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(cell, 2, 2)

                # Value text if cell wide enough and value > 0
                if cell_w > 22 and val >= 0.1:
                    p.setFont(_font(7))
                    lum = 0.299 * r + 0.587 * g + 0.114 * b
                    text_rgba = (0, 0, 0, 180) if lum > 140 else (255, 255, 255, 180)
                    p.setPen(QColor(*text_rgba))
                    p.drawText(cell, Qt.AlignCenter, f"{val:.1f}")


# ──────────────────────────────────────────────────────────
# 4. Weekly comparison — horizontal grouped bars
# ──────────────────────────────────────────────────────────

class WeeklyCompChart(NativeChart):
    _PAD = (34, 80, 12, 0)  # top: space for legend; right: delta labels

    def __init__(self, parent=None):
        super().__init__(fixed_height=200, parent=parent)

    def refresh_comparison(self, comp: WeeklyComparison) -> None:
        self._comp = comp
        all_tasks  = {t.name: t
                      for t in comp.this_week.active_tasks
                               + comp.last_week.active_tasks}
        n = max(len(all_tasks), 1)
        self.setMinimumHeight(max(160, self._PAD[0] + n * 36 + self._PAD[2] + 10))
        self.update()

    def refresh(self, stats: RangeStats) -> None:
        pass   # driven by refresh_comparison

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(BG2))
        if not hasattr(self, "_comp"):
            self._draw_no_data(p)
            p.end()
            return
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        self._paint_comp(p)
        p.end()

    def _paint(self, p: QPainter) -> None:
        pass

    def _paint_comp(self, p: QPainter) -> None:
        comp = self._comp
        all_tasks = {t.name: t
                     for t in comp.this_week.active_tasks
                              + comp.last_week.active_tasks}
        if not all_tasks:
            self._draw_no_data(p)
            return

        names   = list(all_tasks.keys())
        name_w  = 110
        bar_area_x = name_w + 8
        bar_area_w = self.width() - bar_area_x - self._PAD[1]
        ROW_H = 36
        BAR_H = 11
        PAD_T = self._PAD[0]

        tw_vals = [comp.this_week.task_seconds.get(n, 0) / 3600 for n in names]
        lw_vals = [comp.last_week.task_seconds.get(n, 0) / 3600 for n in names]
        max_v   = max(max(tw_vals), max(lw_vals), 0.01)

        for i, name in enumerate(names):
            task = all_tasks[name]
            y0   = PAD_T + i * ROW_H

            # Task name + dot
            p.setBrush(QColor(task.colour))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QRectF(6, y0 + (ROW_H - 8) / 2, 8, 8))
            p.setFont(_font(9))
            p.setPen(QColor(TEXT))
            disp = name if len(name) <= 13 else name[:12] + "…"
            p.drawText(QRectF(18, y0, name_w - 18, ROW_H),
                       Qt.AlignVCenter, disp)

            tw = tw_vals[i]
            lw = lw_vals[i]

            # Last week bar (dim)
            lw_px = lw / max_v * bar_area_w
            lw_r  = QRectF(bar_area_x, y0 + ROW_H / 2 - BAR_H - 1,
                           lw_px, BAR_H)
            c = QColor(task.colour)
            c.setAlpha(70)
            p.setBrush(c)
            p.setPen(Qt.NoPen)
            if lw_px > 0:
                p.drawRoundedRect(lw_r, 2, 2)

            # This week bar (solid)
            tw_px = tw / max_v * bar_area_w
            tw_r  = QRectF(bar_area_x, y0 + ROW_H / 2 + 1,
                           tw_px, BAR_H)
            c2 = QColor(task.colour)
            c2.setAlpha(220)
            p.setBrush(c2)
            if tw_px > 0:
                p.drawRoundedRect(tw_r, 2, 2)

            # Delta label on the right
            delta  = tw - lw
            d_sign = "+" if delta >= 0 else "−"
            d_col  = SUCCESS if delta > 0 else (DANGER if delta < -0.05 else MUTED)
            d_txt  = f"{d_sign}{fmt_dur(abs(delta) * 3600, short=True)}"
            p.setFont(_font(9, bold=True))
            p.setPen(QColor(d_col))
            p.drawText(
                QRectF(bar_area_x + bar_area_w + 6, y0, 70, ROW_H),
                Qt.AlignVCenter, d_txt,
            )

        # Legend (top-right corner)
        p.setFont(_font(8))
        legend_x = self.width() - 76
        for col, (lbl, alpha) in enumerate([("Last wk", 70), ("This wk", 220)]):
            lx = legend_x
            ly = 4 + col * 14
            c = QColor(MUTED)
            c.setAlpha(alpha)
            p.setBrush(c)
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(lx, ly + 3, 24, 8), 2, 2)
            p.setPen(QColor(MUTED))
            p.drawText(QRectF(lx + 28, ly, 48, 14), Qt.AlignVCenter, lbl)


# ──────────────────────────────────────────────────────────
# 5. Category donut chart
# ──────────────────────────────────────────────────────────

class CategoryPieChart(NativeChart):
    """Donut showing relative time of each task (or category) in a RangeStats."""

    def __init__(self, parent=None):
        super().__init__(fixed_height=240, parent=parent)

    def _paint(self, p: QPainter) -> None:
        stats  = self._stats
        active = sorted(stats.active_tasks,
                        key=lambda t: stats.task_seconds.get(t.name, 0),
                        reverse=True)
        if not active:
            self._draw_no_data(p)
            return

        total = stats.grand_total_seconds
        if total <= 0:
            self._draw_no_data(p)
            return

        cx = self.width() / 2
        cy = self.height() / 2 - 10
        outer_r = min(cx, cy) - 20
        inner_r = outer_r * 0.55

        angle = 90.0  # start at top
        for task in active:
            frac   = stats.task_seconds.get(task.name, 0) / total
            span   = frac * 360.0
            rect   = QRectF(cx - outer_r, cy - outer_r, outer_r * 2, outer_r * 2)
            path   = QPainterPath()
            path.moveTo(cx, cy)
            path.arcTo(rect, angle, -span)
            path.closeSubpath()
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(task.colour))
            p.drawPath(path)
            angle -= span

        # Punch inner hole
        p.setBrush(QColor(BG2))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(cx - inner_r, cy - inner_r, inner_r * 2, inner_r * 2))

        # Center text — total hours
        from ..core.models import fmt_dur
        p.setFont(_font(11, bold=True))
        p.setPen(QColor(TEXT))
        p.drawText(QRectF(cx - 40, cy - 14, 80, 28),
                   Qt.AlignCenter, fmt_dur(total, short=True))

        # Legend at bottom
        self._draw_legend(p, active, 16, self.height() - 22, self.width() - 32)


# ──────────────────────────────────────────────────────────
# 6-9. Per-task charts  (driven by TaskSessionStats)
# ──────────────────────────────────────────────────────────

class _TaskChart(NativeChart):
    """Base for charts that take TaskSessionStats instead of RangeStats."""

    def __init__(self, fixed_height: int = 200, parent=None):
        super().__init__(fixed_height=fixed_height, parent=parent)
        self._task_stats: Optional[TaskSessionStats] = None

    def refresh(self, stats: RangeStats) -> None:  # type: ignore[override]
        pass   # not driven by RangeStats

    def refresh_task(self, task_stats: TaskSessionStats) -> None:
        self._task_stats = task_stats
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(BG2))
        if self._task_stats is None:
            self._draw_no_data(p)
            p.end()
            return
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        self._paint(p)
        p.end()


class DailyBarChart(_TaskChart):
    """One bar per day in range for a single task."""

    _PAD = (20, 16, 40, 56)

    def __init__(self, parent=None):
        super().__init__(fixed_height=200, parent=parent)

    def _paint(self, p: QPainter) -> None:
        ts   = self._task_stats
        days = date_range(ts.start, ts.end)
        vals = [ts.daily_seconds.get(d, 0.0) / 3600 for d in days]
        max_h = max(vals) if vals else 0.0
        if max_h <= 0:
            self._draw_no_data(p)
            return

        rect   = self._plot_rect()
        n      = len(days)
        ticks  = _nice_ticks(max_h)
        bar_w  = max(3, rect.width() / n * 0.6)

        self._draw_h_grid(p, rect, ticks, max_h)
        self._draw_axes(p, rect)

        colour = ts.task.colour
        for i, h in enumerate(vals):
            if h <= 0:
                continue
            x = rect.x() + (i + 0.5) / n * rect.width() - bar_w / 2
            bh = h / max_h * rect.height()
            y  = rect.bottom() - bh
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(colour))
            p.drawRoundedRect(QRectF(x, y, bar_w, bh), 2, 2)

        self._draw_y_labels(p, rect, ticks, max_h)
        self._draw_x_date_labels(p, rect, days)


class SessionHistogramChart(_TaskChart):
    """Bar chart of session duration distribution in 15-min buckets."""

    _PAD = (20, 16, 36, 56)

    def __init__(self, parent=None):
        super().__init__(fixed_height=200, parent=parent)

    # Fixed 30-min buckets: <0.5h, 0.5-1h, 1-1.5h, 1.5-2h, 2-2.5h, >2.5h
    _BUCKETS = [
        (0,    1800,  "< 0.5h"),
        (1800, 3600,  "0.5–1h"),
        (3600, 5400,  "1–1.5h"),
        (5400, 7200,  "1.5–2h"),
        (7200, 9000,  "2–2.5h"),
        (9000, None,  "> 2.5h"),
    ]

    def _paint(self, p: QPainter) -> None:
        ts = self._task_stats
        if not ts.session_durations:
            self._draw_no_data(p)
            return

        vals = []
        for lo, hi, _ in self._BUCKETS:
            count = sum(1 for s in ts.session_durations
                        if s >= lo and (hi is None or s < hi))
            vals.append(count)

        if not any(vals):
            self._draw_no_data(p)
            return

        rect   = self._plot_rect()
        n      = len(self._BUCKETS)
        max_v  = max(vals)
        colour = ts.task.colour
        bar_w  = max(4, rect.width() / n * 0.6)
        modal  = vals.index(max_v)

        for i, ((_, _, lbl), v) in enumerate(zip(self._BUCKETS, vals)):
            x  = rect.x() + (i + 0.5) / n * rect.width() - bar_w / 2
            bh = v / max_v * rect.height() if max_v > 0 else 0
            y  = rect.bottom() - bh
            c  = QColor(colour) if i == modal else QColor(BG4)
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            if bh > 0:
                p.drawRoundedRect(QRectF(x, y, bar_w, bh), 2, 2)

            p.setFont(_font(8))
            p.setPen(QColor(MUTED))
            p.drawText(QRectF(x - 8, rect.bottom() + 4, bar_w + 16, 14),
                       Qt.AlignCenter, lbl)

        self._draw_axes(p, rect)

        # Y axis: session count
        p.setFont(_font(9))
        p.setPen(QColor(MUTED))
        for v_tick in range(0, max_v + 1, max(1, max_v // 4)):
            y = rect.bottom() - v_tick / max_v * rect.height()
            p.drawText(QRectF(rect.left() - 30, y - 9, 26, 18),
                       Qt.AlignRight | Qt.AlignVCenter, str(v_tick))


class TimeOfDayBarChart(_TaskChart):
    """24-column bar chart of hours per hour-of-day for one task."""

    _PAD = (20, 16, 28, 56)

    def __init__(self, parent=None):
        super().__init__(fixed_height=180, parent=parent)

    def _paint(self, p: QPainter) -> None:
        ts     = self._task_stats
        vals   = [ts.hour_seconds.get(h, 0.0) / 3600 for h in range(24)]
        max_h  = max(vals) if vals else 0.0
        if max_h <= 0:
            self._draw_no_data(p)
            return

        rect   = self._plot_rect()
        ticks  = _nice_ticks(max_h)
        bar_w  = max(3, rect.width() / 24 * 0.7)
        colour = ts.task.colour

        self._draw_h_grid(p, rect, ticks, max_h)
        self._draw_axes(p, rect)

        for h, v in enumerate(vals):
            if v <= 0:
                continue
            x  = rect.x() + (h + 0.5) / 24 * rect.width() - bar_w / 2
            bh = v / max_h * rect.height()
            y  = rect.bottom() - bh
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(colour))
            p.drawRoundedRect(QRectF(x, y, bar_w, bh), 2, 2)

        # X labels every 4 hours
        p.setFont(_font(8))
        p.setPen(QColor(MUTED))
        for h in range(0, 24, 4):
            x = rect.x() + (h + 0.5) / 24 * rect.width()
            p.drawText(QRectF(x - 12, rect.bottom() + 3, 24, 14),
                       Qt.AlignCenter, f"{h:02d}")

        self._draw_y_labels(p, rect, ticks, max_h)


class CumulativePaceChart(_TaskChart):
    """Cumulative hours line + dashed goal trajectory (if goal set)."""

    _PAD = (20, 16, 40, 56)

    def __init__(self, parent=None):
        super().__init__(fixed_height=220, parent=parent)

    def _paint(self, p: QPainter) -> None:
        ts   = self._task_stats
        days = date_range(ts.start, ts.end)
        if not days:
            self._draw_no_data(p)
            return

        cumul   = ts.cumulative_hours_by_date(days)
        goal_h  = ts.task.goal_hours
        max_h   = max(cumul[-1] if cumul else 0.0, goal_h if goal_h > 0 else 0.0, 0.01)
        max_h  *= 1.1
        ticks   = _nice_ticks(max_h)
        rect    = self._plot_rect()
        n       = len(days)
        colour  = ts.task.colour

        self._draw_h_grid(p, rect, ticks, max_h)
        self._draw_axes(p, rect)

        def px(i: int) -> float:
            if n == 1:
                return rect.x() + rect.width() / 2
            return rect.x() + i / (n - 1) * rect.width()

        def py(h: float) -> float:
            return rect.bottom() - h / max_h * rect.height()

        # Goal dashed line
        if goal_h > 0:
            pen = QPen(QColor(FAINT), 1, Qt.DashLine)
            p.setPen(pen)
            p.drawLine(QPointF(px(0), py(0)), QPointF(px(n - 1), py(goal_h)))

        # Actual cumulative line
        pen2 = QPen(QColor(colour), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen2)
        pts = [QPointF(px(i), py(h)) for i, h in enumerate(cumul)]
        for i in range(1, len(pts)):
            p.drawLine(pts[i - 1], pts[i])

        # End-point dot
        if pts:
            p.setBrush(QColor(colour))
            p.setPen(Qt.NoPen)
            lp = pts[-1]
            p.drawEllipse(QRectF(lp.x() - 4, lp.y() - 4, 8, 8))

        self._draw_y_labels(p, rect, ticks, max_h)
        self._draw_x_date_labels(p, rect, days)

        # ETA / completion label (top-right corner)
        if goal_h > 0 and cumul:
            done_h    = cumul[-1]
            remaining = goal_h - done_h
            if remaining <= 0:
                p.setFont(_font(9, bold=True))
                p.setPen(QColor(SUCCESS))
                p.drawText(QRectF(rect.right() - 130, rect.top(), 130, 20),
                           Qt.AlignRight | Qt.AlignVCenter, "Goal reached! ✓")
            else:
                days_elapsed = max(1, (ts.end - ts.start).days + 1)
                hpd = done_h / days_elapsed
                if hpd > 0:
                    from datetime import timedelta as _td
                    eta_date = ts.end + _td(days=int(remaining / hpd))
                    eta_str = eta_date.strftime("%d %b %Y")
                    on_track = (
                        ts.task.goal_deadline is not None
                        and eta_date <= ts.task.goal_deadline
                    )
                    col = SUCCESS if on_track else WARNING
                    p.setFont(_font(9))
                    p.setPen(QColor(col))
                    p.drawText(QRectF(rect.right() - 150, rect.top(), 150, 20),
                               Qt.AlignRight | Qt.AlignVCenter,
                               f"ETA {eta_str}")
