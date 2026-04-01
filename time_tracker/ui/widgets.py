"""
ui/widgets.py — Reusable PyQt5 components for the Time Tracker UI.
"""

from __future__ import annotations
from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal, QRectF
from PyQt5.QtGui import QColor, QPainter, QPen, QFont, QFontMetrics
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QMenu,
    QDialog, QDialogButtonBox, QDateTimeEdit,
)
from PyQt5.QtCore import QDateTime

from .theme import (
    BG, BG2, BG3, BG4, BORDER, BORDER2,
    TEXT, MUTED, FAINT, ACCENT, ACCENT_DIM,
    SUCCESS, SUCCESS_DIM, WARNING, WARNING_DIM, DANGER, DANGER_DIM,
    PAD_XS, PAD_SM, PAD_MD, PAD_LG,
)


# ──────────────────────────────────────────────────────────
# Primitive helpers
# ──────────────────────────────────────────────────────────

def h_line() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet(f"color: {BORDER}; max-height: 1px; background: {BORDER};")
    return f


def v_line() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.VLine)
    f.setStyleSheet(f"color: {BORDER}; max-width: 1px; background: {BORDER};")
    return f


def label(text: str, colour: str = TEXT, bold: bool = False,
          size: int = 11) -> QLabel:
    lbl = QLabel(text)
    w   = "600" if bold else "400"
    lbl.setStyleSheet(
        f"color: {colour}; font-size: {size}px; font-weight: {w};"
        f" background: transparent; border: none;"
    )
    return lbl


def card_frame(parent=None) -> QFrame:
    f = QFrame(parent)
    f.setStyleSheet(
        f"QFrame {{ background: {BG2}; border-radius: 8px;"
        f" border: 1px solid {BORDER}; }}"
    )
    return f


# ──────────────────────────────────────────────────────────
# Metric card  (top of right panel, 4 across)
# ──────────────────────────────────────────────────────────

