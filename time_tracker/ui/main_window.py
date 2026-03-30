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
    QFrame, QSplitter, QMessageBox, QTabWidget,
    QDoubleSpinBox, QDialog, QDialogButtonBox,
    QDateEdit, QLineEdit, QComboBox,
)
from PyQt5.QtGui import QColor, QPalette

from ..core import (
    DBStore, ParseResult, RangeStats,
    WeeklyComparison, GoalTracker, InsightEngine, Insight, streak_days,
    GoalSpec,
    date_range, this_week_range, last_week_range,
    this_month_range, last_month_range, last_n_days,
    fmt_dur,
)
from ..core.models import Task, CATEGORY_COLOUR_TAG as _CATEGORY_COLOUR_TAG_IMPORT
from ..charts.panels import (
    StackedAreaChart, WeekdayBarChart, HourHeatmap, WeeklyCompChart,
    CategoryBreakdownChart,
)
from .widgets import (
    MetricCard, InsightStrip, ChartPanel, CollapsibleSection,
    RangeSlider, TaskRow, GoalRow, PresetBar,
    h_line, v_line, label, card_frame, make_chart_panel,
    EditSessionDialog, AddSessionDialog,
)
from .tab_widgets import CategoryTabWidget, TaskTabWidget
from .theme import (
    BG, BG2, BG3, BG4, BORDER, BORDER2,
    TEXT, MUTED, FAINT, ACCENT, SUCCESS, WARNING, DANGER,
    PAD_XS, PAD_SM, PAD_MD, PAD_LG,
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
# Goal dialog  (hours + optional deadline)
# ──────────────────────────────────────────────────────────

class GoalDialog(QDialog):
    def __init__(self, tasks: list[Task],
                 goals: dict[str, GoalSpec], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Goals")
        self.setMinimumWidth(540)
        self.setStyleSheet(
            f"background: {BG}; color: {TEXT};"
            f" QLabel {{ background: transparent; }}"
        )

        root = QVBoxLayout(self)
        root.setSpacing(PAD_SM)

        root.addWidget(label(
            "Set a target hours and optional deadline per task.", MUTED, size=10
        ))
        root.addWidget(h_line())

        # Header row
        hdr = QHBoxLayout()
        for txt, stretch in [("Task", 2), ("Target hours", 1),
                              ("Deadline (optional)", 1), ("Pace needed", 1)]:
            hdr.addWidget(label(txt, FAINT, size=9), stretch)
        root.addLayout(hdr)
        root.addWidget(h_line())

        self._rows: dict[str, tuple[QDoubleSpinBox, QDateEdit, QLabel]] = {}

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {BG}; }}"
        )
        inner = QWidget()
        inner.setStyleSheet(f"background: {BG};")
        form  = QVBoxLayout(inner)
        form.setSpacing(4)

        for t in tasks:
            gs   = goals.get(t.name, GoalSpec())
            row  = QHBoxLayout()

            # Task name
            name_lbl = label(f"● {t.name}", t.colour, size=10)
            row.addWidget(name_lbl, 2)

            # Hours spin
            spin = QDoubleSpinBox()
            spin.setRange(0, 9999)
            spin.setSingleStep(0.5)
            spin.setValue(gs.hours)
            spin.setStyleSheet(
                f"background: {BG3}; color: {TEXT}; border: 1px solid {BORDER};"
                f" border-radius: 5px; padding: 2px 6px; font-size: 10px;"
            )
            row.addWidget(spin, 1)

            # Date picker
            de = QDateEdit()
            de.setCalendarPopup(True)
            de.setDisplayFormat("dd MMM yyyy")
            de.setStyleSheet(
                f"background: {BG3}; color: {TEXT}; border: 1px solid {BORDER};"
                f" border-radius: 5px; padding: 2px 6px; font-size: 10px;"
            )
            if gs.deadline:
                de.setDate(QDate(gs.deadline.year,
                                 gs.deadline.month, gs.deadline.day))
            else:
                de.setDate(QDate.currentDate().addMonths(1))
            de.setSpecialValueText("No deadline")
            row.addWidget(de, 1)

            # Computed pace label
            pace_lbl = QLabel("—")
            pace_lbl.setStyleSheet(
                f"color: {MUTED}; font-size: 10px;"
                f" background: transparent;"
            )
            row.addWidget(pace_lbl, 1)

            def _update_pace(_, _s=spin, _d=de, _l=pace_lbl, _t=t):
                h   = _s.value()
                qd  = _d.date()
                dl  = date(qd.year(), qd.month(), qd.day())
                days_left = (dl - date.today()).days
                done = _t.total_hours
                if h > 0 and done < h and days_left > 0:
                    req = (h - done) / days_left
                    col = SUCCESS if req <= 2 else (WARNING if req <= 4 else DANGER)
                    _l.setText(f"{req:.1f}h/day")
                    _l.setStyleSheet(
                        f"color: {col}; font-size: 10px; background: transparent;"
                    )
                elif h > 0 and done >= h:
                    _l.setText("Done!")
                    _l.setStyleSheet(
                        f"color: {SUCCESS}; font-size: 10px; background: transparent;"
                    )
                else:
                    _l.setText("—")

            spin.valueChanged.connect(_update_pace)
            de.dateChanged.connect(_update_pace)
            _update_pace(None)

            self._rows[t.name] = (spin, de, pace_lbl)

            w = QWidget()
            w.setStyleSheet("background: transparent;")
            w.setLayout(row)
            form.addWidget(w)

        form.addStretch()
        inner.setLayout(form)
        scroll.setWidget(inner)
        root.addWidget(scroll, stretch=1)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.setStyleSheet(f"color: {TEXT};")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    def get_goals(self) -> dict[str, GoalSpec]:
        result: dict[str, GoalSpec] = {}
        for name, (spin, de, _) in self._rows.items():
            qd = de.date()
            dl = date(qd.year(), qd.month(), qd.day())
            result[name] = GoalSpec(
                hours    = spin.value(),
                deadline = dl if spin.value() > 0 else None,
            )
        return result


