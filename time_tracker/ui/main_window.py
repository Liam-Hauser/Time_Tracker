"""
ui/main_window.py — Top-level application window.
Orchestrates all panels, handles data loading, timer ticks.
"""

from __future__ import annotations
import sys
import traceback
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QObject
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFileDialog, QScrollArea,
    QFrame, QSplitter, QGridLayout, QMessageBox, QCheckBox,
    QDoubleSpinBox, QFormLayout, QDialog, QDialogButtonBox,
    QSizePolicy,
)
from PyQt5.QtGui import QColor, QPalette

from ..core import (
    VaultParser, VaultWriter, ParseResult, RangeStats,
    WeeklyComparison, GoalTracker,
    date_range, this_week_range, last_week_range,
    this_month_range, last_month_range, last_n_days,
    fmt_dur,
)
from ..core.models import Task
from ..charts.panels import (
    PieChart, TaskBarChart, WeekdayChart,
    DailyLineChart, TotalDailyChart,
    HourHeatmap, WeeklyComparisonChart,
)
from .widgets import (
    StatCard, CollapsibleSection, RangeSlider,
    TaskRow, GoalBar, PresetBar, h_line, label, card_frame,
)
from .theme import (
    BG, BG2, BG3, BORDER, TEXT, MUTED, FAINT,
    ACCENT, SUCCESS, WARNING, DANGER, PAD_SM, PAD_MD, PAD_LG,
    WEEKDAY_NAMES,
)

DEFAULT_PATH = Path(r"C:/Users/liamh/Desktop/general_vault_0/Time Tracking/2026-Q1.md")


# ──────────────────────────────────────────────────────────
# Background reload worker
# Keeps worker alive by storing it on the thread object itself.
# Uses a plain string signal to avoid cross-thread object passing issues.
# ──────────────────────────────────────────────────────────
class ReloadWorker(QObject):
    """Parses the vault file on a background thread."""
    done  = pyqtSignal()   # emitted on success
    error = pyqtSignal(str)

    def __init__(self, path: Path, parser: VaultParser):
        super().__init__()
        self._path   = path
        self._parser = parser
        self.result: Optional[ParseResult] = None

    def run(self) -> None:
        try:
            self.result = self._parser.parse(self._path)
            self.done.emit()
        except Exception:
            self.error.emit(traceback.format_exc())


