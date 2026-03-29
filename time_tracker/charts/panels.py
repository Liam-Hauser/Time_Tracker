"""
charts/panels.py — Individual chart widgets, each self-contained.
Each panel receives a RangeStats object and re-draws itself.
"""

from __future__ import annotations
from datetime import date, timedelta
from typing import Optional

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QSizePolicy

from ..core.analytics import RangeStats, WeeklyComparison
from ..core.models import Task, fmt_dur
from ..ui.theme import (
    apply_matplotlib_theme, MPL_BG, MPL_BG2, MPL_TEXT,
    MPL_MUTED, MPL_GRID, ACCENT, BORDER, WEEKDAY_SHORT,
)


def _hex_to_rgba(hex_colour: str, alpha: float = 1.0):
    """Convert '#rrggbb' to (r,g,b,a) floats."""
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i:i+2], 16) / 255 for i in (0, 2, 4))
    return (r, g, b, alpha)


class BaseChart(QWidget):
    """Common base: holds a Figure + Canvas, provides clear/resize helpers."""

    def __init__(self, figsize=(6, 3), parent=None):
        super().__init__(parent)
        apply_matplotlib_theme()
        self.fig    = Figure(figsize=figsize, tight_layout=True)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)

    def _clear(self) -> None:
        self.fig.clear()

    def _draw(self) -> None:
        self.canvas.draw_idle()

    def refresh(self, stats: RangeStats) -> None:
        raise NotImplementedError


# ──────────────────────────────────────────────────────────
# 1. Pie chart
# ──────────────────────────────────────────────────────────
class PieChart(BaseChart):
    def __init__(self, parent=None):
        super().__init__(figsize=(5, 3.5), parent=parent)

    def refresh(self, stats: RangeStats) -> None:
        self._clear()
        ax = self.fig.add_subplot(111)
        active = stats.active_tasks
        if not active:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    transform=ax.transAxes, color=MPL_MUTED)
            self._draw()
            return

        sizes  = [stats.task_seconds[t.name] for t in active]
        labels = [t.name for t in active]
        colours = [_hex_to_rgba(t.colour) for t in active]

        wedges, texts, autotexts = ax.pie(
            sizes, labels=None, colors=colours,
            autopct=lambda p: f"{p:.1f}%" if p > 3 else "",
            startangle=90, pctdistance=0.75,
            wedgeprops={"linewidth": 0.5, "edgecolor": MPL_BG},
        )
        for at in autotexts:
            at.set_fontsize(8)
            at.set_color(MPL_TEXT)

        ax.legend(
            wedges, [f"{l} ({fmt_dur(s, short=True)})"
                     for l, s in zip(labels, sizes)],
            loc="center left", bbox_to_anchor=(1, 0.5),
            fontsize=8, framealpha=0.3,
        )
        ax.set_title("Time per task", fontsize=10, pad=6)
        self._draw()


# ──────────────────────────────────────────────────────────
# 2. Horizontal bar (task totals)
# ──────────────────────────────────────────────────────────
class TaskBarChart(BaseChart):
    def __init__(self, parent=None):
        super().__init__(figsize=(6, 3.5), parent=parent)

    def refresh(self, stats: RangeStats) -> None:
        self._clear()
        ax = self.fig.add_subplot(111)
        active = stats.active_tasks
        if not active:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    transform=ax.transAxes, color=MPL_MUTED)
            self._draw()
            return

        names   = [t.name for t in active]
        seconds = [stats.task_seconds[n] for n in names]
        colours = [t.colour for t in active]

        y = np.arange(len(names))
        bars = ax.barh(y, seconds, color=colours, height=0.55)
        ax.set_yticks(y)
        ax.set_yticklabels(names, fontsize=9)
        ax.xaxis.set_major_formatter(
            plt_formatter(lambda v, _: f"{v/3600:.1f}h")
        )
        ax.set_xlabel("Hours", fontsize=9, color=MPL_MUTED)
        ax.set_title("Time per task", fontsize=10, pad=6)
        ax.invert_yaxis()
        self._draw()