# ──────────────────────────────────────────────────────────
# New task dialog
# ──────────────────────────────────────────────────────────

# Middle shade for each TAG_PALETTES entry, used as swatch colour.
_PALETTE_SWATCHES: dict[str, str] = {
    "blue":   "#185FA5",
    "red":    "#DC3912",
    "yellow": "#FF9900",
    "green":  "#639922",
    "purple": "#7F77DD",
    "brown":  "#8B6C42",
    "white":  "#AAAAAA",
    "black":  "#444444",
}

_COMBO_CSS = (
    f"QComboBox {{ background: {BG3}; color: {TEXT};"
    f" border: 1px solid {BORDER}; border-radius: 5px;"
    f" padding: 4px 10px; font-size: 11px; }}"
    f" QComboBox::drop-down {{ border: none; }}"
    f" QComboBox QAbstractItemView {{ background: {BG2};"
    f" color: {TEXT}; selection-background-color: {ACCENT}; }}"
)

_INPUT_CSS = (
    f"QLineEdit {{ background: {BG3}; color: {TEXT};"
    f" border: 1px solid {BORDER}; border-radius: 5px;"
    f" padding: 4px 10px; font-size: 11px; }}"
    f" QLineEdit:focus {{ border-color: {ACCENT}; }}"
)


def _swatch_for_tag(colour_tag: str) -> str:
    """Return the representative hex for a TAG_PALETTES key."""
    from ..core.models import TAG_PALETTES
    palette = TAG_PALETTES.get(colour_tag, TAG_PALETTES["none"])
    return palette[1] if len(palette) > 1 else palette[0]


class NewCategoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Category")
        self.setFixedWidth(340)
        self.setStyleSheet(
            f"background: {BG}; color: {TEXT};"
            f" QLabel {{ background: transparent; }}"
        )

        root = QVBoxLayout(self)
        root.setSpacing(PAD_SM)

        root.addWidget(label("Category name", MUTED, size=10))
        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. Side Projects")
        self._name.setStyleSheet(_INPUT_CSS)
        root.addWidget(self._name)

        root.addWidget(label("Colour", MUTED, size=10))
        self._colour = QComboBox()
        self._colour.setStyleSheet(_COMBO_CSS)
        for tag in _PALETTE_SWATCHES:
            self._colour.addItem(f"● {tag}", userData=tag)
            idx = self._colour.count() - 1
            self._colour.setItemData(idx, QColor(_PALETTE_SWATCHES[tag]),
                                     Qt.ForegroundRole)
        root.addStretch()

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.setStyleSheet(f"color: {TEXT};")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    def _on_accept(self) -> None:
        name = self._name.text().strip()
        if not name:
            self._name.setStyleSheet(
                _INPUT_CSS + f" QLineEdit {{ border-color: {DANGER}; }}"
            )
            return
        # Enforce capital first letter
        if name[0].islower():
            name = name[0].upper() + name[1:]
            self._name.setText(name)
        self.accept()

    def values(self) -> tuple[str, str]:
        """Returns (category_name, colour_tag)."""
        return self._name.text().strip(), self._colour.currentData()


class NewTaskDialog(QDialog):
    def __init__(self, categories: list[tuple[str, str]], parent=None):
        """categories: list of (name, colour_tag) from the DB."""
        super().__init__(parent)
        self.setWindowTitle("New Task")
        self.setFixedWidth(380)
        self.setStyleSheet(
            f"background: {BG}; color: {TEXT};"
            f" QLabel {{ background: transparent; }}"
        )

        root = QVBoxLayout(self)
        root.setSpacing(PAD_SM)

        root.addWidget(label("Task name", MUTED, size=10))
        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. Deep work")
        self._name.setStyleSheet(_INPUT_CSS)
        root.addWidget(self._name)

        root.addWidget(label("Category", MUTED, size=10))
        self._category = QComboBox()
        self._category.setStyleSheet(_COMBO_CSS)
        for cat_name, colour_tag in categories:
            swatch = _swatch_for_tag(colour_tag)
            self._category.addItem(f"● {cat_name}", userData=cat_name)
            idx = self._category.count() - 1
            self._category.setItemData(idx, QColor(swatch), Qt.ForegroundRole)
        root.addWidget(self._category)

        root.addStretch()

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.setStyleSheet(f"color: {TEXT};")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    def _on_accept(self) -> None:
        if not self._name.text().strip():
            self._name.setStyleSheet(
                _INPUT_CSS + f" QLineEdit {{ border-color: {DANGER}; }}"
            )
            return
        self.accept()

    def values(self) -> tuple[str, str]:
        """Returns (task_name, category_name)."""
        return self._name.text().strip(), self._category.currentData()


# ──────────────────────────────────────────────────────────
# Rename / Move task dialogs
# ──────────────────────────────────────────────────────────

