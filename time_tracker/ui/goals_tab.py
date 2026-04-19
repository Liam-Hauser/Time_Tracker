"""
ui/goals_tab.py — Dedicated Goals tab widget.
"""

from __future__ import annotations
from datetime import date, timedelta
from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPen, QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy, QGridLayout,
)

from ..core.models import Task, GoalSpec
from .theme import (
    BG, BG2, BG3, BORDER, BORDER2,
    TEXT, MUTED, FAINT, ACCENT, SUCCESS, WARNING, DANGER,
    PAD_SM, PAD_MD,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _lbl(text: str, color: str = TEXT, size: int = 10,
         bold: bool = False, mono: bool = False) -> QLabel:
    w = QLabel(text)
    w.setStyleSheet(
        f"color: {color}; font-size: {size}px; font-weight: {'600' if bold else '400'};"
        f" background: transparent; border: none;"
        + (f" font-family: Consolas, monospace;" if mono else "")
    )
    return w


# ── sparkline ────────────────────────────────────────────────────────────────

class _Sparkline(QWidget):
    def __init__(self, data: list[float], color: str, parent=None):
        super().__init__(parent)
        self._data = data
        self._color = color
        self.setFixedSize(90, 28)

    def set_data(self, data: list[float], color: str) -> None:
        self._data = data
        self._color = color
        self.update()

    def paintEvent(self, _event) -> None:
        if not self._data:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        n = len(self._data)
        maxv = max(self._data) if max(self._data) > 0 else 1
        bar_w = max(1, (w - (n - 1) * 2) // n)
        color = QColor(self._color)
        for i, v in enumerate(self._data):
            bar_h = max(2, int((v / maxv) * (h - 4)))
            x = i * (bar_w + 2)
            y = h - bar_h - 2
            color.setAlphaF(0.85)
            p.fillRect(x, y, bar_w, bar_h, color)
        p.end()


# ── progress bar ─────────────────────────────────────────────────────────────

class _ProgressBar(QWidget):
    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self._pct = 0.0
        self._color = color
        self._text = ""
        self.setFixedHeight(20)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set(self, pct: float, text: str, color: str) -> None:
        self._pct = min(1.0, max(0.0, pct))
        self._text = text
        self._color = color
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(BG3))
        fill_w = int(self._pct * w)
        color = QColor(self._color)
        color.setAlphaF(0.72)
        p.fillRect(0, 0, fill_w, h, color)
        p.setPen(QPen(QColor(BORDER), 1))
        p.drawRect(0, 0, w - 1, h - 1)
        p.setPen(QColor(TEXT))
        font = QFont("Consolas", 8)
        font.setWeight(QFont.DemiBold)
        p.setFont(font)
        p.drawText(0, 0, w, h, Qt.AlignCenter, self._text)
        p.end()


# ── KPI cell ─────────────────────────────────────────────────────────────────

class _KpiCell(QWidget):
    def __init__(self, label_text: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG2}; border-right: 1px solid {BORDER};")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(PAD_MD, PAD_SM, PAD_MD, PAD_SM)
        lay.setSpacing(2)
        self._val_lbl = QLabel("—")
        self._val_lbl.setStyleSheet(
            f"color: {TEXT}; font-size: 18px; font-weight: 700;"
            f" background: transparent; border: none;"
        )
        lay.addWidget(self._val_lbl)
        lbl = QLabel(label_text.upper())
        lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 8px; letter-spacing: 1px;"
            f" background: transparent; border: none;"
        )
        lay.addWidget(lbl)

    def set_value(self, text: str, color: str = TEXT) -> None:
        self._val_lbl.setText(text)
        self._val_lbl.setStyleSheet(
            f"color: {color}; font-size: 18px; font-weight: 700;"
            f" background: transparent; border: none;"
        )


# ── single goal card ──────────────────────────────────────────────────────────