# ──────────────────────────────────────────────────────────
# 3. Weekday stacked bar
# ──────────────────────────────────────────────────────────
class WeekdayChart(BaseChart):
    def __init__(self, parent=None):
        super().__init__(figsize=(6, 3.5), parent=parent)

    def refresh(self, stats: RangeStats) -> None:
        self._clear()
        ax = self.fig.add_subplot(111)
        active = stats.active_tasks
        if not active:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    transform=ax.transAxes, color=MPL_MUTED)
            self._draw()
            return

        x      = np.arange(7)
        bottom = np.zeros(7)
        most_consistent = stats.most_consistent_weekday()

        for t in active:
            vals = np.array([
                stats.avg_by_weekday.get(wd, {}).get(t.name, 0) / 3600
                for wd in range(7)
            ])
            ax.bar(x, vals, bottom=bottom, color=t.colour,
                   label=t.name, width=0.65)
            bottom += vals

        # Highlight most consistent weekday
        if most_consistent is not None:
            ax.axvline(most_consistent, color=ACCENT, linewidth=1.2,
                       linestyle="--", alpha=0.7)

        ax.set_xticks(x)
        ax.set_xticklabels(WEEKDAY_SHORT, fontsize=9)
        ax.set_ylabel("Avg hours / day", fontsize=9, color=MPL_MUTED)
        ax.set_title("Average time by weekday", fontsize=10, pad=6)
        self._draw()


# ──────────────────────────────────────────────────────────
# 4. Daily line chart
# ──────────────────────────────────────────────────────────
class DailyLineChart(BaseChart):
    def __init__(self, parent=None):
        super().__init__(figsize=(8, 3), parent=parent)

    def refresh(self, stats: RangeStats) -> None:
        import matplotlib.dates as mdates
        self._clear()
        ax = self.fig.add_subplot(111)
        active = stats.active_tasks
        if not active:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    transform=ax.transAxes, color=MPL_MUTED)
            self._draw()
            return

        from ..core.analytics import date_range
        days = date_range(stats.start, stats.end)
        import datetime
        xs = [datetime.datetime.combine(d, datetime.time()) for d in days]

        for t in active:
            ys = [stats.daily.get(d, {}).get(t.name, 0) / 60
                  for d in days]
            ax.plot(xs, ys, color=t.colour, linewidth=1.4,
                    label=t.name, alpha=0.9)
            ax.fill_between(xs, ys, alpha=0.08, color=t.colour)

        # Smart x-axis ticks: first, last, first of each month
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        self._set_smart_ticks(ax, days, xs)

        ax.set_ylabel("Minutes", fontsize=9, color=MPL_MUTED)
        ax.set_title("Daily time per task", fontsize=10, pad=6)
        ax.margins(x=0.01)
        self._draw()

    @staticmethod
    def _set_smart_ticks(ax, days, xs):
        import matplotlib.dates as mdates
        tick_xs, tick_labels = [], []
        seen_months = set()
        for i, (d, x) in enumerate(zip(days, xs)):
            is_first = i == 0
            is_last  = i == len(days) - 1
            is_month = d.day == 1
            if is_first or is_last or is_month:
                if is_month and not is_first:
                    lbl = d.strftime("%b '%y")
                else:
                    lbl = d.strftime("%d/%m")
                tick_xs.append(x)
                tick_labels.append(lbl)
        ax.set_xticks(tick_xs)
        ax.set_xticklabels(tick_labels, fontsize=8, rotation=30, ha="right")


# ──────────────────────────────────────────────────────────
# 5. Total daily line (dual axis)
# ──────────────────────────────────────────────────────────
class TotalDailyChart(BaseChart):
    def __init__(self, parent=None):
        super().__init__(figsize=(8, 2.6), parent=parent)

    def refresh(self, stats: RangeStats) -> None:
        import datetime
        self._clear()
        ax = self.fig.add_subplot(111)

        from ..core.analytics import date_range
        days = date_range(stats.start, stats.end)
        xs   = [datetime.datetime.combine(d, datetime.time()) for d in days]
        ys   = [stats.total_by_day.get(d, 0) / 60 for d in days]

        ax.plot(xs, ys, color=ACCENT, linewidth=2)
        ax.fill_between(xs, ys, alpha=0.12, color=ACCENT)

        ax2 = ax.twinx()
        ax2.set_ylim(ax.get_ylim()[0] / 60, ax.get_ylim()[1] / 60)
        ax2.yaxis.set_major_formatter(
            plt_formatter(lambda v, _: f"{v:.1f}h")
        )
        ax2.tick_params(labelsize=8, colors=MPL_MUTED)
        ax2.set_facecolor("none")

        DailyLineChart._set_smart_ticks(ax, days, xs)
        ax.set_ylabel("Minutes", fontsize=9, color=MPL_MUTED)
        ax.set_title("Total daily time", fontsize=10, pad=6)
        ax.margins(x=0.01)
        self._draw()


