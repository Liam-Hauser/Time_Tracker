"""
ui/tab_widgets.py — Per-category and per-task tab content widgets.
"""
from __future__ import annotations
from datetime import date, datetime
from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QPushButton,
)

from ..core.analytics import (
    RangeStats, WeeklyComparison, TaskSessionStats, category_insights,
)
from ..core.models import Task, GoalSpec, fmt_dur
from ..charts.panels import (
    StackedAreaChart, WeekdayBarChart, HourHeatmap, WeeklyCompChart,
    CategoryPieChart,
    DailyBarChart, SessionHistogramChart, TimeOfDayBarChart, CumulativePaceChart,
)
from .widgets import (
    MetricCard, InsightStrip, SessionTable, make_chart_panel,
    label, h_line,
)
from .theme import (
    BG, BG2, BG3, BORDER, TEXT, MUTED, FAINT,
    PAD_SM, PAD_MD, PAD_LG,
    ACCENT, DANGER,
)


def _today_seconds(tasks: list[Task]) -> float:
    """Sum duration of all sessions (including open) that started today."""
    today = date.today()
    total = 0.0
    for t in tasks:
        for s in t.sessions:
            if s.start.date() == today:
                total += s.duration_seconds
    return total


# ──────────────────────────────────────────────────────────
# Category tab
# ──────────────────────────────────────────────────────────

class CategoryTabWidget(QWidget):
    """Full chart view filtered to one category."""

    def __init__(self, category_name: str, parent=None):
        super().__init__(parent)
        self.category_name = category_name
        self._build()

    def _build(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {BG}; }}"
            f"QScrollBar:vertical {{ background: {BG2}; width: 4px; }}"
            f"QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 2px; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
        )
        inner = QWidget()
        inner.setStyleSheet(f"background: {BG};")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(PAD_SM, PAD_MD, PAD_MD, PAD_MD)
        lay.setSpacing(PAD_SM)

        # Metric cards (4 across)
        mc_row = QHBoxLayout()
        mc_row.setSpacing(PAD_SM)
        self._mc_today    = MetricCard("Today")
        self._mc_total    = MetricCard("Total hours")
        self._mc_sessions = MetricCard("Sessions")
        self._mc_avg      = MetricCard("Avg session")
        for mc in [self._mc_today, self._mc_total, self._mc_sessions, self._mc_avg]:
            mc_row.addWidget(mc)
        lay.addLayout(mc_row)

        # Insight strip
        self._insight_strip = InsightStrip()
        lay.addWidget(self._insight_strip)

        # Charts — same four as overview + donut
        self._stacked_chart = StackedAreaChart()
        lay.addWidget(make_chart_panel("Daily activity", self._stacked_chart))

        row2 = QHBoxLayout()
        row2.setSpacing(PAD_SM)
        self._wd_chart = WeekdayBarChart()
        row2.addWidget(make_chart_panel("Avg by weekday", self._wd_chart))
        self._wc_chart = WeeklyCompChart()
        row2.addWidget(make_chart_panel("This week vs last week", self._wc_chart))
        lay.addLayout(row2)

        self._hm_chart = HourHeatmap()
        lay.addWidget(make_chart_panel("Hour-of-day heatmap", self._hm_chart))

        self._pie_chart = CategoryPieChart()
        lay.addWidget(make_chart_panel("Task breakdown", self._pie_chart))

        lay.addStretch()
        scroll.setWidget(inner)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def refresh(self, start: date, end: date,
                all_tasks: list[Task], goals: dict) -> None:
        cat_tasks = [t for t in all_tasks if t.tag == self.category_name]
        if not cat_tasks:
            return
        stats = RangeStats(cat_tasks, start, end)

        # Today card
        today_sec = _today_seconds(cat_tasks)
        self._mc_today.update_value(
            fmt_dur(today_sec, short=True),
            f"{today_sec / 3600:.1f}h so far",
        )

        # Other metric cards
        self._mc_total.update_value(
            fmt_dur(stats.grand_total_seconds, short=True),
            f"{stats.grand_total_seconds / 3600:.1f}h total",
        )
        n_sess = sum(
            len(t.sessions_in_range(start, end)) for t in cat_tasks
        )
        self._mc_sessions.update_value(str(n_sess), f"over {stats.n_days} days")

        closed = [s for t in cat_tasks
                  for s in t.sessions_in_range(start, end)
                  if not s.is_open]
        if closed:
            avg = sum(s.duration_seconds for s in closed) / len(closed)
            self._mc_avg.update_value(fmt_dur(avg, short=True))
        else:
            self._mc_avg.update_value("—")

        # Insights
        insights = category_insights(self.category_name, all_tasks, stats)
        self._insight_strip.refresh(insights)

        # Charts
        self._stacked_chart.refresh(stats)
        self._wd_chart.refresh(stats)
        self._hm_chart.refresh(stats)
        self._pie_chart.refresh(stats)
        comp = WeeklyComparison(cat_tasks)
        self._wc_chart.refresh_comparison(comp)


# ──────────────────────────────────────────────────────────
# Task tab
# ──────────────────────────────────────────────────────────