class MetricCard(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame {{ background: {BG2}; border-radius: 8px;"
            f" border: 1px solid {BORDER}; }}"
        )
        self.setMinimumHeight(80)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(2)

        self._title = label(title, MUTED, size=10)
        self._value = label("—", TEXT, bold=True, size=24)
        self._sub   = label("", FAINT, size=10)

        lay.addWidget(self._title)
        lay.addWidget(self._value)
        lay.addWidget(self._sub)
        lay.addStretch()

    def update_value(self, value: str, sub: str = "",
                     colour: str = TEXT) -> None:
        self._value.setText(value)
        self._value.setStyleSheet(
            f"color: {colour}; font-size: 24px; font-weight: 600;"
            f" background: transparent; border: none;"
        )
        self._sub.setText(sub)


# ──────────────────────────────────────────────────────────
# Insight strip  (row of small insight cards)
# ──────────────────────────────────────────────────────────

_SENTIMENT_COLORS = {
    "positive": (SUCCESS, SUCCESS_DIM),
    "warning":  (WARNING, WARNING_DIM),
    "negative": (DANGER,  DANGER_DIM),
    "neutral":  (MUTED,   BG3),
}


class InsightCard(QFrame):
    def __init__(self, icon: str, label_txt: str, value: str,
                 sub: str, sentiment: str, parent=None):
        super().__init__(parent)
        fg, bg = _SENTIMENT_COLORS.get(sentiment, (MUTED, BG3))
        self.setStyleSheet(
            f"QFrame {{ background: {bg}; border-radius: 8px;"
            f" border: 1px solid {BORDER}; }}"
        )
        self.setFixedHeight(72)
        self.setMinimumWidth(150)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(1)

        top = QHBoxLayout()
        top.setSpacing(5)
        top.addWidget(label(icon, fg, size=13))
        top.addWidget(label(label_txt, MUTED, size=10))
        top.addStretch()
        lay.addLayout(top)

        lay.addWidget(label(value, fg, bold=True, size=16))
        if sub:
            lay.addWidget(label(sub, MUTED, size=9))


class InsightStrip(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(PAD_SM)
        self._lay.addStretch()

    def refresh(self, insights) -> None:
        # Clear existing cards
        while self._lay.count() > 1:
            item = self._lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for ins in insights:
            card = InsightCard(ins.icon, ins.label, ins.value,
                               ins.sub, ins.sentiment)
            self._lay.insertWidget(self._lay.count() - 1, card)

        self.setVisible(len(insights) > 0)


# ──────────────────────────────────────────────────────────
# Chart panel  (titled container for QPainter charts)
# ──────────────────────────────────────────────────────────

class ChartPanel(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QFrame()
        header.setFixedHeight(30)
        header.setStyleSheet(
            f"QFrame {{ background: {BG3};"
            f" border-top-left-radius: 8px; border-top-right-radius: 8px;"
            f" border: 1px solid {BORDER}; border-bottom: none; }}"
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(12, 0, 12, 0)
        hl.addWidget(label(title, MUTED, size=10))
        hl.addStretch()
        outer.addWidget(header)

        self._content = QFrame()
        self._content.setStyleSheet(
            f"QFrame {{ background: {BG2};"
            f" border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;"
            f" border: 1px solid {BORDER}; border-top: none; }}"
        )
        cl = QVBoxLayout(self._content)
        cl.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._content)
        self._cl = cl

    def add_widget(self, w: QWidget) -> None:
        self._cl.addWidget(w)


# ──────────────────────────────────────────────────────────
# Collapsible section  (left panel goals)
# ──────────────────────────────────────────────────────────

class CollapsibleSection(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._expanded = True

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(3)

        header = QFrame()
        header.setCursor(Qt.PointingHandCursor)
        header.setFixedHeight(32)
        header.setStyleSheet(
            f"QFrame {{ background: {BG3}; border-radius: 6px;"
            f" border: 1px solid {BORDER}; }}"
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(10, 0, 10, 0)
        hl.setSpacing(8)

        self._arrow = label("▾", MUTED, size=10)
        self._arrow.setFixedWidth(12)
        hl.addWidget(self._arrow)
        hl.addWidget(label(title, TEXT, bold=True, size=10))
        hl.addStretch()
        header.mousePressEvent = lambda _: self._toggle()
        outer.addWidget(header)

        self._content = QFrame()
        self._content.setStyleSheet(
            f"QFrame {{ background: {BG2}; border-radius: 6px;"
            f" border: 1px solid {BORDER}; }}"
        )
        cl = QVBoxLayout(self._content)
        cl.setContentsMargins(PAD_SM, PAD_SM, PAD_SM, PAD_SM)
        cl.setSpacing(4)
        outer.addWidget(self._content)
        self._cl = cl

    def add_widget(self, w: QWidget) -> None:
        self._cl.addWidget(w)

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        self._arrow.setText("▾" if self._expanded else "▸")


# ──────────────────────────────────────────────────────────
# Dual-handle range slider
# ──────────────────────────────────────────────────────────

class RangeSlider(QWidget):
    range_changed = pyqtSignal(int, int)
    HANDLE_R = 8
    TRACK_H  = 4

    def __init__(self, count: int = 100, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(32)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._count    = max(2, count)
        self._low      = 0
        self._high     = self._count - 1
        self._dragging: Optional[str] = None

    def set_count(self, n: int) -> None:
        self._count = max(2, n)
        self._low, self._high = 0, self._count - 1
        self.update()

    def set_range(self, low: int, high: int) -> None:
        self._low  = max(0, min(low,  self._count - 1))
        self._high = max(self._low, min(high, self._count - 1))
        self.update()

    @property
    def low(self)  -> int: return self._low
    @property
    def high(self) -> int: return self._high

    def _track(self):
        r = self.HANDLE_R
        return (r, self.height() // 2 - self.TRACK_H // 2,
                self.width() - 2 * r, self.TRACK_H)

    def _to_x(self, idx: int) -> int:
        tx, _, tw, _ = self._track()
        return tx + int(idx / max(1, self._count - 1) * tw)

    def _to_idx(self, x: int) -> int:
        tx, _, tw, _ = self._track()
        pct = (x - tx) / max(1, tw)
        return max(0, min(self._count - 1, round(pct * (self._count - 1))))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        tx, ty, tw, th = self._track()
        cy = self.height() // 2
        r  = self.HANDLE_R

        p.setPen(Qt.NoPen)
        p.setBrush(QColor(BG4))
        p.drawRoundedRect(tx, ty, tw, th, 2, 2)

        lx, hx = self._to_x(self._low), self._to_x(self._high)
        p.setBrush(QColor(ACCENT))
        p.drawRoundedRect(lx, ty, hx - lx, th, 2, 2)

        p.setPen(QPen(QColor(BG), 2))
        p.setBrush(QColor(ACCENT))
        for x in (lx, hx):
            p.drawEllipse(x - r, cy - r, 2 * r, 2 * r)
        p.end()

    def mousePressEvent(self, e):
        lx, hx = self._to_x(self._low), self._to_x(self._high)
        r = self.HANDLE_R + 4
        if abs(e.x() - lx) <= r:
            self._dragging = "low"
        elif abs(e.x() - hx) <= r:
            self._dragging = "high"
        else:
            idx = self._to_idx(e.x())
            if abs(idx - self._low) <= abs(idx - self._high):
                self._low = max(0, min(idx, self._high))
            else:
                self._high = max(self._low, min(idx, self._count - 1))
            self.update()
            self.range_changed.emit(self._low, self._high)

    def mouseMoveEvent(self, e):
        if not self._dragging:
            return
        idx = self._to_idx(e.x())
        if self._dragging == "low":
            self._low = max(0, min(idx, self._high))
        else:
            self._high = max(self._low, min(idx, self._count - 1))
        self.update()
        self.range_changed.emit(self._low, self._high)

    def mouseReleaseEvent(self, _):
        self._dragging = None


# ──────────────────────────────────────────────────────────
# Quick preset buttons
# ──────────────────────────────────────────────────────────

class PresetBar(QWidget):
    preset_selected = pyqtSignal(str)
    PRESETS = ["7d", "30d", "Month", "Last mo.", "Week", "Last wk", "All"]
    PRESET_KEYS = ["Last 7d", "Last 30d", "This month", "Last month",
                   "This week", "Last week", "All"]

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(PAD_XS)
        for display, key in zip(self.PRESETS, self.PRESET_KEYS):
            btn = QPushButton(display)
            btn.setFixedHeight(24)
            btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {MUTED};"
                f" border: 1px solid {BORDER}; border-radius: 5px;"
                f" font-size: 10px; padding: 0 8px; }}"
                f" QPushButton:hover {{ color: {TEXT}; border-color: {BORDER2};"
                f" background: {BG3}; }}"
            )
            btn.clicked.connect(
                lambda _, k=key: self.preset_selected.emit(k)
            )
            lay.addWidget(btn)
        lay.addStretch()


# ──────────────────────────────────────────────────────────
# Mini progress bar (used in task rows + goal rows)
# ──────────────────────────────────────────────────────────

class _MiniBar(QWidget):
    def __init__(self, value: float = 0, maximum: float = 1,
                 colour: str = ACCENT, parent=None):
        super().__init__(parent)
        self._value   = value
        self._maximum = max(1.0, maximum)
        self._colour  = colour
        self.setFixedHeight(5)

    def set(self, value: float, maximum: float, colour: str = "") -> None:
        self._value   = value
        self._maximum = max(1.0, maximum)
        if colour:
            self._colour = colour
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(BG4))
        p.drawRoundedRect(0, 0, w, h, 2, 2)
        fill = int(w * min(1.0, self._value / self._maximum))
        if fill > 0:
            p.setBrush(QColor(self._colour))
            p.drawRoundedRect(0, 0, fill, h, 2, 2)
        p.end()


# ──────────────────────────────────────────────────────────
# Task row  (left panel task list)
# ──────────────────────────────────────────────────────────

class TaskRow(QWidget):
    clock_in_requested  = pyqtSignal(str)
    clock_out_requested = pyqtSignal(str)
    rename_requested    = pyqtSignal(str)
    move_requested      = pyqtSignal(str)
    delete_requested    = pyqtSignal(str)
    clicked             = pyqtSignal(str)

    def __init__(self, task_name: str, colour: str,
                 total_sec: float = 0, max_sec: float = 1,
                 n_sessions: int = 0, clocked_in: bool = False,
                 elapsed_sec: float = 0, category_colour: str = "",
                 parent=None):
        super().__init__(parent)
        self._name       = task_name
        self._colour     = colour
        self._clocked_in = clocked_in

        self.setStyleSheet(
            f"TaskRow {{ border-bottom: 1px solid {BORDER};"
            f" background: transparent; }}"
        )

        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 8, 4, 8)
        lay.setSpacing(8)

        # Category colour accent stripe (thin left border)
        if category_colour:
            stripe = QFrame()
            stripe.setFixedWidth(3)
            stripe.setFixedHeight(28)
            stripe.setStyleSheet(
                f"background: {category_colour}; border-radius: 1px;"
                f" border: none;"
            )
            lay.addWidget(stripe)

        # Dot
        dot = QLabel("●")
        dot.setStyleSheet(
            f"color: {colour}; font-size: 11px;"
            f" background: transparent; border: none;"
        )
        dot.setFixedWidth(14)
        lay.addWidget(dot)

        # Name
        name_lbl = QLabel(task_name)
        name_lbl.setStyleSheet(
            f"color: {TEXT}; font-size: 11px;"
            f" background: transparent; border: none;"
        )
        name_lbl.setMinimumWidth(120)
        lay.addWidget(name_lbl)

        # Bar
        self._bar = _MiniBar(total_sec, max_sec, colour)
        lay.addWidget(self._bar, stretch=1)

        # Duration
        from ..core.models import fmt_dur
        self._dur_lbl = QLabel(fmt_dur(total_sec, short=True))
        self._dur_lbl.setStyleSheet(
            f"color: {TEXT}; font-size: 11px; font-weight: 600;"
            f" min-width: 56px; background: transparent; border: none;"
        )
        self._dur_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(self._dur_lbl)

        # Elapsed (clocked in)
        self._elapsed_lbl = QLabel()
        self._elapsed_lbl.setStyleSheet(
            f"color: {SUCCESS}; font-size: 10px; min-width: 50px;"
            f" background: transparent; border: none;"
        )
        self._elapsed_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._elapsed_lbl.setVisible(clocked_in)
        if clocked_in:
            self._elapsed_lbl.setText(fmt_dur(elapsed_sec, short=True))
        lay.addWidget(self._elapsed_lbl)

        # Clock button
        self._btn = QPushButton()
        self._btn.setFixedSize(72, 24)
        self._update_btn()
        self._btn.clicked.connect(self._on_clock)
        lay.addWidget(self._btn)

    def _update_btn(self) -> None:
        if self._clocked_in:
            self._btn.setText("Clock Out")
            self._btn.setStyleSheet(
                f"QPushButton {{ background: {DANGER}; color: white;"
                f" border-radius: 5px; font-size: 10px; font-weight: 600;"
                f" border: none; }}"
                f" QPushButton:hover {{ background: #c0392b; }}"
            )
        else:
            self._btn.setText("Clock In")
            self._btn.setStyleSheet(
                f"QPushButton {{ background: {SUCCESS}; color: white;"
                f" border-radius: 5px; font-size: 10px; font-weight: 600;"
                f" border: none; }}"
                f" QPushButton:hover {{ background: #2aab6f; }}"
            )

    def _on_clock(self) -> None:
        if self._clocked_in:
            self.clock_out_requested.emit(self._name)
        else:
            self.clock_in_requested.emit(self._name)

    def update_elapsed(self, sec: float) -> None:
        from ..core.models import fmt_dur
        self._elapsed_lbl.setVisible(True)
        self._elapsed_lbl.setText(fmt_dur(sec, short=True))

    def set_clocked_in(self, state: bool) -> None:
        self._clocked_in = state
        self._elapsed_lbl.setVisible(state)
        self._update_btn()

    def mousePressEvent(self, e) -> None:
        # Left-click on the row (not on the clock button) opens the task tab
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self._name)
        super().mousePressEvent(e)

    def contextMenuEvent(self, e) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background: {BG2}; color: {TEXT};"
            f" border: 1px solid {BORDER}; padding: 2px; }}"
            f" QMenu::item {{ padding: 5px 20px 5px 12px; }}"
            f" QMenu::item:selected {{ background: {BG3}; }}"
        )
        menu.addAction("Rename…").triggered.connect(
            lambda: self.rename_requested.emit(self._name))
        menu.addAction("Move to category…").triggered.connect(
            lambda: self.move_requested.emit(self._name))
        menu.addSeparator()
        del_act = menu.addAction("Delete task…")
        del_act.setStyleSheet(f"color: {DANGER};")
        del_act.triggered.connect(
            lambda: self.delete_requested.emit(self._name))
        menu.exec_(e.globalPos())


# ──────────────────────────────────────────────────────────
# Goal row  (left panel goal progress)
# ──────────────────────────────────────────────────────────

class GoalRow(QWidget):
    """Rich goal display: progress, deadline, pace indicator."""

    def __init__(self, task_name: str, colour: str, parent=None):
        super().__init__(parent)
        self._colour = colour
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 8)
        lay.setSpacing(3)

        # Top row: dot + name + percentage
        top = QHBoxLayout()
        top.setSpacing(6)
        dot = QLabel("●")
        dot.setStyleSheet(
            f"color: {colour}; font-size: 10px;"
            f" background: transparent; border: none;"
        )
        dot.setFixedWidth(12)
        top.addWidget(dot)
        self._name_lbl = QLabel(task_name)
        self._name_lbl.setStyleSheet(
            f"color: {TEXT}; font-size: 10px; font-weight: 600;"
            f" background: transparent; border: none;"
        )
        top.addWidget(self._name_lbl, stretch=1)
        self._pct_lbl = QLabel("0%")
        self._pct_lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 10px;"
            f" background: transparent; border: none;"
        )
        top.addWidget(self._pct_lbl)
        lay.addLayout(top)

        # Progress bar
        self._bar = _MiniBar(0, 1, colour)
        lay.addWidget(self._bar)

        # Detail row: hours / goal · deadline
        self._detail_lbl = QLabel()
        self._detail_lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 9px;"
            f" background: transparent; border: none;"
        )
        lay.addWidget(self._detail_lbl)

        # Pace row
        self._pace_lbl = QLabel()
        self._pace_lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 9px;"
            f" background: transparent; border: none;"
        )
        lay.addWidget(self._pace_lbl)

    def update(self, progress: float, goal_hours: float,
               daily_avg: float, req_hpd: Optional[float],
               deadline_days: Optional[int]) -> None:  # type: ignore[override]
        pct = int(progress * 100)
        from ..core.models import fmt_dur
        done_h = progress * goal_hours
        self._bar.set(progress, 1.0, self._colour)

        # Color based on progress
        if pct >= 80:
            c = SUCCESS
        elif pct >= 40:
            c = WARNING
        else:
            c = MUTED

        self._pct_lbl.setText(f"{pct}%")
        self._pct_lbl.setStyleSheet(
            f"color: {c}; font-size: 10px;"
            f" background: transparent; border: none;"
        )

        done_str = fmt_dur(done_h * 3600, short=True)
        goal_str = fmt_dur(goal_hours * 3600, short=True)
        detail   = f"{done_str} / {goal_str}"
        if deadline_days is not None:
            detail += f"  ·  due in {deadline_days}d"
        self._detail_lbl.setText(detail)

        if req_hpd is not None:
            on_pace = daily_avg >= req_hpd
            icon    = "✓" if on_pace else "⚠"
            col     = SUCCESS if on_pace else WARNING
            self._pace_lbl.setText(
                f"{icon}  {req_hpd:.1f}h/day needed  ·  avg {daily_avg:.1f}h/day"
            )
            self._pace_lbl.setStyleSheet(
                f"color: {col}; font-size: 9px;"
                f" background: transparent; border: none;"
            )
            self._pace_lbl.setVisible(True)
        else:
            self._pace_lbl.setVisible(False)


