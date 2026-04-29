"""
ui/main_window.py — Top-level application window.
"""

from __future__ import annotations
import traceback
from datetime import date, datetime
from typing import Optional

from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QObject, QDate
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea,
    QFrame, QSplitter, QMessageBox, QStackedWidget, QComboBox,
    QDialog, QVBoxLayout as _QVL, QDialogButtonBox, QTextEdit,
    QMenu,
)
from PyQt5.QtGui import QColor, QPalette, QIcon, QPainter, QPainterPath
from pathlib import Path

from ..core import (
    DBStore, ParseResult, RangeStats,
    WeeklyComparison, GoalTracker, InsightEngine, Insight, streak_days,
    GoalSpec,
    date_range, this_week_range, last_week_range,
    this_month_range, last_month_range, last_n_days,
    fmt_dur,
)
from ..core.models import Task, category_swatch as _category_swatch
from ..charts.panels import (
    StackedAreaChart, WeekdayBarChart, HourHeatmap, WeeklyCompChart,
    CategoryPieChart,
)
from .widgets import (
    MetricCard, InsightStrip, ChartPanel, PanelWidget,
    RangeSlider, TaskRow, PresetBar,
    h_line, v_line, label, section_label, card_frame,
    make_chart_panel, make_resizable_chart_panel, ResizableChartPanel,
    EditSessionDialog, AddSessionDialog,
)
from .dialogs import (
    AddGoalDialog, EditGoalDialog,
    NewTaskDialog, RenameTaskDialog, MoveTaskDialog,
    NewCategoryDialog, RenameCategoryDialog, RecolorCategoryDialog,
)
from .tab_widgets import CategoryTabWidget, TaskTabWidget
from .calendar_widget import CalendarWidget
from .goals_tab import GoalsTab
from .theme import (
    BG, BG2, BG3, BG4, BORDER, BORDER2,
    TEXT, DIM, MUTED, FAINT, ACCENT, SUCCESS, WARNING, DANGER,
    FONT_UI, FONT_MONO, RADIUS, RADIUS_LG, PAD, PAD_MD, PAD_LG,
    SS,
)


# ──────────────────────────────────────────────────────────
# Background reload worker
# ──────────────────────────────────────────────────────────

class ReloadWorker(QObject):
    done  = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, store: DBStore):
        super().__init__()
        self._store = store
        self.result:     Optional[ParseResult]       = None
        self.goals:      Optional[dict]              = None
        self.categories: list[tuple[str, str]]       = []

    def run(self) -> None:
        try:
            self.result     = self._store.load()
            self.goals      = self._store.load_goals()
            self.categories = self._store.load_categories()
            self.done.emit()
        except Exception:
            self.error.emit(traceback.format_exc())


# ──────────────────────────────────────────────────────────
# Update checker
# ──────────────────────────────────────────────────────────