class _GoalCard(QWidget):
    clicked        = pyqtSignal(str)
    edit_clicked   = pyqtSignal(str)
    cancel_clicked = pyqtSignal(str)
    archive_clicked = pyqtSignal(str)

    def __init__(self, task: Task, parent=None):
        super().__init__(parent)
        self._task_name = task.name
        self.setObjectName("GoalCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(8)

        # ── top row: dot · name · status badge ──────────────
        top = QHBoxLayout()
        top.setSpacing(8)
        self._dot = QLabel("●")
        self._dot.setStyleSheet(
            f"color: {task.colour}; font-size: 11px; background: transparent; border: none;"
        )
        self._dot.setFixedWidth(14)
        top.addWidget(self._dot)
        self._name_lbl = _lbl(task.name, TEXT, 12, bold=True)
        top.addWidget(self._name_lbl, stretch=1)
        self._badge = QLabel("—")
        self._badge.setAlignment(Qt.AlignCenter)
        self._badge.setFixedHeight(18)
        self._badge.setStyleSheet(
            f"font-size: 8px; font-family: Consolas, monospace; letter-spacing: 1px;"
            f" padding: 0 6px; border-radius: 3px; border: 1px solid {MUTED}; color: {MUTED};"
            f" background: transparent;"
        )
        top.addWidget(self._badge)
        outer.addLayout(top)

        # ── progress bar ─────────────────────────────────────
        self._bar = _ProgressBar(task.colour)
        outer.addWidget(self._bar)

        # ── stats row ────────────────────────────────────────
        stats = QHBoxLayout()
        stats.setSpacing(0)

        # left block: deadline OR completion date
        dl_col = QVBoxLayout()
        dl_col.setSpacing(1)
        self._dl_label = _lbl("DEADLINE", MUTED, 8, mono=True)
        self._dl_date  = _lbl("—", TEXT, 10, mono=True)
        self._dl_days  = _lbl("", MUTED, 9, mono=True)
        dl_col.addWidget(self._dl_label)
        dl_col.addWidget(self._dl_date)
        dl_col.addWidget(self._dl_days)
        stats.addLayout(dl_col, stretch=1)

        v1 = QFrame(); v1.setFrameShape(QFrame.VLine)
        v1.setStyleSheet(f"color: {BORDER};")
        stats.addWidget(v1)
        stats.addSpacing(PAD_SM)

        # pace block
        pace_col = QVBoxLayout()
        pace_col.setSpacing(1)
        self._pace_lbl = _lbl("PACE NEEDED", MUTED, 8, mono=True)
        self._pace_val = _lbl("—", TEXT, 10, mono=True)
        self._pace_avg = _lbl("", MUTED, 9, mono=True)
        pace_col.addWidget(self._pace_lbl)
        pace_col.addWidget(self._pace_val)
        pace_col.addWidget(self._pace_avg)
        stats.addLayout(pace_col, stretch=1)

        v2 = QFrame(); v2.setFrameShape(QFrame.VLine)
        v2.setStyleSheet(f"color: {BORDER};")
        stats.addWidget(v2)
        stats.addSpacing(PAD_SM)

        # sparkline
        spark_col = QVBoxLayout()
        spark_col.setSpacing(1)
        spark_col.addWidget(_lbl("7D TREND", MUTED, 8, mono=True))
        self._sparkline = _Sparkline([], task.colour)
        spark_col.addWidget(self._sparkline)
        spark_col.addStretch()
        stats.addLayout(spark_col)

        outer.addLayout(stats)

        # ── action buttons ───────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        btn_row.addStretch()

        self._archive_btn = QPushButton("Archive")
        self._archive_btn.setFixedHeight(24)
        self._archive_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {MUTED};"
            f" border: 1px solid {BORDER}; border-radius: 4px;"
            f" font-size: 9px; padding: 0 10px; }}"
            f" QPushButton:hover {{ color: {TEXT}; border-color: {BORDER2}; }}"
        )
        self._archive_btn.clicked.connect(
            lambda: self.archive_clicked.emit(self._task_name)
        )
        btn_row.addWidget(self._archive_btn)

        edit_btn = QPushButton("Edit")
        edit_btn.setFixedHeight(24)
        edit_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {MUTED};"
            f" border: 1px solid {BORDER}; border-radius: 4px;"
            f" font-size: 9px; padding: 0 10px; }}"
            f" QPushButton:hover {{ color: {TEXT}; border-color: {BORDER2}; }}"
        )
        edit_btn.clicked.connect(lambda: self.edit_clicked.emit(self._task_name))
        btn_row.addWidget(edit_btn)

        cancel_btn = QPushButton("Remove")
        cancel_btn.setFixedHeight(24)
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {DANGER};"
            f" border: 1px solid {DANGER}; border-radius: 4px;"
            f" font-size: 9px; padding: 0 10px; }}"
            f" QPushButton:hover {{ background: {DANGER}; color: #fff; }}"
        )
        cancel_btn.clicked.connect(lambda: self.cancel_clicked.emit(self._task_name))
        btn_row.addWidget(cancel_btn)

        outer.addLayout(btn_row)

    def mousePressEvent(self, event) -> None:
        child = self.childAt(event.pos())
        if child is None or not isinstance(child, QPushButton):
            self.clicked.emit(self._task_name)

    def refresh(self, task: Task, daily_avg: float, gs: GoalSpec) -> None:
        pct     = task.goal_progress()
        done_h  = task.total_hours
        goal_h  = task.goal_hours
        req_hpd = task.required_daily_hours()
        dl_days = task.deadline_days_left()
        is_archived = gs.archived or (
            gs.completed_on is not None
            and (date.today() - gs.completed_on).days >= 3
        )

        # card dimming for archived
        self.setStyleSheet(
            f"QWidget#GoalCard {{ background: {BG2 if not is_archived else BG3};"
            f" border: 1px solid {BORDER}; border-radius: 6px; opacity: {'1' if not is_archived else '0.6'}; }}"
        )

        # status badge
        if pct >= 1.0:
            status, s_color = "DONE", SUCCESS
        elif gs.archived:
            status, s_color = "ARCHIVED", MUTED
        elif req_hpd is None:
            on_track = daily_avg > 0
            status, s_color = ("ON TRACK", SUCCESS) if on_track else ("IN PROGRESS", MUTED)
        else:
            on_track = daily_avg >= req_hpd
            if on_track:
                status, s_color = "ON TRACK", SUCCESS
            elif dl_days is not None and dl_days < 5:
                status, s_color = "CRITICAL", DANGER
            else:
                status, s_color = "BEHIND", WARNING

        self._badge.setText(status)
        self._badge.setStyleSheet(
            f"font-size: 8px; font-family: Consolas, monospace; letter-spacing: 1px;"
            f" padding: 0 6px; border-radius: 3px; border: 1px solid {s_color};"
            f" color: {s_color}; background: transparent;"
        )

        self._dot.setStyleSheet(
            f"color: {task.colour}; font-size: 11px; background: transparent; border: none;"
        )

        bar_text = f"{done_h:.1f}h / {goal_h:.0f}h · {int(pct * 100)}%"
        self._bar.set(pct, bar_text, task.colour)

        # left block: show completion date if done, else deadline
        if gs.completed_on is not None:
            self._dl_label.setText("COMPLETED")
            self._dl_date.setText(gs.completed_on.strftime("%Y-%m-%d"))
            days_since = (date.today() - gs.completed_on).days
            self._dl_days.setText(f"{days_since}d ago")
            self._dl_days.setStyleSheet(
                f"color: {SUCCESS}; font-size: 9px; font-family: Consolas, monospace;"
                f" background: transparent; border: none;"
            )
        elif task.goal_deadline:
            self._dl_label.setText("DEADLINE")
            self._dl_date.setText(task.goal_deadline.strftime("%Y-%m-%d"))
            if dl_days is not None:
                dl_color = DANGER if dl_days < 5 else MUTED
                self._dl_days.setText(f"{dl_days}d left")
                self._dl_days.setStyleSheet(
                    f"color: {dl_color}; font-size: 9px; font-family: Consolas, monospace;"
                    f" background: transparent; border: none;"
                )
            else:
                self._dl_days.setText("deadline passed")
                self._dl_days.setStyleSheet(
                    f"color: {DANGER}; font-size: 9px; font-family: Consolas, monospace;"
                    f" background: transparent; border: none;"
                )
        else:
            self._dl_label.setText("DEADLINE")
            self._dl_date.setText("no deadline")
            self._dl_days.setText("")

        # pace block
        if req_hpd is not None:
            pace_color = SUCCESS if daily_avg >= req_hpd else WARNING
            self._pace_val.setText(f"{req_hpd:.1f} h/day")
            self._pace_val.setStyleSheet(
                f"color: {pace_color}; font-size: 10px; font-family: Consolas, monospace;"
                f" background: transparent; border: none;"
            )
            self._pace_avg.setText(f"avg7 {daily_avg:.1f}h")
        elif pct >= 1.0:
            self._pace_val.setText("complete")
            self._pace_val.setStyleSheet(
                f"color: {SUCCESS}; font-size: 10px; font-family: Consolas, monospace;"
                f" background: transparent; border: none;"
            )
            self._pace_avg.setText(f"avg7 {daily_avg:.1f}h")
        elif dl_days is not None and dl_days <= 0:
            self._pace_val.setText("overdue")
            self._pace_val.setStyleSheet(
                f"color: {DANGER}; font-size: 10px; font-family: Consolas, monospace;"
                f" background: transparent; border: none;"
            )
            self._pace_avg.setText(f"avg7 {daily_avg:.1f}h")
        else:
            self._pace_val.setText("no deadline")
            self._pace_val.setStyleSheet(
                f"color: {MUTED}; font-size: 10px; font-family: Consolas, monospace;"
                f" background: transparent; border: none;"
            )
            self._pace_avg.setText(f"avg7 {daily_avg:.1f}h")

        # archive button label
        self._archive_btn.setText("Unarchive" if gs.archived else "Archive")

        # sparkline
        today = date.today()
        spark_data = [
            task.seconds_in_range(today - timedelta(days=i), today - timedelta(days=i)) / 3600
            for i in range(6, -1, -1)
        ]
        self._sparkline.set_data(spark_data, task.colour)