# ──────────────────────────────────────────────────────────
# Session table  (per-task tab)
# ──────────────────────────────────────────────────────────

class _SessionRow(QWidget):
    """Single session row with a hover-revealed Edit button."""

    edit_requested   = pyqtSignal(int, object, object)
    delete_requested = pyqtSignal(int, bool)

    def __init__(self, session_id: int, is_open: bool,
                 start, end, dur_str: str, parent=None):
        super().__init__(parent)
        self._id      = session_id
        self._is_open = is_open
        self._start   = start
        self._end     = end

        self.setObjectName("SessRow")
        self.setStyleSheet(
            f"#SessRow {{ border-bottom: 1px solid {BORDER};"
            f" background: transparent; }}"
            f"#SessRow:hover {{ background: {BG3}; }}"
        )
        self.setAttribute(Qt.WA_Hover, True)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 5, 8, 5)
        lay.setSpacing(0)

        def _cell(text: str, width: int, colour: str = TEXT) -> QLabel:
            lbl = QLabel(text)
            lbl.setFixedWidth(width)
            lbl.setStyleSheet(
                f"color: {colour}; font-size: 11px;"
                f" background: transparent; border: none;"
            )
            return lbl

        lay.addWidget(_cell(start.strftime("%Y-%m-%d"), 108))
        lay.addWidget(_cell(start.strftime("%H:%M"), 72))
        end_str = end.strftime("%H:%M") if end else "—"
        lay.addWidget(_cell(end_str, 72, TEXT if end else MUTED))

        dur_lbl = QLabel(dur_str)
        dur_lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 11px;"
            f" background: transparent; border: none;"
        )
        lay.addWidget(dur_lbl, stretch=1)

        # Action buttons — hidden until hover
        self._edit_btn = QPushButton("Edit")
        self._edit_btn.setFixedSize(46, 22)
        self._edit_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {MUTED};"
            f" border: 1px solid {BORDER}; border-radius: 4px;"
            f" font-size: 10px; }}"
            f" QPushButton:hover {{ color: {TEXT}; background: {BG4};"
            f" border-color: {BORDER2}; }}"
        )
        self._edit_btn.setVisible(False)
        if not is_open:
            self._edit_btn.clicked.connect(
                lambda: self.edit_requested.emit(self._id, self._start, self._end)
            )
        lay.addWidget(self._edit_btn)

        self._del_btn = QPushButton("Delete")
        self._del_btn.setFixedSize(54, 22)
        self._del_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {DANGER};"
            f" border: 1px solid {DANGER}; border-radius: 4px;"
            f" font-size: 10px; }}"
            f" QPushButton:hover {{ background: {DANGER_DIM}; }}"
        )
        self._del_btn.setVisible(False)
        self._del_btn.clicked.connect(
            lambda: self.delete_requested.emit(self._id, self._is_open)
        )
        lay.addWidget(self._del_btn)

    def enterEvent(self, e) -> None:
        if not self._is_open:
            self._edit_btn.setVisible(True)
        self._del_btn.setVisible(True)
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        self._edit_btn.setVisible(False)
        self._del_btn.setVisible(False)
        super().leaveEvent(e)