# ──────────────────────────────────────────────────────────
# 6. Hour-of-day heatmap
# ──────────────────────────────────────────────────────────
class HourHeatmap(BaseChart):
    def __init__(self, parent=None):
        super().__init__(figsize=(8, 3.2), parent=parent)

    def refresh(self, stats: RangeStats) -> None:
        self._clear()
        active = stats.active_tasks
        if not active:
            ax = self.fig.add_subplot(111)
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    transform=ax.transAxes, color=MPL_MUTED)
            self._draw()
            return

        n_tasks = len(active)
        ax = self.fig.add_subplot(111)

        data = np.zeros((n_tasks, 24))
        for i, t in enumerate(active):
            for h in range(24):
                data[i, h] = stats.by_hour.get(h, {}).get(t.name, 0) / 3600

        im = ax.imshow(
            data, aspect="auto", cmap="Blues",
            extent=[-0.5, 23.5, n_tasks - 0.5, -0.5],
            vmin=0,
        )
        ax.set_yticks(range(n_tasks))
        ax.set_yticklabels([t.name for t in active], fontsize=8)
        ax.set_xticks(range(0, 24, 2))
        ax.set_xticklabels(
            [f"{h:02d}:00" for h in range(0, 24, 2)],
            fontsize=7, rotation=45, ha="right"
        )
        self.fig.colorbar(im, ax=ax, label="Hours", shrink=0.8)
        ax.set_title("Time-of-day heatmap", fontsize=10, pad=6)
        self._draw()


# ──────────────────────────────────────────────────────────
# 7. Weekly comparison bar
# ──────────────────────────────────────────────────────────
class WeeklyComparisonChart(BaseChart):
    def __init__(self, parent=None):
        super().__init__(figsize=(7, 3), parent=parent)

    def refresh_comparison(self, comp: WeeklyComparison) -> None:
        self._clear()
        ax = self.fig.add_subplot(111)

        tasks_tw = comp.this_week.active_tasks
        tasks_lw = comp.last_week.active_tasks
        all_tasks = {t.name: t for t in tasks_tw + tasks_lw}

        if not all_tasks:
            ax.text(0.5, 0.5, "No data", ha="center", va="center",
                    transform=ax.transAxes, color=MPL_MUTED)
            self._draw()
            return

        names = list(all_tasks.keys())
        x     = np.arange(len(names))
        w     = 0.35

        tw_vals = [comp.this_week.task_seconds.get(n, 0) / 3600 for n in names]
        lw_vals = [comp.last_week.task_seconds.get(n, 0) / 3600 for n in names]
        colours = [all_tasks[n].colour for n in names]

        ax.bar(x - w/2, lw_vals, w, color=colours, alpha=0.45, label="Last week")
        ax.bar(x + w/2, tw_vals, w, color=colours, alpha=0.9,  label="This week")

        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=30, ha="right", fontsize=8)
        ax.set_ylabel("Hours", fontsize=9, color=MPL_MUTED)
        ax.set_title("This week vs last week", fontsize=10, pad=6)
        ax.legend(fontsize=8)
        self._draw()

    def refresh(self, stats: RangeStats) -> None:
        pass  # driven by refresh_comparison


# ──────────────────────────────────────────────────────────
# Matplotlib ticker helper (avoids import in every class)
# ──────────────────────────────────────────────────────────
import matplotlib.ticker as mticker

def plt_formatter(fn):
    return mticker.FuncFormatter(fn)