class RenameTaskDialog(QDialog):
    def __init__(self, current_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Rename Task")
        self.setFixedWidth(340)
        self.setStyleSheet(
            f"background: {BG}; color: {TEXT};"
            f" QLabel {{ background: transparent; }}"
        )
        root = QVBoxLayout(self)
        root.setSpacing(PAD_SM)
        root.addWidget(label("New name", MUTED, size=10))
        self._name = QLineEdit(current_name)
        self._name.setStyleSheet(_INPUT_CSS)
        self._name.selectAll()
        root.addWidget(self._name)
        root.addStretch()
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.setStyleSheet(f"color: {TEXT};")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    def _on_accept(self) -> None:
        if not self._name.text().strip():
            self._name.setStyleSheet(
                _INPUT_CSS + f" QLineEdit {{ border-color: {DANGER}; }}")
            return
        self.accept()

    def value(self) -> str:
        return self._name.text().strip()


class MoveTaskDialog(QDialog):
    def __init__(self, categories: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Move to Category")
        self.setFixedWidth(340)
        self.setStyleSheet(
            f"background: {BG}; color: {TEXT};"
            f" QLabel {{ background: transparent; }}"
        )
        root = QVBoxLayout(self)
        root.setSpacing(PAD_SM)
        root.addWidget(label("Select category", MUTED, size=10))
        self._category = QComboBox()
        self._category.setStyleSheet(_COMBO_CSS)
        for cat_name, colour_tag in categories:
            swatch = _swatch_for_tag(colour_tag)
            self._category.addItem(f"● {cat_name}", userData=cat_name)
            idx = self._category.count() - 1
            from PyQt5.QtCore import Qt as _Qt
            self._category.setItemData(idx, QColor(swatch), _Qt.ForegroundRole)
        root.addWidget(self._category)
        root.addStretch()
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.setStyleSheet(f"color: {TEXT};")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    def value(self) -> str:
        return self._category.currentData()


# ──────────────────────────────────────────────────────────
# Main window
# ──────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Time Tracker")
        self.resize(1600, 960)

        self._store      = DBStore()
        self._result:      Optional[ParseResult]          = None
        self._goals:       dict[str, GoalSpec]            = {}
        self._categories:  list[tuple[str, str]]          = []
        self._task_rows:   dict[str, TaskRow]             = {}
        self._category_tabs: dict[str, CategoryTabWidget] = {}
        self._task_tabs:     dict[str, TaskTabWidget]     = {}

        self._date_low  = 0
        self._date_high = 0
        self._all_dates: list[date] = []

        self._thread: Optional[QThread]      = None
        self._worker: Optional[ReloadWorker] = None

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
        bar.setFixedHeight(46)
        bar.setStyleSheet(
            f"QFrame {{ background: {BG2}; border-bottom: 1px solid {BORDER}; }}"
        )
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(PAD_LG, 0, PAD_LG, 0)
        lay.setSpacing(10)

        logo = QLabel("Time Tracker")
        logo.setStyleSheet(
            f"color: {TEXT}; font-size: 13px; font-weight: 700;"
            f" letter-spacing: 0.5px; background: transparent; border: none;"
        )
        lay.addWidget(logo)
        lay.addWidget(v_line())
        lay.addWidget(label("PostgreSQL", MUTED, size=10))
        lay.addStretch()

        for txt, slot in [("Reload",   self._trigger_reload),
                          ("Goals…",  self._on_edit_goals),
                          ("☀ Light", self._on_toggle_theme)]:
            btn = self._mk_btn(txt, slot)
            if txt.startswith("☀"):
                self._theme_btn = btn
            lay.addWidget(btn)

        self._updated_lbl = label("Loading…", FAINT, size=9)
        lay.addWidget(self._updated_lbl)

        root.addWidget(bar)

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

        # ── Left panel (fixed 340 px) ─────────────────────
        left = QWidget()
        left.setMinimumWidth(220)
        left.setMaximumWidth(560)
        left.setStyleSheet(f"background: {BG};")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(PAD_MD, PAD_MD, PAD_SM, PAD_MD)
        ll.setSpacing(PAD_SM)

        # Date range card
        rc = card_frame()
        rl = QVBoxLayout(rc)
        rl.setContentsMargins(PAD_SM, PAD_SM, PAD_SM, PAD_SM)
        rl.setSpacing(5)
        self._preset_bar = PresetBar()
        self._preset_bar.preset_selected.connect(self._on_preset)
        rl.addWidget(self._preset_bar)
        self._range_slider = RangeSlider()
        self._range_slider.range_changed.connect(self._on_range_changed)
        rl.addWidget(self._range_slider)
        self._range_lbl = label("", MUTED, size=9)
        self._range_lbl.setAlignment(Qt.AlignCenter)
        rl.addWidget(self._range_lbl)
        ll.addWidget(rc)

        # Task list header: label + "+ Category" button
        tasks_hdr = QHBoxLayout()
        tasks_hdr.setContentsMargins(0, 0, 0, 0)
        tasks_hdr.addWidget(label("Tasks", TEXT, bold=True, size=11))
        tasks_hdr.addStretch()
        add_cat_btn = QPushButton("+ Category")
        add_cat_btn.setFixedHeight(22)
        add_cat_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {MUTED};"
            f" border: 1px solid {BORDER}; border-radius: 4px;"
            f" font-size: 10px; padding: 0 8px; }}"
            f" QPushButton:hover {{ color: {TEXT}; background: {BG3};"
            f" border-color: {BORDER2}; }}"
        )
        add_cat_btn.clicked.connect(self._on_new_category)
        tasks_hdr.addWidget(add_cat_btn)
        ll.addLayout(tasks_hdr)

        task_scroll = QScrollArea()
        task_scroll.setWidgetResizable(True)
        task_scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {BG}; }}"
            f"QScrollBar:vertical {{ background: {BG2}; width: 4px; }}"
            f"QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 2px; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
        )
        self._task_container = QWidget()
        self._task_container.setStyleSheet(f"background: {BG};")
        self._task_layout = QVBoxLayout(self._task_container)
        self._task_layout.setContentsMargins(0, 0, 0, 0)
        self._task_layout.setSpacing(0)
        self._task_layout.addStretch()
        task_scroll.setWidget(self._task_container)
        ll.addWidget(task_scroll, stretch=1)

        # Goal progress section
        self._goals_section = CollapsibleSection("Goal Progress")
        self._goals_inner   = QWidget()
        self._goals_inner.setStyleSheet("background: transparent;")
        self._goals_inner_layout = QVBoxLayout(self._goals_inner)
        self._goals_inner_layout.setContentsMargins(0, 0, 0, 0)
        self._goals_inner_layout.setSpacing(2)
        self._goals_section.add_widget(self._goals_inner)
        ll.addWidget(self._goals_section)

        splitter.addWidget(left)

        # ── Right panel: tab widget ───────────────────────
        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(True)
        self._tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: none; background: {BG}; }}"
            f"QTabWidget::tab-bar {{ left: 0px; }}"
            f"QTabBar::tab {{ background: {BG2}; color: {MUTED};"
            f" border: 1px solid {BORDER}; border-bottom: none;"
            f" padding: 5px 14px; font-size: 10px;"
            f" border-top-left-radius: 4px; border-top-right-radius: 4px; }}"
            f"QTabBar::tab:selected {{ background: {BG3}; color: {TEXT}; }}"
            f"QTabBar::tab:hover {{ color: {TEXT}; background: {BG3}; }}"
            f"QTabBar::close-button {{ image: none; }}"
        )
        self._tabs.tabCloseRequested.connect(self._on_tab_close_requested)
        overview = self._build_overview_tab()
        self._tabs.addTab(overview, "Overview")
        # Prevent the Overview tab from being closable
        self._tabs.tabBar().setTabButton(0, self._tabs.tabBar().RightSide, None)

        splitter.addWidget(self._tabs)
        splitter.setSizes([340, 1260])
        root.addWidget(splitter, stretch=1)

    def _build_overview_tab(self) -> QWidget:
        """Build and return the overview scroll area (former right panel)."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {BG}; }}"
            f"QScrollBar:vertical {{ background: {BG2}; width: 4px; }}"
            f"QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 2px; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
        )
        right_inner = QWidget()
        right_inner.setStyleSheet(f"background: {BG};")
        cl = QVBoxLayout(right_inner)
        cl.setContentsMargins(PAD_SM, PAD_MD, PAD_MD, PAD_MD)
        cl.setSpacing(PAD_SM)

        # Metric cards (5 across)
        mc_row = QHBoxLayout()
        mc_row.setSpacing(PAD_SM)
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

        # Daily stacked area (full width)
        self._stacked_chart = StackedAreaChart()
        cl.addWidget(make_chart_panel("Daily activity", self._stacked_chart))

        # Weekday + Weekly comparison side by side
        row2 = QHBoxLayout()
        row2.setSpacing(PAD_SM)
        self._wd_chart = WeekdayBarChart()
        row2.addWidget(make_chart_panel("Avg by weekday", self._wd_chart))
        self._wc_chart = WeeklyCompChart()
        row2.addWidget(make_chart_panel("This week vs last week", self._wc_chart))
        cl.addLayout(row2)

        # Hour heatmap (full width)
        self._hm_chart = HourHeatmap()
        cl.addWidget(make_chart_panel("Hour-of-day heatmap", self._hm_chart))

        # Category breakdown (full width)
        self._cat_breakdown = CategoryBreakdownChart()
        cl.addWidget(make_chart_panel("Category breakdown", self._cat_breakdown))

        cl.addStretch()
        scroll.setWidget(right_inner)
        return scroll

    # ── Data loading ─────────────────────────────────────

    def _trigger_reload(self) -> None:
        if self._thread and self._thread.isRunning():
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

    def _on_reload_done(self, result: ParseResult) -> None:
        self._result = result
        self._apply_goals_to_tasks()

        all_dates: set[date] = set()
        for t in result.tasks:
            for s in t.sessions:
                all_dates.add(s.date)
        self._all_dates = sorted(all_dates)

        if self._all_dates:
            self._range_slider.set_count(len(self._all_dates))
            self._date_low  = 0
            self._date_high = len(self._all_dates) - 1

        ts = result.parsed_at.strftime("%H:%M:%S")
        self._updated_lbl.setText(f"Updated {ts}  ·  {len(result.tasks)} tasks")

        self._rebuild_task_rows()
        self._rebuild_category_tabs()
        self._refresh_all()

    def _on_reload_error(self, msg: str) -> None:
        self._updated_lbl.setText("Error — see console")
        QMessageBox.critical(self, "Failed to load data", msg)

    def _apply_goals_to_tasks(self) -> None:
        if not self._result:
            return
        for t in self._result.tasks:
            gs = self._goals.get(t.name, GoalSpec())
            t.goal_hours    = gs.hours
            t.goal_deadline = gs.deadline

    # ── Task rows ────────────────────────────────────────

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
        for t in sorted(self._result.tasks,
                        key=lambda t: t.total_seconds, reverse=True):
            elapsed = (t.open_session.duration.total_seconds()
                       if t.open_session else 0)
            cat_colour = _swatch_for_tag(
                _CATEGORY_COLOUR_TAG_IMPORT.get(t.tag, "none")
            )
            row = TaskRow(
                task_name        = t.name,
                colour           = t.colour,
                total_sec        = t.total_seconds,
                max_sec          = max_sec,
                n_sessions       = t.session_count,
                clocked_in       = t.is_clocked_in,
                elapsed_sec      = elapsed,
                category_colour  = cat_colour,
            )
            row.clock_in_requested.connect(self._on_clock_in)
            row.clock_out_requested.connect(self._on_clock_out)
            row.rename_requested.connect(self._on_rename_task)
            row.move_requested.connect(self._on_move_task)
            row.delete_requested.connect(self._on_delete_task)
            row.clicked.connect(self._open_task_tab)
            self._task_layout.insertWidget(self._task_layout.count() - 1, row)
            self._task_rows[t.name] = row

        # "+ New Task" button at the bottom of the list
        add_btn = QPushButton("+ New Task")
        add_btn.setFixedHeight(28)
        add_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {FAINT};"
            f" border: 1px dashed {BORDER}; border-radius: 5px;"
            f" font-size: 10px; margin: 4px 0px; }}"
            f" QPushButton:hover {{ color: {MUTED}; border-color: {BORDER2}; }}"
        )
        add_btn.clicked.connect(self._on_new_task)
        self._task_layout.insertWidget(self._task_layout.count() - 1, add_btn)

        self._rebuild_goal_rows()

    def _rebuild_goal_rows(self) -> None:
        while self._goals_inner_layout.count():
            item = self._goals_inner_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._result:
            return

        tasks_with_goals = [t for t in self._result.tasks
                            if t.goal_hours > 0]
        if not tasks_with_goals:
            self._goals_inner_layout.addWidget(
                label("No goals set. Click 'Goals…' above.", FAINT, size=9)
            )
            return

        stats   = self._current_stats()
        tracker = GoalTracker(self._result.tasks, stats) if stats else None

        for t in tasks_with_goals:
            row = GoalRow(t.name, t.colour)
            daily_avg = tracker.daily_avg_hours(t.name) if tracker else 0
            row.update(
                progress      = t.goal_progress(),
                goal_hours    = t.goal_hours,
                daily_avg     = daily_avg,
                req_hpd       = t.required_daily_hours(),
                deadline_days = t.deadline_days_left(),
            )
            self._goals_inner_layout.addWidget(row)

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

        # Refresh category tabs
        for tab in self._category_tabs.values():
            tab.refresh(start, end, self._result.tasks, self._goals)

        # Refresh task tabs
        for task_name, tab in list(self._task_tabs.items()):
            task = self._result.task_by_name(task_name)
            if task:
                tab.update_task(task)
                tab.refresh(start, end)
            else:
                # Task was deleted — remove its tab
                for i in range(self._tabs.count()):
                    if self._tabs.widget(i) is tab:
                        self._tabs.removeTab(i)
                        break
                self._task_tabs.pop(task_name, None)
                tab.deleteLater()

    def _current_stats(self) -> Optional[RangeStats]:
        if not self._result or not self._all_dates:
            return None
        s = self._all_dates[self._date_low]
        e = self._all_dates[self._date_high]
        return RangeStats(self._result.tasks, s, e)

    def _update_metric_cards(self, stats: RangeStats) -> None:
        from datetime import date as _date
        today = _date.today()
        today_sec = sum(
            s.duration_seconds
            for t in (self._result.tasks if self._result else [])
            for s in t.sessions
            if s.start.date() == today
        )
        self._mc_today.update_value(
            fmt_dur(today_sec, short=True),
            f"{today_sec / 3600:.1f}h so far",
        )

        self._mc_total.update_value(
            fmt_dur(stats.grand_total_seconds, short=True),
            f"{stats.grand_total_seconds / 3600:.1f}h total",
        )

        n_sess = sum(
            len(t.sessions_in_range(stats.start, stats.end))
            for t in stats.tasks
        )
        self._mc_sessions.update_value(str(n_sess),
                                       f"over {stats.n_days} days")

        closed = [s for t in stats.tasks
                  for s in t.sessions_in_range(stats.start, stats.end)
                  if not s.is_open]
        if closed:
            avg = sum(s.duration_seconds for s in closed) / len(closed)
            self._mc_avg.update_value(fmt_dur(avg, short=True))
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
        for t in self._result.tasks:
            if t.is_clocked_in and t.name in self._task_rows:
                self._task_rows[t.name].update_elapsed(
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

    # ── Tab management ───────────────────────────────────

    def _rebuild_category_tabs(self) -> None:
        """Recreate one tab per category found in current tasks."""
        # Remove all non-overview tabs
        while self._tabs.count() > 1:
            w = self._tabs.widget(1)
            self._tabs.removeTab(1)
            if w:
                w.deleteLater()
        self._category_tabs.clear()
        # Clear task tabs too (they'll be reopened on demand)
        self._task_tabs.clear()

        if not self._result:
            return

        seen: set[str] = set()
        for t in self._result.tasks:
            if t.tag and t.tag not in seen:
                seen.add(t.tag)
                tab = CategoryTabWidget(t.tag, parent=self)
                display = t.tag if len(t.tag) <= 14 else t.tag[:13] + "…"
                self._tabs.addTab(tab, display)
                # Prevent category tabs from being closable
                idx = self._tabs.count() - 1
                self._tabs.tabBar().setTabButton(
                    idx, self._tabs.tabBar().RightSide, None)
                self._category_tabs[t.tag] = tab

    def _open_task_tab(self, task_name: str) -> None:
        """Open or focus the task detail tab for the given task."""
        if task_name in self._task_tabs:
            tab = self._task_tabs[task_name]
            for i in range(self._tabs.count()):
                if self._tabs.widget(i) is tab:
                    self._tabs.setCurrentIndex(i)
                    return
        if not self._result:
            return
        task = self._result.task_by_name(task_name)
        if not task:
            return
        tab = TaskTabWidget(task, parent=self)
        display = task_name if len(task_name) <= 14 else task_name[:13] + "…"
        self._tabs.addTab(tab, display)
        self._task_tabs[task_name] = tab
        self._tabs.setCurrentWidget(tab)

        # Refresh immediately with current range
        if self._all_dates:
            tab.refresh(
                self._all_dates[self._date_low],
                self._all_dates[self._date_high],
            )

    def _on_tab_close_requested(self, index: int) -> None:
        """Only task tabs are closable."""
        w = self._tabs.widget(index)
        if isinstance(w, TaskTabWidget):
            self._task_tabs.pop(w.task_name, None)
            self._tabs.removeTab(index)
            w.deleteLater()

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
        # Close any open task tab for this task
        if task_name in self._task_tabs:
            tab = self._task_tabs.pop(task_name)
            for i in range(self._tabs.count()):
                if self._tabs.widget(i) is tab:
                    self._tabs.removeTab(i)
                    break
            tab.deleteLater()
        self._trigger_reload()

    # ── Theme toggle ─────────────────────────────────────────

    def _on_toggle_theme(self) -> None:
        from ..ui import theme as _theme
        # Switch palette module-level vars and propagate to consumer modules
        if _theme.IS_DARK:
            _theme.set_light_mode()
            self._theme_btn.setText("☾ Dark")
        else:
            _theme.set_dark_mode()
            self._theme_btn.setText("☀ Light")
        # Rebuild UI with new colours; preserve data state
        self._category_tabs = {}
        self._task_tabs     = {}
        self._task_rows     = {}
        self._build_ui()
        self._apply_palette()
        if self._result:
            self._on_reload_done(self._result)

    # ── Session management ───────────────────────────────────

    def _on_add_session(self, task_id: int) -> None:
        dlg = AddSessionDialog(parent=self)
        if dlg.exec_() != QDialog.Accepted:
            return
        start_dt, end_dt = dlg.values()
        try:
            self._store.add_session(task_id, start_dt, end_dt)
        except Exception as e:
            QMessageBox.warning(self, "Failed to add session", str(e))
            return
        self._trigger_reload()

    def _on_edit_session(self, session_id: int, start, end) -> None:
        dlg = EditSessionDialog(start, end, parent=self)
        if dlg.exec_() != QDialog.Accepted:
            return
        new_start, new_end = dlg.values()
        try:
            self._store.update_session(session_id, new_start, new_end)
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
        if not self._result:
            QMessageBox.information(self, "Goals", "No data loaded yet.")
            return
        dlg = GoalDialog(self._result.tasks, self._goals, parent=self)
        dlg.resize(600, 500)
        if dlg.exec_() == QDialog.Accepted:
            self._goals = dlg.get_goals()
            try:
                self._store.save_goals(self._goals, self._result.tasks)
            except Exception as e:
                QMessageBox.warning(self, "Failed to save goals", str(e))
            self._apply_goals_to_tasks()
            self._rebuild_goal_rows()

    # ── Helpers ──────────────────────────────────────────

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