class SessionTable(QWidget):
    """Scrollable list of session rows for a single task.

    Signals
    -------
    edit_requested(int, object, object)  — session_id, start datetime, end datetime
    delete_requested(int, bool)          — session_id, is_open
    """

    edit_requested   = pyqtSignal(int, object, object)
    delete_requested = pyqtSignal(int, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(200)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header row
        hdr = QFrame()
        hdr.setFixedHeight(28)
        hdr.setStyleSheet(
            f"QFrame {{ background: {BG3}; border-bottom: 1px solid {BORDER}; }}"
        )
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(8, 0, 8, 0)
        hl.setSpacing(0)
        for txt, w in [("Date", 108), ("Start", 72), ("End", 72)]:
            lbl = QLabel(txt)
            lbl.setFixedWidth(w)
            lbl.setStyleSheet(
                f"color: {MUTED}; font-size: 10px;"
                f" background: transparent; border: none;"
            )
            hl.addWidget(lbl)
        dur_hdr = QLabel("Duration")
        dur_hdr.setStyleSheet(
            f"color: {MUTED}; font-size: 10px;"
            f" background: transparent; border: none;"
        )
        hl.addWidget(dur_hdr, stretch=1)
        root.addWidget(hdr)

        # Scrollable rows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {BG2}; }}"
            f"QScrollBar:vertical {{ background: {BG2}; width: 4px; }}"
            f"QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 2px; }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
        )
        self._container = QWidget()
        self._container.setStyleSheet(f"background: {BG2};")
        self._list_lay = QVBoxLayout(self._container)
        self._list_lay.setContentsMargins(0, 0, 0, 0)
        self._list_lay.setSpacing(0)
        self._list_lay.addStretch()
        scroll.setWidget(self._container)
        root.addWidget(scroll)

    def refresh(self, task, start, end) -> None:
        from ..core.models import fmt_dur
        # Remove all existing rows (keep trailing stretch)
        while self._list_lay.count() > 1:
            item = self._list_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sessions = sorted(
            task.sessions_in_range(start, end),
            key=lambda s: s.start,
            reverse=True,
        )
        for s in sessions:
            row = _SessionRow(
                session_id=s.line_index,
                is_open=s.is_open,
                start=s.start,
                end=s.end,
                dur_str=fmt_dur(s.duration_seconds, short=True),
            )
            row.edit_requested.connect(self.edit_requested)
            row.delete_requested.connect(self.delete_requested)
            self._list_lay.insertWidget(self._list_lay.count() - 1, row)


