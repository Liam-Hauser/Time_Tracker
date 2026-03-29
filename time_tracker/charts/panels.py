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

from ..core.analytics import RangeStats, WeeklyComparison, date_range
from ..core.models import Task, fmt_dur
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
        self.setFixedHeight(fixed_height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAttribute(Qt.WA_OpaquePaintEvent)

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
                     font_size: int = 9) -> None:
        """Horizontal wrapping legend."""
        f = _font(font_size)
        p.setFont(f)
        fm = QFontMetrics(f)
        DOT, GAP_TEXT, GAP_ITEM, ITEM_H = 8, 4, 16, 18
        x, y = x0, y0
        for task in tasks:
            name = task.name if len(task.name) <= 16 else task.name[:14] + "…"
            item_w = DOT + GAP_TEXT + fm.horizontalAdvance(name) + GAP_ITEM
            if x + item_w > x0 + max_w and x > x0:
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
    """Daily tracked time as stacked filled areas per task."""

    _PAD = (20, 16, 56, 56)   # extra bottom for legend

    def __init__(self, parent=None):
        super().__init__(fixed_height=300, parent=parent)

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

        # Axes labels
        self._draw_y_labels(p, rect, ticks, max_h)
        self._draw_x_date_labels(p, rect, days)

        # Legend below x-axis
        pt, pr, pb, pl = self._PAD
        self._draw_legend(p, list(reversed(active)),
                          pl, self.height() - pb + 24,
                          self.width() - pl - pr)


# ──────────────────────────────────────────────────────────
# 2. Weekday pattern — avg hours per weekday, stacked
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
        self.setFixedHeight(max(160, self._PAD[0] + n * 30 + self._PAD[2]))
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
                    p.setPen(QColor(255, 255, 255, 180))
                    p.drawText(cell, Qt.AlignCenter, f"{val:.1f}")


# ──────────────────────────────────────────────────────────
# 4. Weekly comparison — horizontal grouped bars
# ──────────────────────────────────────────────────────────

class WeeklyCompChart(NativeChart):
    _PAD = (8, 80, 12, 0)   # right: delta labels, left: task names drawn manually

    def __init__(self, parent=None):
        super().__init__(fixed_height=200, parent=parent)

    def refresh_comparison(self, comp: WeeklyComparison) -> None:
        self._comp = comp
        all_tasks  = {t.name: t
                      for t in comp.this_week.active_tasks
                               + comp.last_week.active_tasks}
        n = max(len(all_tasks), 1)
        self.setFixedHeight(max(140, 24 + n * 36 + 16))
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
        PAD_T = 8

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