# ──────────────────────────────────────────────────────────
# Goal editor dialog
# ──────────────────────────────────────────────────────────
class GoalDialog(QDialog):
    def __init__(self, tasks: list[Task], goals: dict[str, float], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit goals")
        self.setMinimumWidth(360)
        self.setStyleSheet(f"background: {BG}; color: {TEXT};")

        layout = QVBoxLayout(self)
        layout.addWidget(label("Set target hours per task (0 = no goal):", MUTED))
        layout.addWidget(h_line())

        form = QFormLayout()
        self._spins: dict[str, QDoubleSpinBox] = {}
        for t in tasks:
            spin = QDoubleSpinBox()
            spin.setRange(0, 9999)
            spin.setSingleStep(0.5)
            spin.setValue(goals.get(t.name, 0.0))
            spin.setStyleSheet(
                f"background: {BG2}; color: {TEXT}; border: 1px solid {BORDER};"
                f" border-radius: 4px; padding: 2px 4px;"
            )
            self._spins[t.name] = spin
            form.addRow(label(t.name, TEXT, size=10), spin)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.setStyleSheet(f"color: {TEXT};")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_goals(self) -> dict[str, float]:
        return {name: spin.value() for name, spin in self._spins.items()}


# ──────────────────────────────────────────────────────────
# Main window
# ──────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Time Tracker")
        self.resize(1600, 960)

        self._parser  = VaultParser()
        self._writer  = VaultWriter()
        self._path    = DEFAULT_PATH
        self._result: Optional[ParseResult] = None
        self._goals:  dict[str, float]      = {}
        self._compact = False
        self._task_rows: dict[str, TaskRow] = {}

        self._date_low  = 0
        self._date_high = 0
        self._all_dates: list[date] = []

        # Keep worker + thread alive as instance attributes
        self._thread: Optional[QThread]       = None
        self._worker: Optional[ReloadWorker]  = None

        self._apply_dark_palette()
        self._build_ui()

        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._on_tick)
        self._tick_timer.start(1000)

        self._auto_reload = QTimer(self)
        self._auto_reload.timeout.connect(self._trigger_reload)
        self._auto_reload.start(30_000)

        # Delay initial load slightly so the window can paint first
        QTimer.singleShot(100, self._trigger_reload)

    # ── Dark palette ─────────────────────────────────────
    def _apply_dark_palette(self) -> None:
        pal = QPalette()
        pal.setColor(QPalette.Window,          QColor(BG))
        pal.setColor(QPalette.WindowText,      QColor(TEXT))
        pal.setColor(QPalette.Base,            QColor(BG2))
        pal.setColor(QPalette.AlternateBase,   QColor(BG3))
        pal.setColor(QPalette.Text,            QColor(TEXT))
        pal.setColor(QPalette.Button,          QColor(BG2))
        pal.setColor(QPalette.ButtonText,      QColor(TEXT))
        pal.setColor(QPalette.Highlight,       QColor(ACCENT))
        pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        self.setPalette(pal)
        QApplication.instance().setPalette(pal)

    # ─────────────────────────────────────────────────────
    # UI construction
    # ─────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        central = QWidget()
        central.setStyleSheet(f"background: {BG};")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._build_top_bar(root)
        self._build_body(root)

    def _build_top_bar(self, root: QVBoxLayout) -> None:
        bar = QFrame()
        bar.setFixedHeight(44)
        bar.setStyleSheet(
            f"QFrame {{ background: {BG2}; border-bottom: 1px solid {BORDER}; }}"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(PAD_LG, 0, PAD_LG, 0)
        layout.setSpacing(PAD_MD)

        layout.addWidget(label("⏱ Time Tracker", TEXT, bold=True, size=14))
        layout.addWidget(h_line())
        layout.addWidget(label("Vault file:", MUTED, size=10))

        self._path_edit = QLineEdit(str(self._path))
        self._path_edit.setStyleSheet(
            f"background: {BG3}; color: {TEXT}; border: 1px solid {BORDER};"
            f" border-radius: 4px; padding: 2px 8px; font-size: 10px;"
        )
        self._path_edit.setMinimumWidth(380)
        self._path_edit.returnPressed.connect(self._on_path_changed)
        layout.addWidget(self._path_edit, stretch=1)

        layout.addWidget(self._mk_btn("Browse…",   self._on_browse))
        layout.addWidget(self._mk_btn("⟳ Reload",  self._trigger_reload))

        self._compact_cb = QCheckBox("Compact")
        self._compact_cb.setStyleSheet(f"color: {MUTED}; font-size: 10px;")
        self._compact_cb.stateChanged.connect(self._on_compact_changed)
        layout.addWidget(self._compact_cb)

        layout.addWidget(self._mk_btn("Goals…", self._on_edit_goals))

        self._updated_lbl = label("Loading…", FAINT, size=9)
        layout.addWidget(self._updated_lbl)

        root.addWidget(bar)

    def _build_body(self, root: QVBoxLayout) -> None:
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet(
            f"QSplitter::handle {{ background: {BORDER}; width: 1px; }}"
        )

        # ── Left panel ────────────────────────────────────
        left = QWidget()
        left.setStyleSheet(f"background: {BG};")
        left.setMinimumWidth(420)
        left.setMaximumWidth(580)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(PAD_LG, PAD_LG, PAD_MD, PAD_LG)
        ll.setSpacing(PAD_MD)

        # Stat cards grid
        sg = QGridLayout()
        sg.setSpacing(8)
        self._stat_total    = StatCard("Total tracked time")
        self._stat_sessions = StatCard("Sessions")
        self._stat_avg_sess = StatCard("Avg session length")
        self._stat_best_day = StatCard("Best weekday")
        sg.addWidget(self._stat_total,    0, 0)
        sg.addWidget(self._stat_sessions, 0, 1)
        sg.addWidget(self._stat_avg_sess, 1, 0)
        sg.addWidget(self._stat_best_day, 1, 1)
        ll.addLayout(sg)

        # Task list
        ll.addWidget(label("Tasks", TEXT, bold=True, size=11))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {BG}; }}"
            f"QScrollBar:vertical {{ background: {BG2}; width: 6px; }}"
            f"QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 3px; }}"
        )
        self._task_container = QWidget()
        self._task_container.setStyleSheet(f"background: {BG};")
        self._task_layout = QVBoxLayout(self._task_container)
        self._task_layout.setContentsMargins(0, 0, 0, 0)
        self._task_layout.setSpacing(0)
        self._task_layout.addStretch()
        scroll.setWidget(self._task_container)
        ll.addWidget(scroll, stretch=1)

        # Goal bars
        self._goals_section = CollapsibleSection("Goal progress")
        self._goals_inner = QWidget()
        self._goals_inner_layout = QVBoxLayout(self._goals_inner)
        self._goals_inner_layout.setContentsMargins(0, 4, 0, 0)
        self._goals_section.add_widget(self._goals_inner)
        ll.addWidget(self._goals_section)

        splitter.addWidget(left)

        # ── Right panel (charts) ──────────────────────────
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {BG}; }}"
            f"QScrollBar:vertical {{ background: {BG2}; width: 6px; }}"
            f"QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 3px; }}"
        )
        right_inner = QWidget()
        right_inner.setStyleSheet(f"background: {BG};")
        cl = QVBoxLayout(right_inner)
        cl.setContentsMargins(PAD_MD, PAD_LG, PAD_LG, PAD_LG)
        cl.setSpacing(PAD_MD)

        # Date range card
        range_card = card_frame()
        rl = QVBoxLayout(range_card)
        rl.setContentsMargins(PAD_MD, PAD_MD, PAD_MD, PAD_MD)
        rl.setSpacing(6)
        self._preset_bar = PresetBar()
        self._preset_bar.preset_selected.connect(self._on_preset)
        rl.addWidget(self._preset_bar)
        self._range_slider = RangeSlider()
        self._range_slider.range_changed.connect(self._on_range_changed)
        rl.addWidget(self._range_slider)
        self._range_lbl = label("", MUTED, size=10)
        self._range_lbl.setAlignment(Qt.AlignCenter)
        rl.addWidget(self._range_lbl)
        cl.addWidget(range_card)

        # Chart row 1: pie + weekday side by side
        row1 = QWidget()
        row1_layout = QHBoxLayout(row1)
        row1_layout.setContentsMargins(0, 0, 0, 0)
        row1_layout.setSpacing(PAD_MD)

        self._pie_section = CollapsibleSection("Time per task — pie")
        self._pie_chart   = PieChart()
        self._pie_section.add_widget(self._pie_chart)
        row1_layout.addWidget(self._pie_section)

        self._wd_section = CollapsibleSection("Average time by weekday")
        self._wd_chart   = WeekdayChart()
        self._wd_section.add_widget(self._wd_chart)
        row1_layout.addWidget(self._wd_section)
        cl.addWidget(row1)

        # Remaining chart rows
        for section_title, chart_attr, chart_class in [
            ("Time per task — bar",    "_bar_chart", TaskBarChart),
            ("Daily time per task",    "_dl_chart",  DailyLineChart),
            ("Total daily time",       "_td_chart",  TotalDailyChart),
            ("Time-of-day heatmap",    "_hm_chart",  HourHeatmap),
            ("This week vs last week", "_wc_chart",  WeeklyComparisonChart),
        ]:
            section = CollapsibleSection(section_title)
            chart   = chart_class()
            section.add_widget(chart)
            cl.addWidget(section)
            setattr(self, chart_attr, chart)
            setattr(self, f"_{chart_attr[1:]}_section", section)

        cl.addStretch()
        right_scroll.setWidget(right_inner)
        splitter.addWidget(right_scroll)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, stretch=1)

    # ─────────────────────────────────────────────────────
    # Data loading  (worker kept alive as self._worker)
    # ─────────────────────────────────────────────────────
    def _trigger_reload(self) -> None:
        if self._thread and self._thread.isRunning():
            return

        self._thread = QThread(self)
        self._worker = ReloadWorker(self._path, self._parser)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.done.connect(self._on_worker_done)
        self._worker.error.connect(self._on_reload_error)
        self._worker.done.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)

        self._thread.start()

    def _on_worker_done(self) -> None:
        if self._worker and self._worker.result:
            self._on_reload_done(self._worker.result)

    def _on_reload_done(self, result: ParseResult) -> None:
        self._result = result

        for t in result.tasks:
            t.goal_hours = self._goals.get(t.name, 0.0)

        all_date_set: set[date] = set()
        for t in result.tasks:
            for s in t.sessions:
                all_date_set.add(s.date)
        self._all_dates = sorted(all_date_set)

        if self._all_dates:
            self._range_slider.set_count(len(self._all_dates))
            self._date_low  = 0
            self._date_high = len(self._all_dates) - 1

        ts = result.parsed_at.strftime("%H:%M:%S")
        self._updated_lbl.setText(f"Updated {ts}  |  {len(result.tasks)} tasks")

        self._rebuild_task_rows()
        self._refresh_all()

    def _on_reload_error(self, msg: str) -> None:
        self._updated_lbl.setText("Error — see details")
        QMessageBox.critical(self, "Failed to load vault file", msg)

    # ─────────────────────────────────────────────────────
    # Task rows
    # ─────────────────────────────────────────────────────
    def _rebuild_task_rows(self) -> None:
        while self._task_layout.count() > 1:
            item = self._task_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._result:
            return

        all_sec = [t.total_seconds for t in self._result.tasks]
        max_sec = max(all_sec) if all_sec else 1.0

        self._task_rows = {}
        for t in self._result.tasks:
            elapsed = (t.open_session.duration.total_seconds()
                       if t.open_session else 0)
            row = TaskRow(
                task_name   = t.name,
                colour      = t.colour,
                total_sec   = t.total_seconds,
                max_sec     = max_sec,
                n_sessions  = t.session_count,
                clocked_in  = t.is_clocked_in,
                elapsed_sec = elapsed,
                compact     = self._compact,
            )
            row.clock_in_requested.connect(self._on_clock_in)
            row.clock_out_requested.connect(self._on_clock_out)
            self._task_layout.insertWidget(self._task_layout.count() - 1, row)
            self._task_rows[t.name] = row

        self._rebuild_goal_bars()

    def _rebuild_goal_bars(self) -> None:
        while self._goals_inner_layout.count():
            item = self._goals_inner_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._result:
            return

        tasks_with_goals = [t for t in self._result.tasks if t.goal_hours > 0]
        if not tasks_with_goals:
            self._goals_inner_layout.addWidget(
                label("No goals set. Click 'Goals…' to add.", FAINT, size=9)
            )
            return

        stats = self._current_stats()
        if stats is None:
            return
        tracker = GoalTracker(self._result.tasks, stats)

        for t in tasks_with_goals:
            bar = GoalBar(t.name, t.colour)
            eta = tracker.eta_days(t.name)
            bar.update(t.goal_progress(), eta, t.goal_hours)
            self._goals_inner_layout.addWidget(bar)

    # ─────────────────────────────────────────────────────
    # Refresh charts + stat cards
    # ─────────────────────────────────────────────────────
    def _refresh_all(self) -> None:
        stats = self._current_stats()
        if stats is None:
            return

        self._update_stat_cards(stats)
        self._update_range_label()

        self._pie_chart.refresh(stats)
        self._bar_chart.refresh(stats)
        self._wd_chart.refresh(stats)
        self._dl_chart.refresh(stats)
        self._td_chart.refresh(stats)
        self._hm_chart.refresh(stats)

        if self._result:
            comp = WeeklyComparison(self._result.tasks)
            self._wc_chart.refresh_comparison(comp)

        self._rebuild_goal_bars()

    def _current_stats(self) -> Optional[RangeStats]:
        if not self._result or not self._all_dates:
            return None
        start = self._all_dates[self._date_low]
        end   = self._all_dates[self._date_high]
        return RangeStats(self._result.tasks, start, end)

    def _update_stat_cards(self, stats: RangeStats) -> None:
        self._stat_total.update_value(
            fmt_dur(stats.grand_total_seconds, short=True),
            f"{stats.grand_total_seconds / 3600:.1f}h total",
        )
        n_sess = sum(
            len(t.sessions_in_range(stats.start, stats.end))
            for t in stats.tasks
        )
        self._stat_sessions.update_value(str(n_sess),
                                         f"across {stats.n_days} days")

        all_closed = [
            s for t in stats.tasks
            for s in t.sessions_in_range(stats.start, stats.end)
            if not s.is_open
        ]
        if all_closed:
            avg = sum(s.duration_seconds for s in all_closed) / len(all_closed)
            self._stat_avg_sess.update_value(fmt_dur(avg, short=True))
        else:
            self._stat_avg_sess.update_value("—")

        wd = stats.most_consistent_weekday()
        if wd is not None:
            self._stat_best_day.update_value(WEEKDAY_NAMES[wd], colour=ACCENT)
        else:
            self._stat_best_day.update_value("—")

    def _update_range_label(self) -> None:
        if not self._all_dates:
            return
        s = self._all_dates[self._date_low]
        e = self._all_dates[self._date_high]
        self._range_lbl.setText(
            f"{s.strftime('%d %b %Y')}  –  {e.strftime('%d %b %Y')}"
            f"  ({(e - s).days + 1} days)"
        )

    # ─────────────────────────────────────────────────────
    # Clock in / out
    # ─────────────────────────────────────────────────────
    def _on_clock_in(self, task_name: str) -> None:
        if not self._result:
            return
        try:
            self._writer.clock_in(self._path, task_name, self._result)
        except Exception as e:
            QMessageBox.warning(self, "Clock-in failed", str(e))
            return
        self._trigger_reload()

    def _on_clock_out(self, task_name: str) -> None:
        if not self._result:
            return
        try:
            self._writer.clock_out(self._path, task_name, self._result)
        except Exception as e:
            QMessageBox.warning(self, "Clock-out failed", str(e))
            return
        self._trigger_reload()

    # ─────────────────────────────────────────────────────
    # Tick — update live elapsed labels every second
    # ─────────────────────────────────────────────────────
    def _on_tick(self) -> None:
        if not self._result:
            return
        for t in self._result.tasks:
            if t.is_clocked_in and t.name in self._task_rows:
                self._task_rows[t.name].update_elapsed(
                    t.open_session.duration.total_seconds()
                )

    # ─────────────────────────────────────────────────────
    # Date range controls
    # ─────────────────────────────────────────────────────
    def _on_range_changed(self, low: int, high: int) -> None:
        self._date_low  = low
        self._date_high = high
        self._refresh_all()

    def _on_preset(self, preset: str) -> None:
        if not self._all_dates:
            return

        presets = {
            "Last 7d":    last_n_days(7),
            "Last 30d":   last_n_days(30),
            "This month": this_month_range(),
            "Last month": last_month_range(),
            "This week":  this_week_range(),
            "Last week":  last_week_range(),
            "All":        (self._all_dates[0], self._all_dates[-1]),
        }
        rng = presets.get(preset)
        if not rng:
            return

        start, end = rng
        low  = min(range(len(self._all_dates)),
                   key=lambda i: abs((self._all_dates[i] - start).days))
        high = min(range(len(self._all_dates)),
                   key=lambda i: abs((self._all_dates[i] - end).days))
        high = max(low, high)
        self._range_slider.set_range(low, high)
        self._date_low, self._date_high = low, high
        self._refresh_all()

    # ─────────────────────────────────────────────────────
    # Path / file controls
    # ─────────────────────────────────────────────────────
    def _on_path_changed(self) -> None:
        self._path = Path(self._path_edit.text().strip())
        self._trigger_reload()

    def _on_browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select vault file", str(self._path),
            "Markdown files (*.md);;All files (*)"
        )
        if path:
            self._path = Path(path)
            self._path_edit.setText(path)
            self._trigger_reload()

    # ─────────────────────────────────────────────────────
    # Goals
    # ─────────────────────────────────────────────────────
    def _on_edit_goals(self) -> None:
        if not self._result:
            QMessageBox.information(self, "Goals",
                                    "Load a vault file first.")
            return
        dlg = GoalDialog(self._result.tasks, self._goals, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self._goals = dlg.get_goals()
            for t in self._result.tasks:
                t.goal_hours = self._goals.get(t.name, 0.0)
            self._rebuild_goal_bars()

    # ─────────────────────────────────────────────────────
    # Compact mode
    # ─────────────────────────────────────────────────────
    def _on_compact_changed(self, state: int) -> None:
        self._compact = bool(state)
        self._rebuild_task_rows()

    # ─────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────
    @staticmethod
    def _mk_btn(text: str, slot) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(28)
        btn.setStyleSheet(
            f"QPushButton {{ background: {BG3}; color: {MUTED};"
            f" border: 1px solid {BORDER}; border-radius: 4px;"
            f" font-size: 10px; padding: 0 10px; }}"
            f" QPushButton:hover {{ color: {TEXT}; }}"
        )
        btn.clicked.connect(slot)
        return btn