"""
ui/tab_widgets.py — Per-category and per-task tab content widgets.
"""
from __future__ import annotations
from datetime import date, datetime
from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QPushButton, QSplitter,
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
    MetricCard, InsightStrip, LogbookWidget, export_sessions_to_csv,
    ChartPanel, make_chart_panel, make_resizable_chart_panel, ResizableChartPanel,
    label, h_line,
)
from .theme import (
    BG, BG2, BG3, BORDER, BORDER2, TEXT, DIM, MUTED, FAINT,
    PAD, PAD_MD, PAD_LG, RADIUS, RADIUS_LG,
    ACCENT, SUCCESS, WARNING, DANGER,
    FONT_UI, FONT_MONO, SS,
)


from PyQt5.QtGui import QPainter, QColor, QFont
from PyQt5.QtCore import QTimer
from datetime import timedelta


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
# Goal info panel (used inside Task tab)
# ──────────────────────────────────────────────────────────

class _GoalProgressBar(QWidget):
    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self._pct = 0.0
        self._color = color
        self._text = ""
        self.setFixedHeight(22)

    def set(self, pct: float, text: str, color: str) -> None:
        self._pct = min(1.0, max(0.0, pct))
        self._text = text
        self._color = color
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(BG3))
        fill_w = int(self._pct * w)
        c = QColor(self._color)
        c.setAlphaF(0.65)
        p.fillRect(0, 0, fill_w, h, c)
        from PyQt5.QtGui import QPen
        p.setPen(QPen(QColor(BORDER), 1))
        p.drawRect(0, 0, w - 1, h - 1)
        p.setPen(QColor(TEXT))
        f = QFont(FONT_MONO, 8)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        from PyQt5.QtCore import Qt as _Qt
        p.drawText(0, 0, w, h, _Qt.AlignCenter, self._text)
        p.end()