class UpdateChecker(QObject):
    update_available = pyqtSignal(str)  # emits latest version string

    def run(self) -> None:
        try:
            import urllib.request, json
            from ..version import GITHUB_REPO, VERSION
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(url, headers={"User-Agent": "TimeTracker"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            latest = data.get("tag_name", "").lstrip("v")
            if latest and latest != VERSION:
                self.update_available.emit(latest)
        except Exception:
            pass  # silently ignore — no internet, rate limit, etc.


# ──────────────────────────────────────────────────────────



def _goal_is_archived(gs, today) -> bool:
    """A goal is archived if manually archived OR completed 3+ days ago."""
    if gs.archived:
        return True
    if gs.completed_on is not None and (today - gs.completed_on).days >= 3:
        return True
    return False


def _swatch_for_tag(colour_tag: str) -> str:
    """Return the representative hex for a colour_tag (named or numeric)."""
    return _category_swatch(colour_tag)


# Main window
# ──────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Time Tracker")
        self.resize(1600, 960)
        _icon_path = Path(__file__).parent.parent / "icon.png"
        if _icon_path.exists():
            from PyQt5.QtGui import QPixmap
            from PyQt5.QtCore import QRectF as _QRectF
            _px = QPixmap(str(_icon_path))
            if not _px.isNull():
                _w, _h = _px.width(), _px.height()
                _r = min(_w, _h) * 0.18
                _out = QPixmap(_w, _h)
                _out.fill(Qt.transparent)
                _p = QPainter(_out)
                _p.setRenderHint(QPainter.Antialiasing)
                _pp = QPainterPath()
                _pp.addRoundedRect(_QRectF(0, 0, _w, _h), _r, _r)
                _p.setClipPath(_pp)
                _p.drawPixmap(0, 0, _px)
                _p.end()
                self.setWindowIcon(QIcon(_out))

        self._store      = DBStore()
        self._result:      Optional[ParseResult]          = None
        self._goals:       dict[str, GoalSpec]            = {}
        self._categories:  list[tuple[str, str]]          = []
        self._category_views: dict[str, CategoryTabWidget] = {}
        self._task_views:     dict[str, TaskTabWidget]     = {}
        self._cal_tab:       Optional[CalendarWidget]     = None
        self._goals_tab:     Optional[GoalsTab]           = None
        self._current_view:  str                          = "overview"
        self._clocked_task:  Optional[str]               = None
        self._collapsed_cats: set[str]                   = set()
        self._sidebar_cat_items: dict[str, list]         = {}  # cat → [task widgets]

        self._date_low  = 0
        self._date_high = 0
        self._all_dates: list[date] = []
        self._show_archived = False

        from ..core.user_presets import load_presets
        self._custom_presets = load_presets()

        self._thread: Optional[QThread]      = None
        self._worker: Optional[ReloadWorker] = None
        self._reload_pending: bool           = False

        self._apply_palette()
        self._build_ui()

        # 1-second tick for live elapsed time
        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._on_tick)
        self._tick_timer.start(1000)

        # Debounce chart redraws (80 ms after last slider event)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(80)
        self._refresh_timer.timeout.connect(self._refresh_all)

        # Auto-reload every 30 s
        self._auto_reload = QTimer(self)
        self._auto_reload.timeout.connect(self._trigger_reload)
        self._auto_reload.start(30_000)

        QTimer.singleShot(100, self._trigger_reload)

    # ── Palette ──────────────────────────────────────────

    def _apply_palette(self) -> None:
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

    # ── UI construction ──────────────────────────────────

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
        bar.setFixedHeight(40)
        bar.setStyleSheet(
            f"QFrame {{ background: {BG2}; border-bottom: 1px solid {BORDER}; }}"
        )
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(PAD_MD, 0, PAD_MD, 0)
        lay.setSpacing(PAD)

        logo = QLabel("Time Tracker")
        logo.setStyleSheet(
            f"color: {TEXT}; font-size: 12px; font-weight: 600;"
            f" font-family: {FONT_UI}; letter-spacing: 0.3px;"
            f" background: transparent; border: none;"
        )
        lay.addWidget(logo)
        lay.addStretch()

        self._update_btn = QPushButton("Update available")
        self._update_btn.setVisible(False)
        self._update_btn.setStyleSheet(SS.button("primary"))
        self._update_btn.clicked.connect(self._open_releases)
        lay.addWidget(self._update_btn)

        for txt, slot in [("Reload", self._trigger_reload),
                          ("Light",  self._on_toggle_theme)]:
            btn = self._mk_btn(txt, slot)
            if txt == "Light":
                self._theme_btn = btn
            lay.addWidget(btn)

        self._updated_lbl = label("Loading…", FAINT, size=9, mono=True)
        lay.addWidget(self._updated_lbl)

        root.addWidget(bar)

        self._start_update_check()

    def _build_body(self, root: QVBoxLayout) -> None:
        _h_css = (
            f"QSplitter::handle:horizontal {{"
            f"  background: {BORDER}; width: 4px; }}"
            f"QSplitter::handle:horizontal:hover {{"
            f"  background: {ACCENT}; }}"
        )
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(4)
        splitter.setStyleSheet(_h_css)

        # ── Left panel ────────────────────────────────────
        left = QWidget()
        left.setMinimumWidth(260)
        left.setMaximumWidth(460)
        left.setStyleSheet(f"background: {BG2};")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)

        self._build_session_bar(ll)
        self._build_nav_section(ll)
        self._build_date_range(ll)
        self._build_task_list(ll)

        splitter.addWidget(left)

        # ── Right panel: stacked widget ───────────────────
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background: {BG};")

        self._view_overview = self._build_overview_tab()
        self._stack.addWidget(self._view_overview)       # index 0

        self._cal_tab = CalendarWidget(store=self._store)
        self._cal_tab.reload_needed.connect(self._trigger_reload)
        self._stack.addWidget(self._cal_tab)             # index 1

        self._goals_tab = GoalsTab()
        self._goals_tab.open_goal_dialog.connect(self._on_edit_goals)
        self._goals_tab.task_clicked.connect(self._open_task_view)
        self._goals_tab.edit_goal.connect(self._on_edit_single_goal)
        self._goals_tab.cancel_goal.connect(self._on_cancel_goal)
        self._goals_tab.archive_goal.connect(self._on_archive_goal)
        self._stack.addWidget(self._goals_tab)           # index 2

        self._stack_base = {"overview": 0, "calendar": 1, "goals": 2}
        self._stack.setCurrentIndex(0)

        splitter.addWidget(self._stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        self._splitter = splitter
        QTimer.singleShot(0, lambda: self._splitter.setSizes([340, self._splitter.width() - 340]))
        root.addWidget(splitter, stretch=1)

    # ── Session bar ──────────────────────────────────────

    def _build_session_bar(self, ll: QVBoxLayout) -> None:
        bar = QFrame()
        bar.setObjectName("SessionBar")
        bar.setStyleSheet(
            f"QFrame#SessionBar {{ background: {BG2}; border-bottom: 1px solid {BORDER}; }}"
        )
        bl = QVBoxLayout(bar)
        bl.setContentsMargins(PAD_MD, PAD, PAD_MD, PAD)
        bl.setSpacing(4)

        top_row = QHBoxLayout()
        self._session_status_lbl = QLabel("○ IDLE")
        self._session_status_lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 9px; font-family: {FONT_MONO};"
            f" letter-spacing: 1.1px; background: transparent; border: none;"
        )
        top_row.addWidget(self._session_status_lbl)
        top_row.addStretch()
        self._session_dot = QLabel("●")
        self._session_dot.setStyleSheet(
            f"color: {MUTED}; font-size: 7px; background: transparent; border: none;"
        )
        top_row.addWidget(self._session_dot)
        bl.addLayout(top_row)

        mid_row = QHBoxLayout()
        self._session_task_lbl = QLabel("—")
        self._session_task_lbl.setStyleSheet(
            f"color: {TEXT}; font-size: 13px; font-weight: 600;"
            f" background: transparent; border: none;"
        )
        mid_row.addWidget(self._session_task_lbl, stretch=1)
        self._session_time_lbl = QLabel("00:00:00")
        self._session_time_lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 16px; font-family: {FONT_MONO};"
            f" font-weight: 600; font-variant-numeric: tabular-nums;"
            f" background: transparent; border: none;"
        )
        mid_row.addWidget(self._session_time_lbl)
        bl.addLayout(mid_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        self._session_combo = QComboBox()
        self._session_combo.setStyleSheet(SS.combo())
        self._session_combo.setFixedHeight(26)
        btn_row.addWidget(self._session_combo, stretch=1)

        self._session_clockin_btn = QPushButton("▶ CLOCK IN")
        self._session_clockin_btn.setFixedHeight(26)
        self._session_clockin_btn.setStyleSheet(SS.button("primary"))
        self._session_clockin_btn.clicked.connect(self._on_session_bar_clockin)
        btn_row.addWidget(self._session_clockin_btn)

        self._session_stop_btn = QPushButton("■ STOP")
        self._session_stop_btn.setFixedHeight(26)
        self._session_stop_btn.setStyleSheet(SS.button("danger"))
        self._session_stop_btn.clicked.connect(self._on_session_bar_stop)
        btn_row.addWidget(self._session_stop_btn)
        bl.addLayout(btn_row)

        ll.addWidget(bar)
        self._session_bar = bar

    def _update_session_bar(self) -> None:
        """Sync session bar state with the current clock state."""
        if not self._result:
            return
        clocked = next((t for t in self._result.tasks if t.is_clocked_in), None)
        self._clocked_task = clocked.name if clocked else None

        if clocked:
            self._session_status_lbl.setText("◉ CLOCKED IN")
            self._session_status_lbl.setStyleSheet(
                f"color: {SUCCESS}; font-size: 9px; font-family: {FONT_MONO};"
                f" letter-spacing: 1.1px; background: transparent; border: none;"
            )
            self._session_dot.setStyleSheet(
                f"color: {SUCCESS}; font-size: 7px; background: transparent; border: none;"
            )
            self._session_task_lbl.setText(clocked.name)
            self._session_task_lbl.setStyleSheet(
                f"color: {TEXT}; font-size: 13px; font-weight: 600;"
                f" background: transparent; border: none;"
            )
            elapsed = clocked.open_session.duration.total_seconds()
            self._update_session_bar_time(elapsed)
            self._session_combo.setVisible(False)
            self._session_clockin_btn.setVisible(False)
            self._session_stop_btn.setVisible(True)
        else:
            self._session_status_lbl.setText("○ IDLE")
            self._session_status_lbl.setStyleSheet(
                f"color: {MUTED}; font-size: 9px; font-family: {FONT_MONO};"
                f" letter-spacing: 1.1px; background: transparent; border: none;"
            )
            self._session_dot.setStyleSheet(
                f"color: {MUTED}; font-size: 7px; background: transparent; border: none;"
            )
            self._session_task_lbl.setText("—")
            self._session_task_lbl.setStyleSheet(
                f"color: {MUTED}; font-size: 13px; font-weight: 600;"
                f" background: transparent; border: none;"
            )
            self._session_time_lbl.setText("00:00:00")
            self._session_time_lbl.setStyleSheet(
                f"color: {MUTED}; font-size: 16px; font-family: {FONT_MONO};"
                f" font-weight: 600; background: transparent; border: none;"
            )
            self._session_combo.setVisible(True)
            self._session_clockin_btn.setVisible(True)
            self._session_stop_btn.setVisible(False)

        # Repopulate combo with current tasks
        self._session_combo.blockSignals(True)
        prev = self._session_combo.currentText()
        self._session_combo.clear()
        if self._result:
            for t in sorted(self._result.tasks, key=lambda x: x.name):
                if not t.archived:
                    self._session_combo.addItem(t.name)
            idx = self._session_combo.findText(prev)
            if idx >= 0:
                self._session_combo.setCurrentIndex(idx)
        self._session_combo.blockSignals(False)

    def _update_session_bar_time(self, elapsed_sec: float) -> None:
        h = int(elapsed_sec // 3600)
        m = int((elapsed_sec % 3600) // 60)
        s = int(elapsed_sec % 60)
        self._session_time_lbl.setText(f"{h:02d}:{m:02d}:{s:02d}")
        self._session_time_lbl.setStyleSheet(
            f"color: {ACCENT}; font-size: 16px; font-family: {FONT_MONO};"
            f" font-weight: 600; background: transparent; border: none;"
        )

    def _on_session_bar_clockin(self) -> None:
        task_name = self._session_combo.currentText()
        if task_name:
            self._on_clock_in(task_name)

    def _on_session_bar_stop(self) -> None:
        if self._clocked_task:
            self._on_clock_out(self._clocked_task)

    # ── Nav section ──────────────────────────────────────

    def _build_nav_section(self, ll: QVBoxLayout) -> None:
        nav = QFrame()
        nav.setStyleSheet(
            f"QFrame {{ background: {BG2}; border-bottom: 1px solid {BORDER}; }}"
        )
        nl = QVBoxLayout(nav)
        nl.setContentsMargins(6, 6, 6, 6)
        nl.setSpacing(2)

        self._nav_items: dict[str, QWidget] = {}
        goals_count = len([t for t in (self._goals or {}).keys()])
        for view_id, lbl_text, sym, badge in [
            ("overview", "Overview", "▦", None),
            ("calendar", "Calendar", "◫", None),
            ("goals",    "Goals",    "◎", str(goals_count) if goals_count else None),
        ]:
            item = self._make_nav_item(view_id, lbl_text, sym, badge)
            nl.addWidget(item)
            self._nav_items[view_id] = item

        ll.addWidget(nav)
        self._update_nav_highlight()

    def _make_nav_item(self, view_id: str, lbl_text: str, sym: str,
                       badge: str | None) -> QWidget:
        item = QWidget()
        item.setCursor(Qt.PointingHandCursor)
        item.setObjectName(f"NavItem")
        il = QHBoxLayout(item)
        il.setContentsMargins(10, 5, 10, 5)
        il.setSpacing(8)

        sym_lbl = QLabel(sym)
        sym_lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 10px; background: transparent; border: none;"
        )
        sym_lbl.setFixedWidth(14)
        il.addWidget(sym_lbl)

        name_lbl = QLabel(lbl_text)
        name_lbl.setStyleSheet(
            f"color: {DIM}; font-size: 11px; font-family: {FONT_MONO};"
            f" letter-spacing: 0.3px; background: transparent; border: none;"
        )
        il.addWidget(name_lbl, stretch=1)

        if badge:
            badge_lbl = QLabel(badge)
            badge_lbl.setStyleSheet(
                f"color: {MUTED}; font-size: 10px; font-family: {FONT_MONO};"
                f" background: transparent; border: none;"
            )
            il.addWidget(badge_lbl)

        item.mousePressEvent = lambda e, vid=view_id: self._select_view(vid)
        return item

    def _update_nav_highlight(self) -> None:
        for view_id, item in self._nav_items.items():
            active = (view_id == self._current_view)
            item.setStyleSheet(
                f"QWidget {{ background: {BG3 if active else 'transparent'};"
                f" border-left: 2px solid {ACCENT if active else 'transparent'};"
                f" border-radius: {RADIUS}px; }}"
            )
            # Re-color child labels
            for child in item.findChildren(QLabel):
                if child.text() in ("▦", "◫", "◎"):
                    child.setStyleSheet(
                        f"color: {ACCENT if active else MUTED}; font-size: 10px;"
                        f" background: transparent; border: none;"
                    )
                else:
                    child.setStyleSheet(
                        f"color: {TEXT if active else DIM}; font-size: 11px;"
                        f" font-family: {FONT_MONO}; letter-spacing: 0.3px;"
                        f" background: transparent; border: none;"
                    )

    def _select_view(self, key: str) -> None:
        """Switch the right panel to the given view."""
        self._current_view = key
        self._update_nav_highlight()

        if key in self._stack_base:
            self._stack.setCurrentIndex(self._stack_base[key])
            return

        if key.startswith("cat:"):
            cat_name = key[4:]
            if cat_name not in self._category_views:
                tab = CategoryTabWidget(cat_name, parent=self)
                self._stack.addWidget(tab)
                self._category_views[cat_name] = tab
                # Refresh immediately with current range
                if self._result and self._all_dates:
                    tab.refresh(
                        self._all_dates[self._date_low],
                        self._all_dates[self._date_high],
                        self._result.tasks, self._goals,
                    )
            self._stack.setCurrentWidget(self._category_views[cat_name])
            return

        if key.startswith("task:"):
            task_name = key[5:]
            self._open_task_view(task_name)

    # ── Date range ───────────────────────────────────────

    def _build_date_range(self, ll: QVBoxLayout) -> None:
        range_sec = QFrame()
        range_sec.setStyleSheet(
            f"QFrame {{ background: {BG2}; border-bottom: 1px solid {BORDER}; }}"
        )
        rl = QVBoxLayout(range_sec)
        rl.setContentsMargins(PAD_MD, PAD, PAD_MD, PAD)
        rl.setSpacing(PAD)
        self._preset_bar = PresetBar()
        self._preset_bar.preset_selected.connect(self._on_preset)
        self._preset_bar.add_custom_requested.connect(self._on_add_custom_preset)
        self._preset_bar.remove_custom_requested.connect(self._on_remove_custom_preset)
        if hasattr(self, "_custom_presets"):
            self._preset_bar.set_custom_presets(self._custom_presets)
        rl.addWidget(self._preset_bar)
        self._range_slider = RangeSlider()
        self._range_slider.range_changed.connect(self._on_range_changed)
        rl.addWidget(self._range_slider)
        self._range_lbl = label("", MUTED, size=9, mono=True)
        self._range_lbl.setAlignment(Qt.AlignCenter)
        rl.addWidget(self._range_lbl)
        ll.addWidget(range_sec)

    # ── Task list ────────────────────────────────────────

    def _build_task_list(self, ll: QVBoxLayout) -> None:
        tasks_hdr_frame = QFrame()
        tasks_hdr_frame.setStyleSheet(
            f"QFrame {{ background: {BG2}; border-bottom: 1px solid {BORDER}; }}"
        )
        tasks_hdr = QHBoxLayout(tasks_hdr_frame)
        tasks_hdr.setContentsMargins(PAD_MD, PAD, PAD_MD, PAD)
        tasks_hdr.setSpacing(PAD)
        tasks_hdr.addWidget(section_label("Tasks"))
        tasks_hdr.addStretch()

        self._archived_btn = QPushButton("Archived")
        self._archived_btn.setFixedHeight(20)
        self._archived_btn.setCheckable(True)
        self._archived_btn.setChecked(self._show_archived)
        self._archived_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {MUTED};"
            f" border: 1px solid {BORDER}; border-radius: {RADIUS}px;"
            f" font-size: 9px; font-family: {FONT_UI}; padding: 0 7px; }}"
            f" QPushButton:hover {{ color: {TEXT}; background: {BG3}; border-color: {BORDER2}; }}"
            f" QPushButton:checked {{ color: {ACCENT}; border-color: {ACCENT}; }}"
        )
        self._archived_btn.toggled.connect(self._on_toggle_archived)
        tasks_hdr.addWidget(self._archived_btn)

        add_cat_btn = QPushButton("+ Cat")
        add_cat_btn.setFixedHeight(20)
        add_cat_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {MUTED};"
            f" border: 1px solid {BORDER}; border-radius: {RADIUS}px;"
            f" font-size: 9px; font-family: {FONT_UI}; padding: 0 7px; }}"
            f" QPushButton:hover {{ color: {TEXT}; background: {BG3}; border-color: {BORDER2}; }}"
        )
        add_cat_btn.clicked.connect(self._on_category_menu)
        tasks_hdr.addWidget(add_cat_btn)
        ll.addWidget(tasks_hdr_frame)

        task_scroll = QScrollArea()
        task_scroll.setWidgetResizable(True)
        task_scroll.setStyleSheet(
            SS.scrollarea() + f" QScrollArea {{ background: {BG2}; }}"
        )
        self._task_container = QWidget()
        self._task_container.setStyleSheet(f"background: {BG2};")
        self._task_layout = QVBoxLayout(self._task_container)
        self._task_layout.setContentsMargins(0, 4, 0, 4)
        self._task_layout.setSpacing(0)
        self._task_layout.addStretch()
        task_scroll.setWidget(self._task_container)
        ll.addWidget(task_scroll, stretch=1)

        # Goals strip (top-3 by closest deadline)
        self._goals_strip = QFrame()
        self._goals_strip.setObjectName("GoalsStrip")
        self._goals_strip.setStyleSheet(
            f"QFrame#GoalsStrip {{ background: {BG2}; border-top: 1px solid {BORDER}; }}"
        )
        self._goals_strip_layout = QVBoxLayout(self._goals_strip)
        self._goals_strip_layout.setContentsMargins(PAD_MD, PAD, PAD_MD, PAD)
        self._goals_strip_layout.setSpacing(3)
        self._goals_strip.setVisible(False)
        ll.addWidget(self._goals_strip)

        # Footer
        footer = QFrame()
        footer.setFixedHeight(28)
        footer.setStyleSheet(
            f"QFrame {{ background: {BG2}; border-top: 1px solid {BORDER}; }}"
        )
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(PAD_MD, 0, PAD_MD, 0)
        self._footer_lbl = QLabel("◉ DB:OK")
        self._footer_lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 9px; font-family: {FONT_MONO};"
            f" background: transparent; border: none; letter-spacing: 0.4px;"
        )
        fl.addWidget(self._footer_lbl)
        fl.addStretch()
        self._footer_time = QLabel("")
        self._footer_time.setStyleSheet(
            f"color: {MUTED}; font-size: 9px; font-family: {FONT_MONO};"
            f" background: transparent; border: none; letter-spacing: 0.4px;"
        )
        fl.addWidget(self._footer_time)
        ll.addWidget(footer)

    def _on_export_all(self) -> None:
        """Export all sessions across all tasks to CSV."""
        from .widgets import export_sessions_to_csv
        if not self._result:
            return
        rows = []
        for t in self._result.tasks:
            for s in t.sessions:
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
        export_sessions_to_csv(rows, "all_sessions.csv", self)

    def _build_overview_tab(self) -> QWidget:
        """Build and return the overview scroll area."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(SS.scrollarea())
        right_inner = QWidget()
        right_inner.setStyleSheet(f"background: {BG};")
        cl = QVBoxLayout(right_inner)
        cl.setContentsMargins(PAD, PAD_MD, PAD_MD, PAD_MD)
        cl.setSpacing(PAD)

        # Overview header with export button
        ov_hdr = QHBoxLayout()
        ov_hdr.addWidget(label("Overview", TEXT, bold=True, size=14))
        ov_hdr.addStretch()
        export_all_btn = QPushButton("Export CSV")
        export_all_btn.setFixedHeight(24)
        export_all_btn.setStyleSheet(SS.button("ghost"))
        export_all_btn.clicked.connect(self._on_export_all)
        ov_hdr.addWidget(export_all_btn)
        cl.addLayout(ov_hdr)

        # Metric cards (5 across)
        mc_row = QHBoxLayout()
        mc_row.setSpacing(PAD)
        self._mc_today    = MetricCard("Today")
        self._mc_total    = MetricCard("Total tracked time")
        self._mc_sessions = MetricCard("Sessions")
        self._mc_avg      = MetricCard("Avg session")
        self._mc_streak   = MetricCard("Current streak")
        for mc in [self._mc_today, self._mc_total, self._mc_sessions,
                   self._mc_avg, self._mc_streak]:
            mc_row.addWidget(mc)
        cl.addLayout(mc_row)

        # Insight strip
        self._insight_strip = InsightStrip()
        cl.addWidget(self._insight_strip)

        _hs_css = (
            f"QSplitter::handle:horizontal {{ background: {BORDER}; width: 4px; margin: 0 1px; }}"
            f"QSplitter::handle:horizontal:hover {{ background: {ACCENT}; }}"
        )

        self._stacked_chart = StackedAreaChart()
        cl.addWidget(make_resizable_chart_panel("Daily activity", self._stacked_chart))

        row2_panel = ResizableChartPanel("")
        row2_split = QSplitter(Qt.Horizontal)
        row2_split.setChildrenCollapsible(False)
        row2_split.setStyleSheet(_hs_css)
        self._wd_chart = WeekdayBarChart()
        row2_split.addWidget(make_chart_panel("Avg by weekday", self._wd_chart))
        self._wc_chart = WeeklyCompChart()
        row2_split.addWidget(make_chart_panel("This week vs last week", self._wc_chart))
        row2_panel.add_widget(row2_split)
        cl.addWidget(row2_panel)

        self._hm_chart = HourHeatmap()
        cl.addWidget(make_resizable_chart_panel("Hour-of-day heatmap", self._hm_chart))

        self._cat_breakdown = CategoryPieChart()
        cl.addWidget(make_resizable_chart_panel("Category breakdown", self._cat_breakdown))

        cl.addStretch()
        scroll.setWidget(right_inner)
        return scroll

    # ── Data loading ─────────────────────────────────────

    def _trigger_reload(self) -> None:
        if self._thread and self._thread.isRunning():
            self._reload_pending = True
            return
        self._thread = QThread(self)
        self._worker = ReloadWorker(self._store)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.done.connect(self._on_worker_done)
        self._worker.error.connect(self._on_reload_error)
        self._worker.done.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.start()

    def _on_worker_done(self) -> None:
        if self._worker and self._worker.result:
            if self._worker.goals is not None:
                self._goals = self._worker.goals
            if self._worker.categories:
                self._categories = self._worker.categories
            self._on_reload_done(self._worker.result)
        if self._reload_pending:
            self._reload_pending = False
            self._trigger_reload()

    def _on_reload_done(self, result: ParseResult) -> None:
        self.setUpdatesEnabled(False)
        try:
            self._result = result
            self._apply_goals_to_tasks()

            old_count = len(self._all_dates)
            prev_low  = self._date_low
            prev_high = self._date_high
            all_dates: set[date] = set()
            for t in result.tasks:
                for s in t.sessions:
                    all_dates.add(s.date)
            self._all_dates = sorted(all_dates)

            if self._all_dates:
                new_count = len(self._all_dates)
                self._range_slider.set_count(new_count)
                if old_count == 0:
                    # First load — show everything
                    self._date_low  = 0
                    self._date_high = new_count - 1
                else:
                    # Preserve the user's selection.
                    # If high was at the last date, extend it to include any new dates
                    # (e.g. first session of a new calendar day) without resetting low.
                    at_max = prev_high >= old_count - 1
                    self._date_high = new_count - 1 if at_max else min(prev_high, new_count - 1)
                    self._date_low  = min(prev_low, self._date_high)
                self._range_slider.set_range(self._date_low, self._date_high)

            ts = result.parsed_at.strftime("%H:%M:%S")
            self._updated_lbl.setText(f"Updated {ts}  ·  {len(result.tasks)} tasks")
            if hasattr(self, "_footer_time"):
                self._footer_time.setText(ts)

            self._rebuild_task_rows()
            self._refresh_all()
            if self._cal_tab:
                self._cal_tab.refresh(result)
            self._rebuild_goal_rows()
            if hasattr(self, "_session_bar"):
                self._update_session_bar()
        finally:
            self.setUpdatesEnabled(True)

    def _on_reload_error(self, msg: str) -> None:
        self._updated_lbl.setText("Error — see console")
        print(msg, flush=True)
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle("Failed to load data")
        dlg.resize(700, 400)
        layout = QVBoxLayout(dlg)
        te = QTextEdit()
        te.setReadOnly(True)
        te.setPlainText(msg)
        te.setFont(__import__("PyQt5.QtGui", fromlist=["QFont"]).QFont("Courier New", 9))
        layout.addWidget(te)
        btns = QDialogButtonBox(QDialogButtonBox.Ok)
        btns.accepted.connect(dlg.accept)
        layout.addWidget(btns)
        dlg.exec_()

    def _apply_goals_to_tasks(self) -> None:
        if not self._result:
            return
        goals_changed = False
        for t in self._result.tasks:
            gs = self._goals.get(t.name, GoalSpec())
            t.goal_hours    = gs.hours
            t.goal_deadline = gs.deadline
            # Mark completion date when goal first reaches 100%
            if gs.hours > 0 and t.goal_progress() >= 1.0 and gs.completed_on is None:
                gs = GoalSpec(
                    hours=gs.hours,
                    deadline=gs.deadline,
                    completed_on=date.today(),
                )
                self._goals[t.name] = gs
                goals_changed = True
        if goals_changed and self._result:
            try:
                self._store.save_goals(self._goals, self._result.tasks)
            except Exception:
                pass

    # ── Sidebar task list (grouped by category) ──────────

    def _rebuild_task_rows(self) -> None:
        """Rebuild the sidebar task list, grouped by category."""
        while self._task_layout.count() > 1:
            item = self._task_layout.takeAt(0)
            if w := item.widget():
                w.hide()
                w.deleteLater()

        if not self._result:
            return

        visible_tasks = [
            t for t in self._result.tasks
            if not t.archived or self._show_archived
        ]
        hidden_archived = sum(1 for t in self._result.tasks if t.archived and not self._show_archived)

        all_sec = [t.total_seconds for t in visible_tasks]
        max_sec = max(all_sec) if all_sec else 1.0

        # Group tasks by category (preserve category order from self._categories)
        cat_order = [c[0] for c in self._categories] if self._categories else []
        by_cat: dict[str, list] = {}
        for t in visible_tasks:
            by_cat.setdefault(t.tag or "none", []).append(t)

        # Sort tasks within each category by total_seconds desc
        for tasks in by_cat.values():
            tasks.sort(key=lambda t: t.total_seconds, reverse=True)

        # Build ordered list of (cat_name, cat_color) respecting DB order
        ordered_cats = []
        for cat_name, colour_tag in self._categories:
            if cat_name in by_cat:
                ordered_cats.append((cat_name, _swatch_for_tag(colour_tag)))
        # Any category in data but not in self._categories (shouldn't happen normally)
        for cat in by_cat:
            if cat not in {c[0] for c in ordered_cats}:
                ordered_cats.append((cat, MUTED))

        insert_at = self._task_layout.count() - 1  # before the stretch

        for cat_name, cat_color in ordered_cats:
            tasks = by_cat.get(cat_name, [])
            if not tasks:
                continue

            # Category total
            cat_total_sec = sum(t.total_seconds for t in tasks)

            collapsed = cat_name in self._collapsed_cats

            # Category header row
            cat_row = QWidget(self._task_container)
            cat_row.setCursor(Qt.PointingHandCursor)
            cat_row.setStyleSheet("QWidget { background: transparent; }")
            cr = QHBoxLayout(cat_row)
            cr.setContentsMargins(PAD_MD, 6, PAD_MD, 6)
            cr.setSpacing(8)

            arrow_btn = QPushButton("▸" if collapsed else "▾")
            arrow_btn.setFlat(True)
            arrow_btn.setFixedSize(18, 18)
            arrow_btn.setCursor(Qt.PointingHandCursor)
            arrow_btn.setStyleSheet(
                f"QPushButton {{ color: {MUTED}; font-size: 10px; font-family: {FONT_MONO};"
                f" border: none; background: transparent; padding: 0; }}"
                f" QPushButton:hover {{ color: {TEXT}; }}"
            )
            arrow_btn.clicked.connect(
                lambda _checked=False, cn=cat_name, ab=arrow_btn: self._toggle_cat_collapse(cn, ab)
            )
            cr.addWidget(arrow_btn)

            dot_lbl = QLabel("⬤")
            dot_lbl.setFixedWidth(14)
            dot_lbl.setStyleSheet(
                f"color: {cat_color}; font-size: 11px; background: transparent; border: none;"
            )
            cr.addWidget(dot_lbl)

            cap = cat_name[:1].upper() + cat_name[1:] if cat_name else cat_name
            cat_lbl = QLabel(cap)
            cat_lbl.setStyleSheet(
                f"color: {TEXT}; font-size: 14px; font-family: {FONT_UI}; font-weight: 600;"
                f" background: transparent; border: none;"
            )
            cr.addWidget(cat_lbl, stretch=1)

            cat_hrs = QLabel(fmt_dur(cat_total_sec, short=True))
            cat_hrs.setStyleSheet(
                f"color: {MUTED}; font-size: 12px; font-family: {FONT_MONO};"
                f" background: transparent; border: none;"
            )
            cr.addWidget(cat_hrs)

            view_key = f"cat:{cat_name}"
            cat_row.mousePressEvent = (
                lambda e, k=view_key: self._select_view(k) if e.button() == Qt.LeftButton else None
            )
            self._task_layout.insertWidget(insert_at, cat_row)
            insert_at += 1

            # Task items (indented, hidden if collapsed)
            task_widgets = []
            for t in tasks:
                item = self._make_sidebar_task_item(t, max_sec)
                item.setVisible(not collapsed)
                self._task_layout.insertWidget(insert_at, item)
                task_widgets.append(item)
                insert_at += 1
            self._sidebar_cat_items[cat_name] = task_widgets

        # "+" new task button
        if hidden_archived > 0 and not self._show_archived:
            hint = label(f"{hidden_archived} archived hidden", FAINT, size=9)
            hint.setAlignment(Qt.AlignCenter)
            hint.setContentsMargins(0, 4, 0, 4)
            self._task_layout.insertWidget(insert_at, hint)
            insert_at += 1

        add_btn = QPushButton("+ New Task")
        add_btn.setFixedHeight(26)
        add_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {FAINT};"
            f" border: 1px dashed {BORDER}; border-radius: {RADIUS}px;"
            f" font-size: 10px; margin: 4px 8px; }}"
            f" QPushButton:hover {{ color: {MUTED}; border-color: {BORDER2}; }}"
        )
        add_btn.clicked.connect(self._on_new_task)
        self._task_layout.insertWidget(insert_at, add_btn)

        self._rebuild_goal_rows()

    def _make_sidebar_task_item(self, task, max_sec: float) -> QWidget:
        """Compact task item for the sidebar."""
        item = QWidget(self._task_container)
        item.setCursor(Qt.PointingHandCursor)
        item.setObjectName(f"SidebarTask")
        item.setContextMenuPolicy(Qt.CustomContextMenu)
        item.customContextMenuRequested.connect(
            lambda pos, n=task.name: self._sidebar_task_menu(
                n, item.mapToGlobal(pos))
        )

        il = QHBoxLayout(item)
        il.setContentsMargins(44, 8, PAD_MD, 8)
        il.setSpacing(10)

        dot = QLabel("⬤")
        dot.setFixedWidth(14)
        dot.setStyleSheet(
            f"color: {task.colour}; font-size: 11px; background: transparent; border: none;"
        )
        il.addWidget(dot)

        name_lbl = QLabel(task.name)
        name_lbl.setStyleSheet(
            f"color: {ACCENT if task.is_clocked_in else TEXT}; font-size: 14px;"
            f" font-family: {FONT_UI}; background: transparent; border: none;"
        )
        il.addWidget(name_lbl, stretch=1)

        # 44×4 mini progress bar
        pct = task.total_seconds / max_sec if max_sec > 0 else 0
        bar_outer = QFrame()
        bar_outer.setFixedSize(44, 4)
        bar_outer.setStyleSheet(f"background: {BG3}; border-radius: 2px;")
        bar_fill = QFrame(bar_outer)
        fill_w = max(2, int(pct * 44))
        fill_c = QColor(task.colour)
        fill_c.setAlphaF(0.8)
        bar_fill.setGeometry(0, 0, fill_w, 4)
        bar_fill.setStyleSheet(
            f"background: {fill_c.name(QColor.HexArgb)}; border-radius: 2px;"
        )
        il.addWidget(bar_outer)

        hrs_lbl = QLabel(fmt_dur(task.total_seconds, short=True))
        hrs_lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 12px; font-family: {FONT_MONO};"
            f" background: transparent; border: none;"
        )
        il.addWidget(hrs_lbl)

        # Style for selected/active state (left border)
        if task.is_clocked_in:
            item.setStyleSheet(
                f"QWidget#SidebarTask {{ border-left: 2px solid {ACCENT}; background: transparent; }}"
            )
        else:
            item.setStyleSheet(
                f"QWidget#SidebarTask {{ border-left: 2px solid transparent; background: transparent; }}"
            )

        item.mousePressEvent = lambda e, n=task.name: self._on_sidebar_task_click(n)
        return item

    def _on_sidebar_task_click(self, task_name: str) -> None:
        self._select_view(f"task:{task_name}")

    def _toggle_cat_collapse(self, cat_name: str, arrow_widget) -> None:
        if cat_name in self._collapsed_cats:
            self._collapsed_cats.discard(cat_name)
            arrow_widget.setText("▾")
        else:
            self._collapsed_cats.add(cat_name)
            arrow_widget.setText("▸")
        for w in self._sidebar_cat_items.get(cat_name, []):
            w.setVisible(cat_name not in self._collapsed_cats)

    def _sidebar_task_menu(self, task_name: str, global_pos) -> None:
        task = self._result.task_by_name(task_name) if self._result else None
        if not task:
            return
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background: {BG3}; color: {TEXT}; border: 1px solid {BORDER};"
            f" border-radius: {RADIUS}px; font-size: 10px; font-family: {FONT_UI}; }}"
            f" QMenu::item {{ padding: 4px 16px; }}"
            f" QMenu::item:selected {{ background: {BG4}; }}"
        )
        if task.is_clocked_in:
            menu.addAction("■ Stop tracking", lambda: self._on_clock_out(task_name))
        else:
            menu.addAction("▶ Clock in", lambda: self._on_clock_in(task_name))
        menu.addSeparator()
        menu.addAction("Rename…", lambda: self._on_rename_task(task_name))
        menu.addAction("Move to category…", lambda: self._on_move_task(task_name))
        menu.addSeparator()
        if task.archived:
            menu.addAction("Unarchive", lambda: self._on_archive_task(task_name, False))
        else:
            menu.addAction("Archive", lambda: self._on_archive_task(task_name, True))
        menu.addAction("Delete…", lambda: self._on_delete_task(task_name))
        menu.exec_(global_pos)

    def _rebuild_goal_rows(self) -> None:
        if not self._result:
            return
        all_goal_tasks = [t for t in self._result.tasks if t.goal_hours > 0]
        if self._goals_tab:
            self._goals_tab.refresh(all_goal_tasks, self._goals)
        if hasattr(self, "_goals_strip"):
            self._rebuild_goals_strip(all_goal_tasks)

    def _rebuild_goals_strip(self, tasks_with_goals: list) -> None:
        """Top-3 goals by closest deadline shown at bottom of left panel."""
        while self._goals_strip_layout.count():
            item = self._goals_strip_layout.takeAt(0)
            if w := item.widget():
                w.hide()
                w.deleteLater()

        today = date.today()
        active = [
            t for t in tasks_with_goals
            if not _goal_is_archived(self._goals.get(t.name, GoalSpec()), today)
        ]
        if not active:
            self._goals_strip.setVisible(False)
            return

        self._goals_strip.setVisible(True)

        # Header
        hdr_w = QWidget()
        hdr_w.setStyleSheet("background: transparent;")
        hdr = QHBoxLayout(hdr_w)
        hdr.setContentsMargins(0, 0, 0, 0)
        h_lbl = QLabel("GOALS")
        h_lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 8px; font-family: {FONT_MONO};"
            f" letter-spacing: 1px; background: transparent; border: none;"
        )
        hdr.addWidget(h_lbl)
        hdr.addStretch()
        see_all = QPushButton("See all →")
        see_all.setFlat(True)
        see_all.setCursor(Qt.PointingHandCursor)
        see_all.setStyleSheet(
            f"color: {ACCENT}; font-size: 9px; background: transparent; border: none;"
        )
        see_all.clicked.connect(self._switch_to_goals_tab)
        hdr.addWidget(see_all)
        self._goals_strip_layout.addWidget(hdr_w)

        # Sort: tasks with deadlines first (nearest first), then rest
        def _sort_key(t):
            dl = t.deadline_days_left()
            return (0 if dl is not None else 1, dl if dl is not None else 9999)

        top3 = sorted(active, key=_sort_key)[:3]
        for t in top3:
            pct = t.goal_progress()
            dl  = t.deadline_days_left()

            row = QWidget(self._goals_strip)
            row.setCursor(Qt.PointingHandCursor)
            row.setStyleSheet("background: transparent;")
            rl = QVBoxLayout(row)
            rl.setContentsMargins(0, 2, 0, 2)
            rl.setSpacing(2)

            name_row = QHBoxLayout()
            name_row.setSpacing(4)
            dot = QLabel("●")
            dot.setFixedWidth(10)
            dot.setStyleSheet(
                f"color: {t.colour}; font-size: 6px; background: transparent; border: none;"
            )
            name_row.addWidget(dot)
            name_lbl = QLabel(t.name if len(t.name) <= 18 else t.name[:17] + "…")
            name_lbl.setStyleSheet(
                f"color: {TEXT}; font-size: 10px; background: transparent; border: none;"
            )
            name_row.addWidget(name_lbl, stretch=1)

            if dl is not None:
                dl_color = DANGER if dl < 5 else (WARNING if dl < 14 else MUTED)
                dl_lbl = QLabel(f"{dl}d")
                dl_lbl.setStyleSheet(
                    f"color: {dl_color}; font-size: 9px; font-family: {FONT_MONO};"
                    f" background: transparent; border: none;"
                )
                name_row.addWidget(dl_lbl)
            rl.addLayout(name_row)

            # Mini progress bar
            bar_outer = QWidget(row)
            bar_outer.setFixedHeight(3)
            bar_outer.setStyleSheet(f"background: {BG3}; border-radius: 1px;")
            bar_lay = QHBoxLayout(bar_outer)
            bar_lay.setContentsMargins(0, 0, 0, 0)
            bar_lay.setSpacing(0)
            fill = QWidget(bar_outer)
            fill.setFixedHeight(3)
            fill.setStyleSheet(f"background: {t.colour}; border-radius: 1px;")
            bar_lay.addWidget(fill, stretch=max(1, int(pct * 100)))
            bar_lay.addStretch(max(1, 100 - int(pct * 100)))
            rl.addWidget(bar_outer)

            row.mousePressEvent = lambda e, n=t.name: self._open_task_view(n)
            self._goals_strip_layout.addWidget(row)

    def _switch_to_goals_tab(self) -> None:
        self._select_view("goals")

    # ── Chart refresh ────────────────────────────────────

    def _refresh_all(self) -> None:
        stats = self._current_stats()
        if stats is None:
            return

        self._update_metric_cards(stats)
        self._update_range_label()

        self._stacked_chart.refresh(stats, self._goals)
        self._wd_chart.refresh(stats)
        self._hm_chart.refresh(stats)
        self._cat_breakdown.refresh(stats)

        if self._result:
            comp = WeeklyComparison(self._result.tasks)
            self._wc_chart.refresh_comparison(comp)

        # Insights
        engine   = InsightEngine(
            self._result.tasks if self._result else [],
            stats, self._goals,
        )
        insights = engine.compute()
        self._insight_strip.refresh(insights)

        self._rebuild_goal_rows()

        if not self._result or not self._all_dates:
            return
        start = self._all_dates[self._date_low]
        end   = self._all_dates[self._date_high]

        # Refresh category views
        for tab in self._category_views.values():
            tab.refresh(start, end, self._result.tasks, self._goals)

        # Refresh task views
        for task_name, tab in list(self._task_views.items()):
            task = self._result.task_by_name(task_name)
            if task:
                tab.update_task(task)
                tab.refresh(start, end)
            else:
                self._stack.removeWidget(tab)
                self._task_views.pop(task_name, None)
                tab.deleteLater()

    def _current_stats(self) -> Optional[RangeStats]:
        if not self._result or not self._all_dates:
            return None
        s = self._all_dates[self._date_low]
        e = self._all_dates[self._date_high]
        return RangeStats(self._result.tasks, s, e)

    def _update_metric_cards(self, stats: RangeStats) -> None:
        import statistics as _stats
        from datetime import date as _date
        today = _date.today()
        today_sec = sum(
            s.duration_seconds
            for t in (self._result.tasks if self._result else [])
            for s in t.sessions
            if s.start.date() == today
        )
        today_sess = sum(
            1 for t in (self._result.tasks if self._result else [])
            for s in t.sessions if s.start.date() == today
        )
        self._mc_today.update_value(
            fmt_dur(today_sec, short=True),
            f"{today_sess} session{'s' if today_sess != 1 else ''} today",
        )

        self._mc_total.update_value(
            fmt_dur(stats.grand_total_seconds, short=True),
            f"{stats.grand_total_seconds / 3600:.1f}h total",
        )

        n_sess = sum(
            len(t.sessions_in_range(stats.start, stats.end))
            for t in stats.tasks
        )
        spd = n_sess / max(1, stats.n_days)
        self._mc_sessions.update_value(
            str(n_sess),
            f"μ {spd:.1f}/day  ·  {stats.n_days}d",
        )

        closed = [s for t in stats.tasks
                  for s in t.sessions_in_range(stats.start, stats.end)
                  if not s.is_open]
        if closed:
            durations = [s.duration_seconds for s in closed]
            avg = sum(durations) / len(durations)
            std = _stats.stdev(durations) if len(durations) > 1 else 0.0
            self._mc_avg.update_value(
                fmt_dur(avg, short=True),
                f"σ {fmt_dur(std, short=True)}",
            )
        else:
            self._mc_avg.update_value("—")

        streak = streak_days(self._result.tasks if self._result else [])
        s_col  = SUCCESS if streak >= 7 else (WARNING if streak >= 3 else TEXT)
        self._mc_streak.update_value(
            f"{streak}d", "consecutive", colour=s_col
        )

    def _update_range_label(self) -> None:
        if not self._all_dates:
            return
        s = self._all_dates[self._date_low]
        e = self._all_dates[self._date_high]
        self._range_lbl.setText(
            f"{s.strftime('%d %b %Y')} – {e.strftime('%d %b %Y')}"
            f"  ({(e - s).days + 1}d)"
        )

    # ── Clock in / out ───────────────────────────────────

    def _on_clock_in(self, task_name: str) -> None:
        if not self._result:
            return
        try:
            self._store.clock_in(task_name, self._result)
        except Exception as e:
            QMessageBox.warning(self, "Clock-in failed", str(e))
            return
        self._trigger_reload()

    def _on_clock_out(self, task_name: str) -> None:
        if not self._result:
            return
        try:
            self._store.clock_out(task_name, self._result)
        except Exception as e:
            QMessageBox.warning(self, "Clock-out failed", str(e))
            return
        self._trigger_reload()

    # ── Tick ─────────────────────────────────────────────

    def _on_tick(self) -> None:
        if not self._result:
            return
        # Update footer clock
        if hasattr(self, "_footer_time"):
            from datetime import datetime as _dt
            self._footer_time.setText(_dt.now().strftime("%H:%M:%S"))
        # Update session bar timer
        if self._clocked_task:
            t = self._result.task_by_name(self._clocked_task)
            if t and t.is_clocked_in and t.open_session:
                self._update_session_bar_time(
                    t.open_session.duration.total_seconds()
                )

    # ── Date range controls ──────────────────────────────

    def _on_range_changed(self, low: int, high: int) -> None:
        self._date_low  = low
        self._date_high = high
        self._update_range_label()
        self._refresh_timer.start()

    def _on_preset(self, preset: str) -> None:
        if not self._all_dates:
            return
        if preset.startswith("custom:"):
            idx = int(preset[7:])
            if idx >= len(self._custom_presets):
                return
            cp    = self._custom_presets[idx]
            start = cp.from_date
            end   = cp.to_date or date.today()
        else:
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

    def _on_add_custom_preset(self) -> None:
        from .dialogs import AddCustomPresetDialog
        from ..core.user_presets import CustomPreset, save_presets
        if len(self._custom_presets) >= 5:
            QMessageBox.information(self, "Limit reached",
                                    "You can have at most 5 custom presets.\n"
                                    "Right-click an existing one to remove it first.")
            return
        dlg = AddCustomPresetDialog(parent=self)
        if dlg.exec_() != QDialog.Accepted:
            return
        lbl, from_d, to_d = dlg.values()
        self._custom_presets.append(CustomPreset(label=lbl, from_date=from_d, to_date=to_d))
        save_presets(self._custom_presets)
        self._preset_bar.set_custom_presets(self._custom_presets)

    def _on_remove_custom_preset(self, idx: int) -> None:
        from ..core.user_presets import save_presets
        if not (0 <= idx < len(self._custom_presets)):
            return
        lbl = self._custom_presets[idx].label
        reply = QMessageBox.question(
            self, "Remove Preset", f"Remove preset \"{lbl}\"?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self._custom_presets.pop(idx)
        save_presets(self._custom_presets)
        self._preset_bar.set_custom_presets(self._custom_presets)

    # ── New task ─────────────────────────────────────────

    def _on_new_task(self) -> None:
        if not self._categories:
            QMessageBox.information(self, "No categories",
                                    "Create a category first with '+ New Category'.")
            return
        dlg = NewTaskDialog(self._categories, parent=self)
        if dlg.exec_() != QDialog.Accepted:
            return
        name, category = dlg.values()
        try:
            self._store.create_task(name, category)
        except Exception as e:
            QMessageBox.warning(self, "Failed to create task", str(e))
            return
        self._trigger_reload()

    def _on_category_menu(self) -> None:
        btn = self.sender()
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background: {BG3}; color: {TEXT}; border: 1px solid {BORDER};"
            f" border-radius: 4px; font-size: 10px; }}"
            f" QMenu::item {{ padding: 4px 16px; }}"
            f" QMenu::item:selected {{ background: {BG4}; }}"
        )
        menu.addAction("New category…", self._on_new_category)
        menu.addAction("Rename category…", self._on_rename_category)
        menu.addAction("Recolor category…", self._on_recolor_category)
        pos = btn.mapToGlobal(btn.rect().bottomLeft())
        menu.exec_(pos)

    def _on_new_category(self) -> None:
        dlg = NewCategoryDialog(parent=self)
        if dlg.exec_() != QDialog.Accepted:
            return
        cat_name, colour_tag = dlg.values()
        try:
            self._store.create_category(cat_name, colour_tag)
        except Exception as e:
            QMessageBox.warning(self, "Failed to create category", str(e))
            return
        # Refresh categories immediately so the next NewTaskDialog sees it
        self._categories = self._store.load_categories()

    def _on_rename_category(self) -> None:
        if not self._categories:
            QMessageBox.information(self, "No categories", "No categories to rename.")
            return
        dlg = RenameCategoryDialog(self._categories, parent=self)
        if dlg.exec_() != QDialog.Accepted:
            return
        old_name, new_name = dlg.values()
        if old_name == new_name:
            return
        try:
            self._store.rename_category(old_name, new_name)
        except Exception as e:
            QMessageBox.warning(self, "Failed to rename category", str(e))
            return
        self._categories = self._store.load_categories()
        self._trigger_reload()

    def _on_recolor_category(self) -> None:
        if not self._categories:
            QMessageBox.information(self, "No categories", "No categories to recolor.")
            return
        dlg = RecolorCategoryDialog(self._categories, parent=self)
        if dlg.exec_() != QDialog.Accepted:
            return
        cat_name, new_colour_tag = dlg.values()
        try:
            self._store.recolor_category(cat_name, new_colour_tag)
        except Exception as e:
            QMessageBox.warning(self, "Failed to recolor category", str(e))
            return
        self._categories = self._store.load_categories()
        self._trigger_reload()

    # ── View management (stacked widget) ─────────────────

    def _open_task_view(self, task_name: str) -> None:
        """Show the task detail view in the stacked widget."""
        if task_name in self._task_views:
            self._current_view = f"task:{task_name}"
            self._update_nav_highlight()
            self._stack.setCurrentWidget(self._task_views[task_name])
            self._sync_combo_to_task(task_name)
            return
        if not self._result:
            return
        task = self._result.task_by_name(task_name)
        if not task:
            return
        tab = TaskTabWidget(task, parent=self)
        tab.edit_session_requested.connect(self._on_edit_session)
        tab.delete_session_requested.connect(self._on_delete_session)
        tab.add_session_requested.connect(self._on_add_session)
        tab.edit_goal_requested.connect(self._on_edit_single_goal)
        tab.remove_goal_requested.connect(self._on_cancel_goal)
        self._stack.addWidget(tab)
        self._task_views[task_name] = tab
        self._current_view = f"task:{task_name}"
        self._update_nav_highlight()
        self._stack.setCurrentWidget(tab)
        self._sync_combo_to_task(task_name)

        if self._all_dates:
            tab.refresh(
                self._all_dates[self._date_low],
                self._all_dates[self._date_high],
            )

    def _sync_combo_to_task(self, task_name: str) -> None:
        """Set the clock-in combo to task_name if not currently clocked in."""
        if self._clocked_task:
            return
        if not hasattr(self, "_session_combo"):
            return
        idx = self._session_combo.findText(task_name)
        if idx >= 0:
            self._session_combo.setCurrentIndex(idx)

    # ── Task editing ─────────────────────────────────────

    def _on_rename_task(self, task_name: str) -> None:
        task = self._result.task_by_name(task_name) if self._result else None
        if not task:
            return
        dlg = RenameTaskDialog(task_name, parent=self)
        if dlg.exec_() != QDialog.Accepted:
            return
        new_name = dlg.value()
        try:
            self._store.rename_task(task.start_line, new_name)
        except Exception as e:
            QMessageBox.warning(self, "Rename failed", str(e))
            return
        self._trigger_reload()

    def _on_move_task(self, task_name: str) -> None:
        task = self._result.task_by_name(task_name) if self._result else None
        if not task:
            return
        dlg = MoveTaskDialog(self._categories, parent=self)
        if dlg.exec_() != QDialog.Accepted:
            return
        new_cat = dlg.value()
        try:
            self._store.move_task(task.start_line, new_cat)
        except Exception as e:
            QMessageBox.warning(self, "Move failed", str(e))
            return
        self._trigger_reload()

    def _on_delete_task(self, task_name: str) -> None:
        task = self._result.task_by_name(task_name) if self._result else None
        if not task:
            return
        reply = QMessageBox.question(
            self, "Delete task",
            f"Delete '{task_name}' and all its sessions permanently?\n\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            self._store.delete_task(task.start_line)
        except Exception as e:
            QMessageBox.warning(self, "Delete failed", str(e))
            return
        # Remove task view from stack if open
        if task_name in self._task_views:
            tab = self._task_views.pop(task_name)
            self._stack.removeWidget(tab)
            tab.deleteLater()
            # Go back to overview if we were viewing the deleted task
            if self._current_view == f"task:{task_name}":
                self._select_view("overview")
        self._trigger_reload()

    def _on_archive_task(self, task_name: str, archived: bool) -> None:
        task = self._result.task_by_name(task_name) if self._result else None
        if not task:
            return
        try:
            self._store.set_archived(task.start_line, archived)
        except Exception as e:
            QMessageBox.warning(self, "Archive failed", str(e))
            return
        self._trigger_reload()

    def _on_toggle_archived(self, checked: bool) -> None:
        self._show_archived = checked
        self.setUpdatesEnabled(False)
        try:
            self._rebuild_task_rows()
        finally:
            self.setUpdatesEnabled(True)

    # ── Theme toggle ─────────────────────────────────────────

    def _on_toggle_theme(self) -> None:
        saved_view = getattr(self, "_current_view", "overview")

        from ..ui import theme as _theme
        if _theme.IS_DARK:
            _theme.set_light_mode()
            self._theme_btn.setText("☾ Dark")
        else:
            _theme.set_dark_mode()
            self._theme_btn.setText("☀ Light")

        self._category_views = {}
        self._task_views     = {}
        self._current_view   = "overview"
        self._build_ui()
        self._apply_palette()
        if self._result:
            self._on_reload_done(self._result)

        if saved_view and saved_view in self._stack_base:
            self._select_view(saved_view)

    # ── Session management ───────────────────────────────────

    def _on_add_session(self, task_id: int) -> None:
        dlg = AddSessionDialog(parent=self)
        if dlg.exec_() != QDialog.Accepted:
            return
        start_dt, end_dt, note = dlg.values()
        try:
            self._store.add_session(task_id, start_dt, end_dt, note)
        except Exception as e:
            QMessageBox.warning(self, "Failed to add session", str(e))
            return
        self._trigger_reload()

    def _on_edit_session(self, session_id: int, start, end, note: str = "") -> None:
        dlg = EditSessionDialog(start, end, note, parent=self)
        if dlg.exec_() != QDialog.Accepted:
            return
        new_start, new_end, new_note = dlg.values()
        try:
            self._store.update_session(session_id, new_start, new_end, new_note)
        except Exception as e:
            QMessageBox.warning(self, "Failed to update session", str(e))
            return
        self._trigger_reload()

    def _on_delete_session(self, session_id: int, is_open: bool) -> None:
        reply = QMessageBox.question(
            self, "Delete session",
            "Delete this session permanently?\n\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            self._store.delete_session(session_id, is_open)
        except Exception as e:
            QMessageBox.warning(self, "Failed to delete session", str(e))
            return
        self._trigger_reload()

    # ── Goals ────────────────────────────────────────────

    def _on_edit_goals(self) -> None:
        """Open the Add Goal dialog (called by + New Goal button)."""
        if not self._result:
            QMessageBox.information(self, "Goals", "No data loaded yet.")
            return
        today = date.today()
        # Exclude archived tasks and auto-archived completed goals
        eligible = [
            t for t in self._result.tasks
            if not t.archived
            and not (
                t.name in self._goals
                and self._goals[t.name].completed_on is not None
                and (today - self._goals[t.name].completed_on).days >= 3
            )
        ]
        dlg = AddGoalDialog(eligible, self._goals, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            task_name, gs = dlg.values()
            existing = self._goals.get(task_name, GoalSpec())
            self._goals[task_name] = GoalSpec(
                hours=gs.hours,
                deadline=gs.deadline,
                completed_on=existing.completed_on,
            )
            try:
                self._store.save_goals(self._goals, self._result.tasks)
            except Exception as e:
                QMessageBox.warning(self, "Failed to save goal", str(e))
            self._apply_goals_to_tasks()
            self._rebuild_goal_rows()

    def _on_edit_single_goal(self, task_name: str) -> None:
        """Open the Edit Goal dialog for a specific task."""
        if not self._result:
            return
        task = next((t for t in self._result.tasks if t.name == task_name), None)
        if not task:
            return
        gs = self._goals.get(task_name, GoalSpec())
        dlg = EditGoalDialog(task, gs, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            new_gs = dlg.values()
            self._goals[task_name] = GoalSpec(
                hours=new_gs.hours,
                deadline=new_gs.deadline,
                completed_on=gs.completed_on,
            )
            try:
                self._store.save_goals(self._goals, self._result.tasks)
            except Exception as e:
                QMessageBox.warning(self, "Failed to save goal", str(e))
            self._apply_goals_to_tasks()
            self._rebuild_goal_rows()

    def _on_cancel_goal(self, task_name: str) -> None:
        """Remove the goal for a task after confirmation."""
        reply = QMessageBox.question(
            self, "Remove Goal",
            f'Remove the goal for "{task_name}"?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self._goals.pop(task_name, None)
        if self._result:
            try:
                self._store.save_goals(self._goals, self._result.tasks)
            except Exception as e:
                QMessageBox.warning(self, "Failed to remove goal", str(e))
            self._apply_goals_to_tasks()
            self._rebuild_goal_rows()

    def _on_archive_goal(self, task_name: str) -> None:
        """Toggle manual archive flag on a goal."""
        gs = self._goals.get(task_name)
        if gs is None:
            return
        self._goals[task_name] = GoalSpec(
            hours=gs.hours,
            deadline=gs.deadline,
            completed_on=gs.completed_on,
            archived=not gs.archived,
        )
        if self._result:
            try:
                self._store.save_goals(self._goals, self._result.tasks)
            except Exception as e:
                QMessageBox.warning(self, "Failed to archive goal", str(e))
            self._apply_goals_to_tasks()
            self._rebuild_goal_rows()

    # ── Helpers ──────────────────────────────────────────

    def _start_update_check(self) -> None:
        if hasattr(self, '_update_thread'):
            return   # already started on first build; don't restart on theme toggle
        from ..version import VERSION
        self._update_thread = QThread()
        self._update_worker = UpdateChecker()
        self._update_worker.moveToThread(self._update_thread)
        self._update_thread.started.connect(self._update_worker.run)
        self._update_worker.update_available.connect(self._on_update_available)
        self._update_worker.update_available.connect(self._update_thread.quit)
        self._update_thread.finished.connect(self._update_thread.deleteLater)
        self._update_thread.start()

    def _on_update_available(self, latest: str) -> None:
        from ..version import VERSION
        self._update_btn.setText(f"⬆ Update available  v{VERSION} → v{latest}")
        self._update_btn.setVisible(True)

    def _open_releases(self) -> None:
        from ..version import GITHUB_REPO
        from PyQt5.QtGui import QDesktopServices
        from PyQt5.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(f"https://github.com/{GITHUB_REPO}/releases/latest"))

    @staticmethod
    def _mk_btn(text: str, slot) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(28)
        btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {MUTED};"
            f" border: 1px solid {BORDER}; border-radius: 6px;"
            f" font-size: 10px; padding: 0 12px; }}"
            f" QPushButton:hover {{ color: {TEXT}; background: {BG3};"
            f" border-color: {BORDER2}; }}"
            f" QPushButton:pressed {{ background: {BG2}; }}"
        )
        btn.clicked.connect(slot)
        return btn