# ── Goals tab ─────────────────────────────────────────────────────────────────

class GoalsTab(QWidget):
    open_goal_dialog  = pyqtSignal()
    task_clicked      = pyqtSignal(str)
    edit_goal         = pyqtSignal(str)
    cancel_goal       = pyqtSignal(str)
    archive_goal      = pyqtSignal(str)  # task name — toggle archive

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG};")
        self._show_archived = False
        # full data stored each refresh so toggle can re-filter without MainWindow
        self._all_tasks: list[Task] = []
        self._all_goals: dict[str, GoalSpec] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── header bar ───────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(48)
        header.setStyleSheet(f"background: {BG2}; border-bottom: 1px solid {BORDER};")
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(PAD_MD, 0, PAD_MD, 0)
        h_lay.setSpacing(PAD_MD)

        title = QLabel("Goals")
        title.setStyleSheet(
            f"color: {TEXT}; font-size: 15px; font-weight: 700;"
            f" background: transparent; border: none;"
        )
        h_lay.addWidget(title)

        self._summary_lbl = QLabel("")
        self._summary_lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 9px; font-family: Consolas, monospace;"
            f" background: transparent; border: none; letter-spacing: 0.5px;"
        )
        h_lay.addWidget(self._summary_lbl)
        h_lay.addStretch()

        self._archived_btn = QPushButton("Archived")
        self._archived_btn.setFixedHeight(28)
        self._archived_btn.setCheckable(True)
        self._archived_btn.setChecked(False)
        self._archived_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {MUTED};"
            f" border: 1px solid {BORDER}; border-radius: 4px;"
            f" font-size: 10px; padding: 0 12px; }}"
            f" QPushButton:checked {{ background: {ACCENT}; color: #fff;"
            f" border-color: {ACCENT}; }}"
            f" QPushButton:hover {{ border-color: {BORDER2}; color: {TEXT}; }}"
        )
        self._archived_btn.toggled.connect(self._on_toggle_archived)
        h_lay.addWidget(self._archived_btn)

        new_btn = QPushButton("+ New Goal")
        new_btn.setFixedHeight(28)
        new_btn.setStyleSheet(
            f"QPushButton {{ background: {ACCENT}; color: #fff; border: none;"
            f" border-radius: 4px; font-size: 10px; padding: 0 14px; font-weight: 600; }}"
            f" QPushButton:hover {{ background: {BORDER2}; }}"
        )
        new_btn.clicked.connect(self.open_goal_dialog)
        h_lay.addWidget(new_btn)
        root.addWidget(header)

        # ── KPI strip ────────────────────────────────────────
        kpi_bar = QWidget()
        kpi_bar.setFixedHeight(70)
        kpi_bar.setStyleSheet(f"background: {BG2}; border-bottom: 1px solid {BORDER};")
        kpi_lay = QHBoxLayout(kpi_bar)
        kpi_lay.setContentsMargins(0, 0, 0, 0)
        kpi_lay.setSpacing(0)

        self._kpi_total    = _KpiCell("Total Goals")
        self._kpi_done     = _KpiCell("Completed")
        self._kpi_on_track = _KpiCell("On Track")
        self._kpi_behind   = _KpiCell("Behind")
        self._kpi_nearest  = _KpiCell("Nearest Deadline")
        self._kpi_nearest.setStyleSheet(f"background: {BG2};")

        for cell in (self._kpi_total, self._kpi_done, self._kpi_on_track,
                     self._kpi_behind, self._kpi_nearest):
            kpi_lay.addWidget(cell, stretch=1)
        root.addWidget(kpi_bar)

        # ── scrollable card area ──────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {BG}; }}"
            f"QScrollBar:vertical {{ background: {BG2}; width: 4px; }}"
            f"QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 2px; }}"
        )
        self._card_container = QWidget()
        self._card_container.setStyleSheet(f"background: {BG};")
        self._card_layout = QGridLayout(self._card_container)
        self._card_layout.setContentsMargins(PAD_MD, PAD_MD, PAD_MD, PAD_MD)
        self._card_layout.setSpacing(10)
        self._card_layout.setColumnStretch(0, 1)
        self._card_layout.setColumnStretch(1, 1)
        scroll.setWidget(self._card_container)
        root.addWidget(scroll, stretch=1)

        self._cards: dict[str, _GoalCard] = {}
        self._empty_lbl: Optional[QLabel] = None

    # ─────────────────────────────────────────────────────────

    def _on_toggle_archived(self, checked: bool) -> None:
        self._show_archived = checked
        self._render(self._all_tasks, self._all_goals)

    def refresh(self, tasks: list[Task], goals: dict[str, GoalSpec]) -> None:
        """Store data and render. tasks should include ALL tasks with goals."""
        self._all_tasks = tasks
        self._all_goals = goals
        self._render(tasks, goals)

    def _render(self, tasks: list[Task], goals: dict[str, GoalSpec]) -> None:
        today = date.today()

        def _is_auto_archived(gs: GoalSpec) -> bool:
            return (
                gs.completed_on is not None
                and (today - gs.completed_on).days >= 3
            )

        def _is_archived(gs: GoalSpec) -> bool:
            return gs.archived or _is_auto_archived(gs)

        tasks_with_goals = [t for t in tasks if t.goal_hours > 0]

        # Split active vs archived for KPIs (always counts active only)
        active_tasks = [
            t for t in tasks_with_goals
            if not _is_archived(goals.get(t.name, GoalSpec()))
        ]
        archived_tasks = [
            t for t in tasks_with_goals
            if _is_archived(goals.get(t.name, GoalSpec()))
        ]
        done_tasks = [t for t in tasks_with_goals if t.goal_progress() >= 1.0]

        # KPIs — three mutually exclusive buckets among active goals
        # completed: pct >= 1.0
        # on track:  pct < 1.0 and on pace (or no deadline)
        # behind:    pct < 1.0 and behind pace
        done_active    = [t for t in active_tasks if t.goal_progress() >= 1.0]
        incomplete     = [t for t in active_tasks if t.goal_progress() < 1.0]
        on_track_tasks = [t for t in incomplete if _is_on_track(t)]
        behind_tasks   = [t for t in incomplete if not _is_on_track(t)]

        dl_values = [
            d for t in incomplete
            if (d := t.deadline_days_left()) is not None and d >= 0
        ]
        nearest_dl = min(dl_values) if dl_values else None

        n = len(active_tasks)
        if n or archived_tasks:
            self._kpi_total.set_value(str(n))
            self._kpi_done.set_value(
                str(len(done_active)),
                color=SUCCESS if done_active else TEXT,
            )
            self._kpi_on_track.set_value(
                str(len(on_track_tasks)),
                color=SUCCESS if on_track_tasks and not behind_tasks else TEXT,
            )
            self._kpi_behind.set_value(
                str(len(behind_tasks)),
                color=DANGER if behind_tasks else TEXT,
            )
            self._kpi_nearest.set_value(
                f"{nearest_dl}d" if nearest_dl is not None else "none",
                color=DANGER if (nearest_dl is not None and nearest_dl < 5) else TEXT,
            )
            self._summary_lbl.setText(
                f"· {len(done_active)} completed"
                f"  · {len(on_track_tasks)} on track"
                f"  · {len(behind_tasks)} behind"
                + (f"  · {len(archived_tasks)} archived" if archived_tasks else "")
            )
        else:
            for kpi in (self._kpi_total, self._kpi_done, self._kpi_on_track,
                        self._kpi_behind, self._kpi_nearest):
                kpi.set_value("—")
            self._summary_lbl.setText("· no goals set")

        # Choose which tasks to show
        display_tasks = tasks_with_goals if self._show_archived else active_tasks

        # Remove cards no longer shown
        shown_names = {t.name for t in display_tasks}
        for name in list(self._cards.keys()):
            if name not in shown_names:
                card = self._cards.pop(name)
                card.setParent(None)
                card.deleteLater()

        if self._empty_lbl:
            self._empty_lbl.setParent(None)
            self._empty_lbl.deleteLater()
            self._empty_lbl = None

        if not display_tasks:
            msg = (
                "No archived goals."
                if self._show_archived and not tasks_with_goals
                else "No goals set yet.\n\nClick  + New Goal  to add one."
                if not tasks_with_goals
                else "No active goals.\n\nAll goals are archived."
            )
            self._empty_lbl = QLabel(msg)
            self._empty_lbl.setAlignment(Qt.AlignCenter)
            self._empty_lbl.setStyleSheet(
                f"color: {MUTED}; font-size: 11px; background: transparent;"
            )
            self._card_layout.addWidget(self._empty_lbl, 0, 0, 1, 2)
            return

        # Build / refresh cards
        for task in display_tasks:
            gs = goals.get(task.name, GoalSpec())
            daily_avg = _avg7_hours(task)
            if task.name not in self._cards:
                card = _GoalCard(task)
                card.clicked.connect(self.task_clicked)
                card.edit_clicked.connect(self.edit_goal)
                card.cancel_clicked.connect(self.cancel_goal)
                card.archive_clicked.connect(self.archive_goal)
                self._cards[task.name] = card
            self._cards[task.name].refresh(task, daily_avg, gs)

        # Re-lay in two columns, top-aligned
        while self._card_layout.count():
            self._card_layout.takeAt(0)
        for i, task in enumerate(display_tasks):
            row, col = divmod(i, 2)
            self._card_layout.addWidget(
                self._cards[task.name], row, col,
                Qt.AlignTop,
            )
        # Push all rows up
        self._card_layout.setRowStretch((len(display_tasks) + 1) // 2, 1)


# ── helpers ───────────────────────────────────────────────────────────────────

def _is_on_track(task: Task) -> bool:
    req = task.required_daily_hours()
    if req is None:
        return True
    return _avg7_hours(task) >= req


def _avg7_hours(task: Task) -> float:
    today = date.today()
    seven_ago = today - timedelta(days=6)
    total_h = task.hours_in_range(seven_ago, today)
    active_days = len({
        s.date for s in task.sessions
        if seven_ago <= s.date <= today and not s.is_open
    })
    return total_h / active_days if active_days else 0.0