class GoalInfoPanel(QWidget):
    """Compact goal summary shown in the task tab when a goal is active."""

    edit_requested   = pyqtSignal()
    remove_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"background: {BG2}; border: 1px solid {BORDER}; border-radius: {RADIUS_LG}px;"
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        # header row
        hdr = QHBoxLayout()
        hdr.setSpacing(8)
        ttl = label("Goal", MUTED, size=9)
        ttl.setStyleSheet(
            f"color: {MUTED}; font-size: 9px; letter-spacing: 1px;"
            f" text-transform: uppercase; background: transparent; border: none;"
        )
        hdr.addWidget(ttl)
        self._badge = label("—", MUTED, size=9)
        self._badge.setStyleSheet(
            f"color: {MUTED}; font-size: 8px; padding: 1px 6px;"
            f" border: 1px solid {MUTED}; border-radius: 3px;"
            f" background: transparent; letter-spacing: 0.8px;"
        )
        hdr.addWidget(self._badge)
        hdr.addStretch()

        edit_btn = QPushButton("Edit")
        edit_btn.setFixedHeight(22)
        edit_btn.setStyleSheet(SS.button("ghost"))
        edit_btn.clicked.connect(self.edit_requested)
        hdr.addWidget(edit_btn)

        rm_btn = QPushButton("Remove")
        rm_btn.setFixedHeight(22)
        rm_btn.setStyleSheet(SS.button("danger"))
        rm_btn.clicked.connect(self.remove_requested)
        hdr.addWidget(rm_btn)
        lay.addLayout(hdr)

        # progress bar
        self._bar_color = "#5B8DEF"
        self._bar = _GoalProgressBar(self._bar_color)
        lay.addWidget(self._bar)

        # stats row
        stats = QHBoxLayout()
        stats.setSpacing(16)

        self._lbl_done     = self._stat_col(stats, "DONE")
        self._lbl_target   = self._stat_col(stats, "TARGET")
        self._lbl_deadline = self._stat_col(stats, "DEADLINE")
        self._lbl_pace     = self._stat_col(stats, "PACE NEEDED")
        self._lbl_avg      = self._stat_col(stats, "AVG 7D")
        stats.addStretch()
        lay.addLayout(stats)

    def _stat_col(self, parent_lay: QHBoxLayout, title: str) -> QLabel:
        col = QWidget()
        col.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(col)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(1)
        t = label(title, MUTED, size=8)
        t.setStyleSheet(
            f"color: {MUTED}; font-size: 8px; letter-spacing: 0.8px;"
            f" background: transparent; border: none;"
        )
        v = label("—", TEXT, size=10)
        v.setStyleSheet(
            f"color: {TEXT}; font-size: 10px; font-family: {FONT_MONO};"
            f" background: transparent; border: none;"
        )
        cl.addWidget(t)
        cl.addWidget(v)
        parent_lay.addWidget(col)
        return v

    def refresh(self, task: Task) -> None:
        pct      = task.goal_progress()
        done_h   = task.total_hours
        goal_h   = task.goal_hours
        req_hpd  = task.required_daily_hours()
        dl_days  = task.deadline_days_left()

        # avg 7-day
        today = date.today()
        seven_ago = today - timedelta(days=6)
        total_7 = task.hours_in_range(seven_ago, today)
        active_days_7 = len({
            s.date for s in task.sessions
            if seven_ago <= s.date <= today and not s.is_open
        })
        avg7 = total_7 / active_days_7 if active_days_7 else 0.0

        # status badge
        if pct >= 1.0:
            status, s_color = "DONE", SUCCESS
        elif req_hpd is None:
            status, s_color = "IN PROGRESS", MUTED
        elif avg7 >= req_hpd:
            status, s_color = "ON TRACK", SUCCESS
        elif dl_days is not None and dl_days < 5:
            status, s_color = "CRITICAL", DANGER
        else:
            status, s_color = "BEHIND", WARNING

        self._badge.setText(status)
        self._badge.setStyleSheet(
            f"color: {s_color}; font-size: 8px; padding: 1px 6px;"
            f" border: 1px solid {s_color}; border-radius: 3px;"
            f" background: transparent; letter-spacing: 0.8px;"
        )

        self._bar.set(pct, f"{done_h:.1f}h / {goal_h:.0f}h  ·  {int(pct*100)}%", task.colour)

        self._lbl_done.setText(f"{done_h:.1f}h")
        self._lbl_target.setText(f"{goal_h:.0f}h")

        if task.goal_deadline:
            self._lbl_deadline.setText(
                task.goal_deadline.strftime("%d %b %Y")
                + (f"  ({dl_days}d)" if dl_days is not None and dl_days >= 0 else "  (passed)")
            )
        else:
            self._lbl_deadline.setText("no deadline")

        if req_hpd is not None:
            pace_color = SUCCESS if avg7 >= req_hpd else WARNING
            self._lbl_pace.setText(f"{req_hpd:.2f} h/day")
            self._lbl_pace.setStyleSheet(
                f"color: {pace_color}; font-size: 10px; font-family: {FONT_MONO};"
                f" background: transparent; border: none;"
            )
        elif pct >= 1.0:
            self._lbl_pace.setText("complete")
            self._lbl_pace.setStyleSheet(
                f"color: {SUCCESS}; font-size: 10px; font-family: {FONT_MONO};"
                f" background: transparent; border: none;"
            )
        else:
            self._lbl_pace.setText("—")
            self._lbl_pace.setStyleSheet(
                f"color: {MUTED}; font-size: 10px; font-family: {FONT_MONO};"
                f" background: transparent; border: none;"
            )

        self._lbl_avg.setText(f"{avg7:.2f} h/day")


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
        self._cat_tasks: list = []
        self._start: Optional[date] = None
        self._end:   Optional[date] = None

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(SS.scrollarea())
        inner = QWidget()
        inner.setStyleSheet(f"background: {BG};")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(PAD, PAD_MD, PAD_MD, PAD_MD)
        lay.setSpacing(PAD)

        # Category header row with export button
        cat_hdr = QHBoxLayout()
        cap = self.category_name[:1].upper() + self.category_name[1:]
        cat_hdr.addWidget(label(cap, TEXT, bold=True, size=14))
        cat_hdr.addStretch()
        export_btn = QPushButton("Export CSV")
        export_btn.setFixedHeight(24)
        export_btn.setStyleSheet(SS.button("ghost"))
        export_btn.clicked.connect(self._on_export)
        cat_hdr.addWidget(export_btn)
        lay.addLayout(cat_hdr)

        # Metric cards (4 across)
        mc_row = QHBoxLayout()
        mc_row.setSpacing(PAD)
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

        _hs_css = (
            f"QSplitter::handle:horizontal {{ background: {BORDER}; width: 4px; margin: 0 1px; }}"
            f"QSplitter::handle:horizontal:hover {{ background: {ACCENT}; }}"
        )

        self._stacked_chart = StackedAreaChart()
        lay.addWidget(make_resizable_chart_panel("Daily activity", self._stacked_chart))

        row2_panel = ResizableChartPanel("")
        row2_split = QSplitter(Qt.Horizontal)
        row2_split.setChildrenCollapsible(False)
        row2_split.setStyleSheet(_hs_css)
        self._wd_chart = WeekdayBarChart()
        row2_split.addWidget(make_chart_panel("Avg by weekday", self._wd_chart))
        self._wc_chart = WeeklyCompChart()
        row2_split.addWidget(make_chart_panel("This week vs last week", self._wc_chart))
        row2_panel.add_widget(row2_split)
        lay.addWidget(row2_panel)

        self._hm_chart = HourHeatmap()
        lay.addWidget(make_resizable_chart_panel("Hour-of-day heatmap", self._hm_chart))

        self._pie_chart = CategoryPieChart()
        lay.addWidget(make_resizable_chart_panel("Task breakdown", self._pie_chart))

        lay.addStretch()
        scroll.setWidget(inner)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _on_export(self) -> None:
        if not self._cat_tasks or self._start is None:
            return
        rows = []
        for t in self._cat_tasks:
            for s in t.sessions_in_range(self._start, self._end):
                rows.append((
                    s.start.strftime("%Y-%m-%d"),
                    s.start.strftime("%H:%M"),
                    s.end.strftime("%H:%M") if s.end else "",
                    round(s.duration_seconds / 3600, 4),
                    t.name,
                    t.tag,
                    s.note,
                ))
        rows.sort(key=lambda r: r[0], reverse=True)
        cap = self.category_name[:1].upper() + self.category_name[1:]
        export_sessions_to_csv(rows, f"{cap}_sessions.csv", self)

    def refresh(self, start: date, end: date,
                all_tasks: list[Task], goals: dict) -> None:
        cat_tasks = [t for t in all_tasks if t.tag == self.category_name]
        if not cat_tasks:
            return
        self._cat_tasks = cat_tasks
        self._start     = start
        self._end       = end
        stats = RangeStats(cat_tasks, start, end)

        import statistics as _stats
        from datetime import date as _date
        today = _date.today()

        today_sec = _today_seconds(cat_tasks)
        today_sess = sum(1 for t in cat_tasks for s in t.sessions if s.start.date() == today)
        self._mc_today.update_value(
            fmt_dur(today_sec, short=True),
            f"{today_sess} session{'s' if today_sess != 1 else ''} today",
        )

        self._mc_total.update_value(
            fmt_dur(stats.grand_total_seconds, short=True),
            f"{stats.grand_total_seconds / 3600:.1f}h total",
        )
        n_sess = sum(len(t.sessions_in_range(start, end)) for t in cat_tasks)
        spd = n_sess / max(1, stats.n_days)
        self._mc_sessions.update_value(str(n_sess), f"μ {spd:.1f}/day  ·  {stats.n_days}d")

        closed = [s for t in cat_tasks
                  for s in t.sessions_in_range(start, end)
                  if not s.is_open]
        if closed:
            durations = [s.duration_seconds for s in closed]
            avg = sum(durations) / len(durations)
            std = _stats.stdev(durations) if len(durations) > 1 else 0.0
            self._mc_avg.update_value(fmt_dur(avg, short=True), f"σ {fmt_dur(std, short=True)}")
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
    edit_session_requested   = pyqtSignal(int, object, object, str)  # id, start, end, note
    delete_session_requested = pyqtSignal(int, bool)             # id, is_open
    add_session_requested    = pyqtSignal(int)                   # task_id
    edit_goal_requested      = pyqtSignal(str)                   # task_name
    remove_goal_requested    = pyqtSignal(str)                   # task_name

    def __init__(self, task: Task, parent=None):
        super().__init__(parent)
        self.task_name = task.name
        self._task     = task
        self._build()

    def _build(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(SS.scrollarea())
        inner = QWidget()
        inner.setStyleSheet(f"background: {BG};")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(PAD, PAD_MD, PAD_MD, PAD_MD)
        lay.setSpacing(PAD)

        # Header: dot + name + category badge
        hdr = QHBoxLayout()
        hdr.setSpacing(10)
        dot = label("●", self._task.colour, bold=True, size=16)
        hdr.addWidget(dot)
        hdr.addWidget(label(self._task.name, TEXT, bold=True, size=15))
        _tag = self._task.tag
        _cap_tag = _tag[:1].upper() + _tag[1:] if _tag else _tag
        cat_badge = label(f"  {_cap_tag}  ", MUTED, size=10)
        cat_badge.setStyleSheet(
            f"color: {MUTED}; font-size: 10px; background: {BG3};"
            f" border: 1px solid {BORDER}; border-radius: {RADIUS}px; padding: 1px 4px;"
        )
        hdr.addWidget(cat_badge)
        hdr.addStretch()
        lay.addLayout(hdr)
        lay.addWidget(h_line())

        # Metric cards
        mc_row = QHBoxLayout()
        mc_row.setSpacing(PAD)
        self._mc_today    = MetricCard("Today")
        self._mc_alltime  = MetricCard("Total (all time)")
        self._mc_sessions = MetricCard("Sessions in range")
        self._mc_avg      = MetricCard("Avg session")
        for mc in [self._mc_today, self._mc_alltime, self._mc_sessions, self._mc_avg]:
            mc_row.addWidget(mc)
        lay.addLayout(mc_row)

        # Goal info panel (hidden until task has a goal)
        self._goal_panel = GoalInfoPanel()
        self._goal_panel.edit_requested.connect(
            lambda: self.edit_goal_requested.emit(self._task.name)
        )
        self._goal_panel.remove_requested.connect(
            lambda: self.remove_goal_requested.emit(self._task.name)
        )
        self._goal_panel.setVisible(False)
        lay.addWidget(self._goal_panel)

        _hs_css = (
            f"QSplitter::handle:horizontal {{ background: {BORDER}; width: 4px; margin: 0 1px; }}"
            f"QSplitter::handle:horizontal:hover {{ background: {ACCENT}; }}"
        )

        # ── Logbook ───────────────────────────────────────────────────────
        self._session_table = LogbookWidget()
        self._session_table.edit_requested.connect(self.edit_session_requested)
        self._session_table.delete_requested.connect(self.delete_session_requested)
        session_panel = ResizableChartPanel("Logbook", default_height=400)
        session_panel.add_widget(self._session_table)

        export_btn = QPushButton("Export CSV")
        export_btn.setFixedHeight(26)
        export_btn.setStyleSheet(SS.button("ghost"))
        export_btn.clicked.connect(self._on_export)
        session_panel.add_header_widget(export_btn)

        add_sess_btn = QPushButton("+ Add session")
        add_sess_btn.setFixedHeight(26)
        add_sess_btn.setStyleSheet(SS.button("ghost"))
        add_sess_btn.clicked.connect(
            lambda: self.add_session_requested.emit(self._task.start_line)
        )
        session_panel.add_header_widget(add_sess_btn)
        lay.addWidget(session_panel)

        # ── Daily activity ────────────────────────────────────────────────
        self._daily_chart = DailyBarChart()
        lay.addWidget(make_resizable_chart_panel("Daily activity", self._daily_chart))

        # ── Histogram + time-of-day (horizontal splitter) ─────────────────
        row2_panel = ResizableChartPanel("")
        row2_split = QSplitter(Qt.Horizontal)
        row2_split.setChildrenCollapsible(False)
        row2_split.setStyleSheet(_hs_css)
        self._histogram = SessionHistogramChart()
        row2_split.addWidget(make_chart_panel("Session length distribution", self._histogram))
        self._tod_chart = TimeOfDayBarChart()
        row2_split.addWidget(make_chart_panel("Time of day", self._tod_chart))
        row2_panel.add_widget(row2_split)
        lay.addWidget(row2_panel)

        # ── Cumulative pace ───────────────────────────────────────────────
        self._pace_chart = CumulativePaceChart()
        self._pace_panel = make_resizable_chart_panel(
            "Cumulative progress vs goal", self._pace_chart
        )
        lay.addWidget(self._pace_panel)

        lay.addStretch()
        scroll.setWidget(inner)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def update_task(self, task: Task) -> None:
        """Replace internal task reference after a reload."""
        self._task = task

    def _on_export(self) -> None:
        rows = list(self._session_table._export_rows)
        export_sessions_to_csv(rows, f"{self._task.name}_sessions.csv", self)

    def refresh(self, start: date, end: date) -> None:
        import statistics as _stats
        task = self._task
        ts   = TaskSessionStats(task, start, end)

        # Today card
        today_sec = _today_seconds([task])
        today_sess = sum(1 for s in task.sessions if s.start.date() == date.today())
        self._mc_today.update_value(
            fmt_dur(today_sec, short=True),
            f"{today_sess} session{'s' if today_sess != 1 else ''} today",
        )

        # All-time card
        n_days_active = len({s.date for s in task.sessions if not s.is_open})
        self._mc_alltime.update_value(
            fmt_dur(task.total_seconds, short=True),
            f"over {n_days_active} active day{'s' if n_days_active != 1 else ''}",
        )
        # Range cards
        range_days = (end - start).days + 1
        spd = ts.session_count / max(1, range_days)
        self._mc_sessions.update_value(
            str(ts.session_count),
            f"μ {spd:.1f}/day  ·  {range_days}d",
        )
        if ts.avg_session_seconds > 0 and ts.session_durations:
            std = _stats.stdev(ts.session_durations) if len(ts.session_durations) > 1 else 0.0
            self._mc_avg.update_value(
                fmt_dur(ts.avg_session_seconds, short=True),
                f"σ {fmt_dur(std, short=True)}",
            )
        else:
            self._mc_avg.update_value("—")

        # Session table
        self._session_table.refresh(task, start, end)

        # Charts
        self._daily_chart.refresh_task(ts)
        self._histogram.refresh_task(ts)
        self._tod_chart.refresh_task(ts)
        self._pace_chart.refresh_task(ts)

        # Show/hide goal elements
        has_goal = task.goal_hours > 0
        self._pace_panel.setVisible(has_goal)
        self._goal_panel.setVisible(has_goal)
        if has_goal:
            self._goal_panel.refresh(task)