# ──────────────────────────────────────────────────────────
# Session edit / add dialogs
# ──────────────────────────────────────────────────────────

_DT_CSS = (
    f"QDateTimeEdit {{ background: {BG3}; color: {TEXT};"
    f" border: 1px solid {BORDER}; border-radius: 5px;"
    f" padding: 4px 8px; font-size: 11px; }}"
    f" QDateTimeEdit:focus {{ border-color: {ACCENT}; }}"
)


class EditSessionDialog(QDialog):
    """Edit the start and end times of an existing session."""

    def __init__(self, start, end, parent=None):
        from datetime import datetime as _dt
        super().__init__(parent)
        self.setWindowTitle("Edit Session")
        self.setFixedWidth(360)
        self.setStyleSheet(
            f"background: {BG}; color: {TEXT};"
            f" QLabel {{ background: transparent; }}"
        )
        root = QVBoxLayout(self)
        root.setSpacing(PAD_SM)

        for lbl_text, attr, dt_val in [
            ("Start", "_start_edit", start),
            ("End",   "_end_edit",   end),
        ]:
            root.addWidget(label(lbl_text, MUTED, size=10))
            edit = QDateTimeEdit()
            edit.setDisplayFormat("yyyy-MM-dd  HH:mm:ss")
            edit.setCalendarPopup(True)
            edit.setStyleSheet(_DT_CSS)
            if dt_val:
                from PyQt5.QtCore import QDateTime as _QDT, QDate as _QDate, QTime as _QTime
                edit.setDateTime(_QDT(
                    _QDate(dt_val.year, dt_val.month, dt_val.day),
                    _QTime(dt_val.hour, dt_val.minute, dt_val.second),
                ))
            setattr(self, attr, edit)
            root.addWidget(edit)

        root.addStretch()
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.setStyleSheet(f"color: {TEXT};")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    def _on_accept(self) -> None:
        if self._start_edit.dateTime() >= self._end_edit.dateTime():
            self._end_edit.setStyleSheet(
                _DT_CSS + f" QDateTimeEdit {{ border-color: {DANGER}; }}")
            return
        self.accept()

    def values(self):
        from datetime import datetime as _dt
        def _to_dt(qdt):
            d = qdt.date()
            t = qdt.time()
            return _dt(d.year(), d.month(), d.day(),
                       t.hour(), t.minute(), t.second())
        return _to_dt(self._start_edit.dateTime()), \
               _to_dt(self._end_edit.dateTime())


