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
    QDateEdit, QLineEdit, QComboBox, QMenu,
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
from ..core.models import Task, CATEGORY_COLOUR_TAG as _CATEGORY_COLOUR_TAG_IMPORT
from ..charts.panels import (
    StackedAreaChart, WeekdayBarChart, HourHeatmap, WeeklyCompChart,
    CategoryBreakdownChart,
)
from .widgets import (
    MetricCard, InsightStrip, ChartPanel,
    RangeSlider, TaskRow, PresetBar,
    h_line, v_line, label, card_frame, make_chart_panel,
    EditSessionDialog, AddSessionDialog,
)
from .tab_widgets import CategoryTabWidget, TaskTabWidget
from .calendar_widget import CalendarWidget
from .goals_tab import GoalsTab
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
# Goal dialogs  (add / edit a single goal)
# ──────────────────────────────────────────────────────────

_SPIN_CSS = (
    f"QDoubleSpinBox {{ background: {BG3}; color: {TEXT};"
    f" border: 1px solid {BORDER}; border-radius: 5px;"
    f" padding: 4px 10px; font-size: 11px; }}"
    f" QDoubleSpinBox:focus {{ border-color: {ACCENT}; }}"
)
_DATE_CSS = (
    f"QDateEdit {{ background: {BG3}; color: {TEXT};"
    f" border: 1px solid {BORDER}; border-radius: 5px;"
    f" padding: 4px 10px; font-size: 11px; }}"
    f" QDateEdit:focus {{ border-color: {ACCENT}; }}"
)


def _make_goal_form(root: QVBoxLayout, task_name: str,
                    task_colour: str, task_total_hours: float,
                    gs: GoalSpec) -> tuple[QDoubleSpinBox, QDateEdit, QLabel, QLabel]:
    """Shared form body for add/edit goal dialogs. Returns (spin, date_edit, pace_lbl, no_dl_lbl)."""

    root.addWidget(label("Target hours", MUTED, size=10))
    spin = QDoubleSpinBox()
    spin.setRange(0.5, 9999)
    spin.setSingleStep(0.5)
    spin.setValue(gs.hours if gs.hours > 0 else 10.0)
    spin.setStyleSheet(_SPIN_CSS)
    root.addWidget(spin)

    root.addWidget(label("Deadline (optional)", MUTED, size=10))

    # "No deadline" checkbox + date picker
    no_dl_row = QHBoxLayout()
    no_dl_row.setSpacing(PAD_SM)
    no_dl_chk = QPushButton("No deadline")
    no_dl_chk.setCheckable(True)
    no_dl_chk.setChecked(gs.deadline is None)
    no_dl_chk.setFixedHeight(30)
    no_dl_chk.setStyleSheet(
        f"QPushButton {{ background: {BG3}; color: {MUTED}; border: 1px solid {BORDER};"
        f" border-radius: 5px; font-size: 10px; padding: 0 10px; }}"
        f" QPushButton:checked {{ background: {ACCENT}; color: #fff; border-color: {ACCENT}; }}"
    )
    no_dl_row.addWidget(no_dl_chk)
    de = QDateEdit()
    de.setCalendarPopup(True)
    de.setDisplayFormat("dd MMM yyyy")
    de.setStyleSheet(_DATE_CSS)
    de.setEnabled(gs.deadline is not None)
    if gs.deadline:
        de.setDate(QDate(gs.deadline.year, gs.deadline.month, gs.deadline.day))
    else:
        de.setDate(QDate.currentDate().addMonths(1))
    no_dl_row.addWidget(de, stretch=1)
    root.addLayout(no_dl_row)

    no_dl_chk.toggled.connect(lambda checked: de.setEnabled(not checked))

    # Live pace label
    pace_lbl = QLabel("—")
    pace_lbl.setStyleSheet(f"color: {MUTED}; font-size: 11px; background: transparent;")
    root.addWidget(pace_lbl)

    def _update_pace():
        h        = spin.value()
        done     = task_total_hours
        if no_dl_chk.isChecked():
            if done >= h:
                pace_lbl.setText("Goal already reached!")
                pace_lbl.setStyleSheet(f"color: {SUCCESS}; font-size: 11px; background: transparent;")
            else:
                pace_lbl.setText(f"{h - done:.1f}h remaining · no deadline")
                pace_lbl.setStyleSheet(f"color: {MUTED}; font-size: 11px; background: transparent;")
            return
        qd        = de.date()
        dl        = date(qd.year(), qd.month(), qd.day())
        days_left = (dl - date.today()).days
        if done >= h:
            pace_lbl.setText("Goal already reached!")
            pace_lbl.setStyleSheet(f"color: {SUCCESS}; font-size: 11px; background: transparent;")
        elif days_left <= 0:
            pace_lbl.setText("Deadline has passed!")
            pace_lbl.setStyleSheet(f"color: {DANGER}; font-size: 11px; background: transparent;")
        else:
            req = (h - done) / days_left
            col = SUCCESS if req <= 2 else (WARNING if req <= 4 else DANGER)
            pace_lbl.setText(f"{req:.2f} h/day needed · {days_left}d left")
            pace_lbl.setStyleSheet(f"color: {col}; font-size: 11px; background: transparent;")

    spin.valueChanged.connect(lambda _: _update_pace())
    de.dateChanged.connect(lambda _: _update_pace())
    no_dl_chk.toggled.connect(lambda _: _update_pace())
    _update_pace()

    return spin, de, pace_lbl, no_dl_chk