class TaskTabWidget(QWidget):
    """Detail view for a single task."""

    # Signals relayed up to MainWindow
    edit_session_requested   = pyqtSignal(int, object, object)  # id, start, end
    delete_session_requested = pyqtSignal(int, bool)             # id, is_open
    add_session_requested    = pyqtSignal(int)                   # task_id

    def __init__(self, task: Task, parent=None):
        super().__init__(parent)
        self.task_name = task.name
        self._task     = task
        self._build()

    def _build(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {BG}; }}"
            f"QScrollBar:vertical {{ background: {BG2}; width: 4px; }}"
            f"QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 2px; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
        )
        inner = QWidget()
        inner.setStyleSheet(f"background: {BG};")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(PAD_SM, PAD_MD, PAD_MD, PAD_MD)
        lay.setSpacing(PAD_SM)

        # Header: dot + name + category badge
        hdr = QHBoxLayout()
        hdr.setSpacing(10)
        dot = label("●", self._task.colour, bold=True, size=16)
        hdr.addWidget(dot)
        hdr.addWidget(label(self._task.name, TEXT, bold=True, size=15))
        cat_badge = label(f"  {self._task.tag}  ", MUTED, size=10)
        cat_badge.setStyleSheet(
            f"color: {MUTED}; font-size: 10px; background: {BG3};"
            f" border: 1px solid {BORDER}; border-radius: 4px; padding: 1px 4px;"
        )
        hdr.addWidget(cat_badge)
        hdr.addStretch()
        lay.addLayout(hdr)
        lay.addWidget(h_line())

        # Metric cards (4 across)
        mc_row = QHBoxLayout()
        mc_row.setSpacing(PAD_SM)
        self._mc_today    = MetricCard("Today")
        self._mc_alltime  = MetricCard("Total (all time)")
        self._mc_sessions = MetricCard("Sessions in range")
        self._mc_avg      = MetricCard("Avg session")
        for mc in [self._mc_today, self._mc_alltime, self._mc_sessions, self._mc_avg]:
            mc_row.addWidget(mc)
        lay.addLayout(mc_row)

        # Session table header with "Add session" button
        sess_hdr = QHBoxLayout()
        sess_hdr.addWidget(label("Sessions", TEXT, bold=True, size=10))
        sess_hdr.addStretch()
        add_sess_btn = QPushButton("+ Add session")
        add_sess_btn.setFixedHeight(22)
        add_sess_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {MUTED};"
            f" border: 1px solid {BORDER}; border-radius: 4px;"
            f" font-size: 10px; padding: 0 8px; }}"
            f" QPushButton:hover {{ color: {TEXT}; background: {BG3};"
            f" border-color: {BORDER}; }}"
        )
        add_sess_btn.clicked.connect(
            lambda: self.add_session_requested.emit(self._task.start_line)
        )
        sess_hdr.addWidget(add_sess_btn)
        lay.addLayout(sess_hdr)

        # Session table
        self._session_table = SessionTable()
        self._session_table.edit_requested.connect(self.edit_session_requested)
        self._session_table.delete_requested.connect(self.delete_session_requested)
        session_panel = make_chart_panel("All sessions", self._session_table)
        lay.addWidget(session_panel)

        # Daily bar chart (full width)
        self._daily_chart = DailyBarChart()
        lay.addWidget(make_chart_panel("Daily activity", self._daily_chart))

        # Two-column: histogram | time-of-day
        row2 = QHBoxLayout()
        row2.setSpacing(PAD_SM)
        self._histogram = SessionHistogramChart()
        row2.addWidget(make_chart_panel("Session length distribution",
                                        self._histogram))
        self._tod_chart = TimeOfDayBarChart()
        row2.addWidget(make_chart_panel("Time of day", self._tod_chart))
        lay.addLayout(row2)

        # Pace chart (only shown when goal is set)
        self._pace_chart = CumulativePaceChart()
        self._pace_panel = make_chart_panel("Cumulative progress vs goal",
                                             self._pace_chart)
        lay.addWidget(self._pace_panel)

        lay.addStretch()
        scroll.setWidget(inner)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def update_task(self, task: Task) -> None:
        """Replace internal task reference after a reload."""
        self._task = task

    def refresh(self, start: date, end: date) -> None:
        task = self._task
        ts   = TaskSessionStats(task, start, end)

        # Today card
        today_sec = _today_seconds([task])
        self._mc_today.update_value(
            fmt_dur(today_sec, short=True),
            f"{today_sec / 3600:.1f}h so far",
        )

        # All-time card
        self._mc_alltime.update_value(
            fmt_dur(task.total_seconds, short=True),
            f"{task.total_hours:.1f}h all time",
        )
        # Range cards
        self._mc_sessions.update_value(
            str(ts.session_count),
            f"over {(end - start).days + 1} days",
        )
        if ts.avg_session_seconds > 0:
            self._mc_avg.update_value(fmt_dur(ts.avg_session_seconds, short=True))
        else:
            self._mc_avg.update_value("—")

        # Session table
        self._session_table.refresh(task, start, end)

        # Charts
        self._daily_chart.refresh_task(ts)
        self._histogram.refresh_task(ts)
        self._tod_chart.refresh_task(ts)
        self._pace_chart.refresh_task(ts)

        # Show/hide pace panel
        self._pace_panel.setVisible(task.goal_hours > 0)