class AddSessionDialog(QDialog):
    """Log a manual session retroactively."""

    def __init__(self, parent=None):
        from datetime import datetime as _dt, timedelta as _td
        super().__init__(parent)
        self.setWindowTitle("Add Manual Session")
        self.setFixedWidth(360)
        self.setStyleSheet(
            f"background: {BG}; color: {TEXT};"
            f" QLabel {{ background: transparent; }}"
        )
        root = QVBoxLayout(self)
        root.setSpacing(PAD_SM)

        now = _dt.now().replace(second=0, microsecond=0)
        defaults = [("Start", "_start_edit", now - _td(hours=1)),
                    ("End",   "_end_edit",   now)]
        for lbl_text, attr, dt_val in defaults:
            root.addWidget(label(lbl_text, MUTED, size=10))
            edit = QDateTimeEdit()
            edit.setDisplayFormat("yyyy-MM-dd  HH:mm:ss")
            edit.setCalendarPopup(True)
            edit.setStyleSheet(_DT_CSS)
            from PyQt5.QtCore import QDateTime as _QDT, QDate as _QDate, QTime as _QTime
            edit.setDateTime(_QDT(
                _QDate(dt_val.year, dt_val.month, dt_val.day),
                _QTime(dt_val.hour, dt_val.minute, dt_val.second),
            ))
            setattr(self, attr, edit)
            root.addWidget(edit)

        root.addStretch()
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.setStyleSheet(f"color: {TEXT};")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    def _on_accept(self) -> None:
        if self._start_edit.dateTime() >= self._end_edit.dateTime():
            self._end_edit.setStyleSheet(
                _DT_CSS + f" QDateTimeEdit {{ border-color: {DANGER}; }}")
            return
        self.accept()

    def values(self):
        from datetime import datetime as _dt
        def _to_dt(qdt):
            d = qdt.date()
            t = qdt.time()
            return _dt(d.year(), d.month(), d.day(),
                       t.hour(), t.minute(), t.second())
        return _to_dt(self._start_edit.dateTime()), \
               _to_dt(self._end_edit.dateTime())


# ──────────────────────────────────────────────────────────
# Chart panel helper
# ──────────────────────────────────────────────────────────

def make_chart_panel(title: str, chart_widget: QWidget) -> "ChartPanel":
    """Wrap a chart widget in a titled ChartPanel."""
    pan = ChartPanel(title)
    pan.add_widget(chart_widget)
    return pan