class AddGoalDialog(QDialog):
    """Pick a task and set hours + optional deadline."""

    def __init__(self, tasks: list[Task], goals: dict[str, GoalSpec], parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Goal")
        self.setFixedWidth(380)
        self.setStyleSheet(
            f"background: {BG}; color: {TEXT};"
            f" QLabel {{ background: transparent; }}"
        )
        self._tasks = tasks
        self._spin: Optional[QDoubleSpinBox] = None
        self._de:   Optional[QDateEdit]      = None
        self._no_dl: Optional[QPushButton]   = None

        root = QVBoxLayout(self)
        root.setSpacing(PAD_SM)

        root.addWidget(label("Task", MUTED, size=10))
        self._task_combo = QComboBox()
        self._task_combo.setStyleSheet(_COMBO_CSS)
        for t in tasks:
            self._task_combo.addItem(f"● {t.name}", userData=t.name)
            idx = self._task_combo.count() - 1
            self._task_combo.setItemData(idx, QColor(t.colour), Qt.ForegroundRole)
        root.addWidget(self._task_combo)

        root.addWidget(h_line())

        self._form_slot = QVBoxLayout()
        self._form_slot.setContentsMargins(0, 0, 0, 0)
        self._form_slot.setSpacing(0)
        self._form_container: Optional[QWidget] = None
        root.addLayout(self._form_slot)

        root.addStretch()

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.setStyleSheet(f"color: {TEXT};")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        self._goals = goals
        self._task_combo.currentIndexChanged.connect(self._rebuild_form)
        self._rebuild_form()

    def _rebuild_form(self) -> None:
        # Destroy the old container entirely — avoids layout-item leak
        if self._form_container is not None:
            self._form_slot.removeWidget(self._form_container)
            self._form_container.deleteLater()
            self._form_container = None
            self._spin = self._de = self._no_dl = None

        task_name = self._task_combo.currentData()
        t = next((x for x in self._tasks if x.name == task_name), None)
        if not t:
            return

        self._form_container = QWidget()
        self._form_container.setStyleSheet("background: transparent;")
        form_lay = QVBoxLayout(self._form_container)
        form_lay.setContentsMargins(0, 0, 0, 0)
        form_lay.setSpacing(PAD_SM)
        self._form_slot.addWidget(self._form_container)

        gs = self._goals.get(t.name, GoalSpec())
        self._spin, self._de, _, self._no_dl = _make_goal_form(
            form_lay, t.name, t.colour, t.total_hours, gs
        )

    def _on_accept(self) -> None:
        if self._spin is None:
            return
        self.accept()

    def values(self) -> tuple[str, GoalSpec]:
        task_name = self._task_combo.currentData()
        if self._no_dl.isChecked():
            dl = None
        else:
            qd = self._de.date()
            dl = date(qd.year(), qd.month(), qd.day())
        return task_name, GoalSpec(hours=self._spin.value(), deadline=dl)


class EditGoalDialog(QDialog):
    """Edit hours + deadline for a specific task goal."""

    def __init__(self, task: Task, gs: GoalSpec, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Goal — {task.name}")
        self.setFixedWidth(380)
        self.setStyleSheet(
            f"background: {BG}; color: {TEXT};"
            f" QLabel {{ background: transparent; }}"
        )

        root = QVBoxLayout(self)
        root.setSpacing(PAD_SM)

        self._spin, self._de, _, self._no_dl = _make_goal_form(
            root, task.name, task.colour, task.total_hours, gs
        )

        root.addStretch()

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.setStyleSheet(f"color: {TEXT};")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    def values(self) -> GoalSpec:
        if self._no_dl.isChecked():
            dl = None
        else:
            qd = self._de.date()
            dl = date(qd.year(), qd.month(), qd.day())
        return GoalSpec(hours=self._spin.value(), deadline=dl)


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


def _goal_is_archived(gs: GoalSpec, today: date) -> bool:
    """A goal is archived if manually archived OR completed 3+ days ago."""
    if gs.archived:
        return True
    if gs.completed_on is not None and (today - gs.completed_on).days >= 3:
        return True
    return False


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


class RenameCategoryDialog(QDialog):
    def __init__(self, categories: list[tuple[str, str]], parent=None):
        """categories: list of (name, colour_tag) from the DB."""
        super().__init__(parent)
        self.setWindowTitle("Rename Category")
        self.setFixedWidth(340)
        self.setStyleSheet(
            f"background: {BG}; color: {TEXT};"
            f" QLabel {{ background: transparent; }}"
        )

        root = QVBoxLayout(self)
        root.setSpacing(PAD_SM)

        root.addWidget(label("Category to rename", MUTED, size=10))
        self._category = QComboBox()
        self._category.setStyleSheet(_COMBO_CSS)
        for cat_name, colour_tag in categories:
            swatch = _swatch_for_tag(colour_tag)
            self._category.addItem(f"● {cat_name}", userData=cat_name)
            idx = self._category.count() - 1
            self._category.setItemData(idx, QColor(swatch), Qt.ForegroundRole)
        root.addWidget(self._category)

        root.addWidget(label("New name", MUTED, size=10))
        self._name = QLineEdit()
        self._name.setStyleSheet(_INPUT_CSS)
        self._name.setPlaceholderText("New category name")
        root.addWidget(self._name)
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
        if name[0].islower():
            name = name[0].upper() + name[1:]
            self._name.setText(name)
        self.accept()

    def values(self) -> tuple[str, str]:
        """Returns (old_category_name, new_category_name)."""
        return self._category.currentData(), self._name.text().strip()


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
        self._task_rows:   dict[str, TaskRow]             = {}
        self._category_tabs: dict[str, CategoryTabWidget] = {}
        self._task_tabs:     dict[str, TaskTabWidget]     = {}
        self._cal_tab:       Optional[CalendarWidget]     = None
        self._goals_tab:     Optional[GoalsTab]           = None

        self._date_low  = 0
        self._date_high = 0
        self._all_dates: list[date] = []
        self._show_archived = False

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
        lay.addStretch()

        self._update_btn = QPushButton("⬆ Update available")
        self._update_btn.setVisible(False)
        self._update_btn.setStyleSheet(
            f"QPushButton {{ background: {SUCCESS}; color: #fff;"
            f" border: none; border-radius: 5px; padding: 4px 10px;"
            f" font-size: 11px; font-weight: 600; }}"
            f"QPushButton:hover {{ background: #2ea85a; }}"
        )
        self._update_btn.clicked.connect(self._open_releases)
        lay.addWidget(self._update_btn)

        for txt, slot in [("Reload",   self._trigger_reload),
                          ("☀ Light", self._on_toggle_theme)]:
            btn = self._mk_btn(txt, slot)
            if txt.startswith("☀"):
                self._theme_btn = btn
            lay.addWidget(btn)

        self._updated_lbl = label("Loading…", FAINT, size=9)
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

        # ── Left panel (fixed 340 px) ─────────────────────
        left = QWidget()
        left.setMinimumWidth(280)
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

        # Task list header: label + "Archived" toggle + "+ Category" button
        tasks_hdr = QHBoxLayout()
        tasks_hdr.setContentsMargins(0, 0, 0, 0)
        tasks_hdr.addWidget(label("Tasks", TEXT, bold=True, size=11))
        tasks_hdr.addStretch()
        self._archived_btn = QPushButton("Archived")
        self._archived_btn.setFixedHeight(22)
        self._archived_btn.setCheckable(True)
        self._archived_btn.setChecked(self._show_archived)
        self._archived_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {MUTED};"
            f" border: 1px solid {BORDER}; border-radius: 4px;"
            f" font-size: 10px; padding: 0 8px; }}"
            f" QPushButton:hover {{ color: {TEXT}; background: {BG3};"
            f" border-color: {BORDER2}; }}"
            f" QPushButton:checked {{ color: {TEXT}; background: {BG3};"
            f" border-color: {BORDER2}; }}"
        )
        self._archived_btn.toggled.connect(self._on_toggle_archived)
        tasks_hdr.addWidget(self._archived_btn)
        add_cat_btn = QPushButton("+ Category")
        add_cat_btn.setFixedHeight(22)
        add_cat_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {MUTED};"
            f" border: 1px solid {BORDER}; border-radius: 4px;"
            f" font-size: 10px; padding: 0 8px; }}"
            f" QPushButton:hover {{ color: {TEXT}; background: {BG3};"
            f" border-color: {BORDER2}; }}"
        )
        add_cat_btn.clicked.connect(self._on_category_menu)
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

        # ── Compact top-3 goals strip ──────────────────────
        self._goals_strip = QWidget()
        self._goals_strip.setStyleSheet(
            f"background: {BG2}; border-top: 1px solid {BORDER};"
        )
        self._goals_strip_layout = QVBoxLayout(self._goals_strip)
        self._goals_strip_layout.setContentsMargins(8, 6, 8, 6)
        self._goals_strip_layout.setSpacing(2)
        ll.addWidget(self._goals_strip)

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
        self._tabs.tabBar().tabMoved.connect(self._on_tab_moved)
        overview = self._build_overview_tab()
        self._tabs.addTab(overview, "Overview")
        # Prevent the Overview tab from being closable
        self._tabs.tabBar().setTabButton(0, self._tabs.tabBar().RightSide, None)

        self._cal_tab = CalendarWidget(store=self._store)
        self._cal_tab.reload_needed.connect(self._trigger_reload)
        self._tabs.addTab(self._cal_tab, "Calendar")
        self._tabs.tabBar().setTabButton(1, self._tabs.tabBar().RightSide, None)

        self._goals_tab = GoalsTab()
        self._goals_tab.open_goal_dialog.connect(self._on_edit_goals)
        self._goals_tab.task_clicked.connect(self._open_task_tab)
        self._goals_tab.edit_goal.connect(self._on_edit_single_goal)
        self._goals_tab.cancel_goal.connect(self._on_cancel_goal)
        self._goals_tab.archive_goal.connect(self._on_archive_goal)
        self._tabs.addTab(self._goals_tab, "Goals")
        self._tabs.tabBar().setTabButton(2, self._tabs.tabBar().RightSide, None)

        splitter.addWidget(self._tabs)
        splitter.setSizes([390, 1210])
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

        # Chart sections in a resizable vertical splitter
        vsplit = QSplitter(Qt.Vertical)
        vsplit.setChildrenCollapsible(False)
        vsplit.setStyleSheet(
            f"QSplitter::handle:vertical {{ background: {BORDER}; height: 4px; margin: 1px 0; }}"
            f"QSplitter::handle:vertical:hover {{ background: {ACCENT}; }}"
        )

        self._stacked_chart = StackedAreaChart()
        vsplit.addWidget(make_chart_panel("Daily activity", self._stacked_chart))

        row2_w = QWidget()
        row2_w.setStyleSheet(f"background: {BG};")
        row2 = QHBoxLayout(row2_w)
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(PAD_SM)
        self._wd_chart = WeekdayBarChart()
        row2.addWidget(make_chart_panel("Avg by weekday", self._wd_chart))
        self._wc_chart = WeeklyCompChart()
        row2.addWidget(make_chart_panel("This week vs last week", self._wc_chart))
        vsplit.addWidget(row2_w)

        self._hm_chart = HourHeatmap()
        vsplit.addWidget(make_chart_panel("Hour-of-day heatmap", self._hm_chart))

        self._cat_breakdown = CategoryBreakdownChart()
        vsplit.addWidget(make_chart_panel("Category breakdown", self._cat_breakdown))

        cl.addWidget(vsplit)
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
        if self._cal_tab:
            self._cal_tab.refresh(result)
        self._rebuild_goal_rows()

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

    # ── Task rows ────────────────────────────────────────

    def _rebuild_task_rows(self) -> None:
        while self._task_layout.count() > 1:
            item = self._task_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._result:
            return

        # Decide which tasks to show
        visible_tasks = []
        hidden_archived = 0
        for t in self._result.tasks:
            if t.archived:
                if self._show_archived:
                    visible_tasks.append(t)
                else:
                    hidden_archived += 1
                continue
            visible_tasks.append(t)

        all_sec = [t.total_seconds for t in visible_tasks]
        max_sec = max(all_sec) if all_sec else 1.0

        self._task_rows = {}
        for t in sorted(visible_tasks, key=lambda t: t.total_seconds, reverse=True):
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
                archived         = t.archived,
            )
            row.clock_in_requested.connect(self._on_clock_in)
            row.clock_out_requested.connect(self._on_clock_out)
            row.rename_requested.connect(self._on_rename_task)
            row.move_requested.connect(self._on_move_task)
            row.delete_requested.connect(self._on_delete_task)
            row.archive_requested.connect(self._on_archive_task)
            row.clicked.connect(self._open_task_tab)
            self._task_layout.insertWidget(self._task_layout.count() - 1, row)
            self._task_rows[t.name] = row

        # Footer hint when tasks are hidden
        if hidden_archived > 0 and not self._show_archived:
            hint = label(f"{hidden_archived} archived hidden", FAINT, size=9)
            hint.setAlignment(Qt.AlignCenter)
            hint.setContentsMargins(0, 4, 0, 4)
            self._task_layout.insertWidget(self._task_layout.count() - 1, hint)

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
        if not self._result:
            return
        # Pass ALL tasks with goals to GoalsTab — it handles filtering internally
        all_goal_tasks = [
            t for t in self._result.tasks
            if t.goal_hours > 0
        ]
        if self._goals_tab:
            self._goals_tab.refresh(all_goal_tasks, self._goals)

        # Sidebar strip shows only active (non-archived, non-auto-archived) goals
        today = date.today()
        active_tasks = [
            t for t in all_goal_tasks
            if not _goal_is_archived(self._goals.get(t.name, GoalSpec()), today)
        ]
        self._rebuild_goals_strip(active_tasks)

    def _rebuild_goals_strip(self, tasks_with_goals: list) -> None:
        """Compact top-3 goals by completion % shown at the bottom of the left panel."""
        while self._goals_strip_layout.count():
            item = self._goals_strip_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not tasks_with_goals:
            self._goals_strip.setVisible(False)
            return

        self._goals_strip.setVisible(True)

        # header row
        hdr = QHBoxLayout()
        hdr.setSpacing(4)
        h_lbl = QLabel("Top Goals")
        h_lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 9px; font-weight: 600; letter-spacing: 0.5px;"
            f" background: transparent; border: none;"
        )
        hdr.addWidget(h_lbl)
        hdr.addStretch()
        see_all = QPushButton("See all →")
        see_all.setFlat(True)
        see_all.setStyleSheet(
            f"color: {ACCENT}; font-size: 9px; background: transparent; border: none;"
        )
        see_all.setCursor(Qt.PointingHandCursor)
        see_all.clicked.connect(lambda: self._switch_to_goals_tab())
        hdr.addWidget(see_all)
        self._goals_strip_layout.addLayout(hdr)

        # top-3 by completion %
        top3 = sorted(tasks_with_goals, key=lambda t: t.goal_progress(), reverse=True)[:3]
        for t in top3:
            pct  = t.goal_progress()
            row  = QWidget()
            row.setStyleSheet("background: transparent;")
            rl   = QVBoxLayout(row)
            rl.setContentsMargins(0, 2, 0, 2)
            rl.setSpacing(2)

            name_row = QHBoxLayout()
            name_row.setSpacing(4)
            dot = QLabel("●")
            dot.setStyleSheet(
                f"color: {t.colour}; font-size: 9px; background: transparent; border: none;"
            )
            dot.setFixedWidth(10)
            name_row.addWidget(dot)
            name_lbl = QLabel(t.name)
            name_lbl.setStyleSheet(
                f"color: {TEXT}; font-size: 9px; background: transparent; border: none;"
            )
            name_row.addWidget(name_lbl, stretch=1)
            pct_lbl = QLabel(f"{int(pct * 100)}%")
            pct_color = SUCCESS if pct >= 1.0 else (WARNING if pct >= 0.5 else MUTED)
            pct_lbl.setStyleSheet(
                f"color: {pct_color}; font-size: 9px; font-family: Consolas, monospace;"
                f" background: transparent; border: none;"
            )
            name_row.addWidget(pct_lbl)
            rl.addLayout(name_row)

            # mini progress bar
            bar = QWidget()
            bar.setFixedHeight(3)
            bar.setStyleSheet(f"background: {BG3}; border-radius: 1px;")
            bar_fill = QWidget(bar)
            fill_w = max(3, int(pct * (bar.sizeHint().width() or 200)))
            bar_fill.setStyleSheet(f"background: {t.colour}; border-radius: 1px;")
            bar.setMinimumWidth(50)

            # We use a layout-based approach for the mini bar
            bar_outer = QWidget()
            bar_outer.setFixedHeight(4)
            bar_outer.setStyleSheet(f"background: {BG3}; border-radius: 2px;")
            bar_lay = QHBoxLayout(bar_outer)
            bar_lay.setContentsMargins(0, 0, 0, 0)
            bar_lay.setSpacing(0)
            fill = QWidget()
            fill.setFixedHeight(4)
            fill.setStyleSheet(f"background: {t.colour}; border-radius: 2px;")
            bar_lay.addWidget(fill, stretch=int(pct * 100))
            bar_lay.addStretch(max(1, 100 - int(pct * 100)))
            rl.addWidget(bar_outer)

            self._goals_strip_layout.addWidget(row)

    def _switch_to_goals_tab(self) -> None:
        for i in range(self._tabs.count()):
            if self._tabs.widget(i) is self._goals_tab:
                self._tabs.setCurrentIndex(i)
                break

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

    # ── Tab management ───────────────────────────────────

    def _rebuild_category_tabs(self) -> None:
        """Recreate category tabs, preserving any open task tabs."""
        # Remember the currently active widget so we can restore it
        current_widget = self._tabs.currentWidget()

        # Remove only the existing category tabs (leave task tabs in place)
        for old_tab in list(self._category_tabs.values()):
            for i in range(self._tabs.count()):
                if self._tabs.widget(i) is old_tab:
                    self._tabs.removeTab(i)
                    break
            old_tab.deleteLater()
        self._category_tabs.clear()

        if not self._result:
            return

        # Insert category tabs after Overview (0), Calendar (1), Goals (2)
        insert_at = 3
        seen: set[str] = set()
        for t in self._result.tasks:
            if t.tag and t.tag not in seen:
                seen.add(t.tag)
                tab = CategoryTabWidget(t.tag, parent=self)
                cap = t.tag[:1].upper() + t.tag[1:] if t.tag else t.tag
                display = cap if len(cap) <= 14 else cap[:13] + "…"
                self._tabs.insertTab(insert_at, tab, display)
                self._tabs.tabBar().setTabButton(
                    insert_at, self._tabs.tabBar().RightSide, None)
                self._category_tabs[t.tag] = tab
                insert_at += 1

        # Restore the previously active tab
        if current_widget is not None:
            for i in range(self._tabs.count()):
                if self._tabs.widget(i) is current_widget:
                    self._tabs.setCurrentIndex(i)
                    return

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
        tab.edit_session_requested.connect(self._on_edit_session)
        tab.delete_session_requested.connect(self._on_delete_session)
        tab.add_session_requested.connect(self._on_add_session)
        tab.edit_goal_requested.connect(self._on_edit_single_goal)
        tab.remove_goal_requested.connect(self._on_cancel_goal)
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

    def _on_tab_moved(self, from_idx: int, to_idx: int) -> None:
        """Keep Overview and Calendar tabs pinned at positions 0 and 1."""
        if from_idx <= 1 or to_idx <= 1:
            bar = self._tabs.tabBar()
            bar.blockSignals(True)
            bar.moveTab(to_idx, from_idx)  # undo the move
            bar.blockSignals(False)

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
        self._rebuild_task_rows()

    # ── Theme toggle ─────────────────────────────────────────

    def _on_toggle_theme(self) -> None:
        # Remember active tab so we can restore it after rebuild
        saved_tab = ""
        if hasattr(self, "_tabs"):
            idx = self._tabs.currentIndex()
            if idx >= 0:
                saved_tab = self._tabs.tabBar().tabText(idx)

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

        # Restore the tab the user was on
        if saved_tab:
            for i in range(self._tabs.count()):
                if self._tabs.tabBar().tabText(i) == saved_tab:
                    self._tabs.setCurrentIndex(i)
                    break

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
