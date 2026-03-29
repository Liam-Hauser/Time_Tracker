"""
ui/widgets.py — Reusable PyQt5 widget components.
"""

from __future__ import annotations
from typing import Callable, Optional

from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt5.QtGui import QColor, QPainter, QFont, QPen, QBrush, QFontMetrics
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy, QSlider, QApplication, QScrollArea,
    QToolButton, QSplitter,
)

from .theme import (
    BG, BG2, BG3, BORDER, TEXT, MUTED, FAINT,
    ACCENT, SUCCESS, WARNING, DANGER,
    FONT_SM, FONT_MD, FONT_BOLD, FONT_LG, PAD_SM, PAD_MD, PAD_LG,
)


# ──────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────
def h_line() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet(f"color: {BORDER};")
    return f


def label(text: str, colour: str = TEXT, bold: bool = False,
          size: int = 11) -> QLabel:
    lbl = QLabel(text)
    w = "600" if bold else "400"
    lbl.setStyleSheet(
        f"color: {colour}; font-size: {size}px; font-weight: {w};"
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
# Stat card
# ──────────────────────────────────────────────────────────
class StatCard(QFrame):
    def __init__(self, title: str, value: str = "—",
                 sub: str = "", colour: str = TEXT, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame {{ background: {BG2}; border-radius: 8px;"
            f" border: 1px solid {BORDER}; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)

        self._title_lbl = label(title, MUTED, size=10)
        self._value_lbl = label(value, colour, bold=True, size=20)
        self._sub_lbl   = label(sub,   FAINT, size=10)

        layout.addWidget(self._title_lbl)
        layout.addWidget(self._value_lbl)
        layout.addWidget(self._sub_lbl)

    def update_value(self, value: str, sub: str = "",
                     colour: str = TEXT) -> None:
        self._value_lbl.setText(value)
        self._value_lbl.setStyleSheet(
            f"color: {colour}; font-size: 20px; font-weight: 600;"
        )
        self._sub_lbl.setText(sub)


# ──────────────────────────────────────────────────────────
# Collapsible section
# ──────────────────────────────────────────────────────────
class CollapsibleSection(QWidget):
    """A titled section that can be collapsed/expanded with a toggle button."""

    def __init__(self, title: str, compact: bool = False, parent=None):
        super().__init__(parent)
        self._expanded = True
        self._compact  = compact

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header bar
        header = QFrame()
        header.setStyleSheet(
            f"QFrame {{ background: {BG3}; border-radius: 6px;"
            f" border: 1px solid {BORDER}; }}"
        )
        h_layout = QHBoxLayout(header)
        pad = PAD_SM if compact else PAD_MD
        h_layout.setContentsMargins(pad, pad, pad, pad)

        self._toggle = QToolButton()
        self._toggle.setArrowType(Qt.DownArrow)
        self._toggle.setStyleSheet(
            f"QToolButton {{ background: transparent; border: none;"
            f" color: {MUTED}; }}"
        )
        self._toggle.clicked.connect(self._on_toggle)

        title_lbl = label(title, TEXT, bold=True, size=11)
        h_layout.addWidget(self._toggle)
        h_layout.addWidget(title_lbl)
        h_layout.addStretch()
        outer.addWidget(header)

        # Content container
        self._content = QWidget()
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, PAD_SM, 0, 0)
        content_layout.setSpacing(0)
        outer.addWidget(self._content)
        self._content_layout = content_layout

    def add_widget(self, w: QWidget) -> None:
        self._content_layout.addWidget(w)

    def _on_toggle(self) -> None:
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        self._toggle.setArrowType(
            Qt.DownArrow if self._expanded else Qt.RightArrow
        )


# ──────────────────────────────────────────────────────────
# Dual-handle range slider
# ──────────────────────────────────────────────────────────
class RangeSlider(QWidget):
    """
    A single-track slider with two draggable handles (low, high).
    Emits range_changed(low_index, high_index) on every change.
    """

    range_changed = pyqtSignal(int, int)

    HANDLE_R = 8   # radius in px
    TRACK_H  = 4

    def __init__(self, count: int = 100, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(32)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._count    = max(2, count)
        self._low      = 0
        self._high     = self._count - 1
        self._dragging: Optional[str] = None  # "low" | "high"

    # ── Public API ───────────────────────────────────────
    def set_count(self, n: int) -> None:
        self._count = max(2, n)
        self._low   = 0
        self._high  = self._count - 1
        self.update()

    def set_range(self, low: int, high: int) -> None:
        self._low  = max(0, min(low, self._count - 1))
        self._high = max(self._low, min(high, self._count - 1))
        self.update()

    @property
    def low(self) -> int:  return self._low
    @property
    def high(self) -> int: return self._high

    # ── Geometry helpers ─────────────────────────────────
    def _track_rect(self):
        r = self.HANDLE_R
        return (r, self.height() // 2 - self.TRACK_H // 2,
                self.width() - 2 * r, self.TRACK_H)

    def _idx_to_x(self, idx: int) -> int:
        tx, _, tw, _ = self._track_rect()
        return tx + int(idx / (self._count - 1) * tw)

    def _x_to_idx(self, x: int) -> int:
        tx, _, tw, _ = self._track_rect()
        pct = (x - tx) / max(1, tw)
        return max(0, min(self._count - 1, round(pct * (self._count - 1))))

    # ── Paint ─────────────────────────────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        tx, ty, tw, th = self._track_rect()
        cy = self.height() // 2

        # track background
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(BORDER))
        p.drawRoundedRect(tx, ty, tw, th, 2, 2)

        # active fill
        lx = self._idx_to_x(self._low)
        hx = self._idx_to_x(self._high)
        p.setBrush(QColor(ACCENT))
        p.drawRoundedRect(lx, ty, hx - lx, th, 2, 2)

        # handles
        p.setPen(QPen(QColor(BG), 2))
        p.setBrush(QColor(ACCENT))
        r = self.HANDLE_R
        for x in (lx, hx):
            p.drawEllipse(x - r, cy - r, 2 * r, 2 * r)

    # ── Mouse ─────────────────────────────────────────────
    def mousePressEvent(self, e):
        lx = self._idx_to_x(self._low)
        hx = self._idx_to_x(self._high)
        r  = self.HANDLE_R + 4
        if abs(e.x() - lx) <= r:
            self._dragging = "low"
        elif abs(e.x() - hx) <= r:
            self._dragging = "high"
        else:
            # snap nearest handle
            idx = self._x_to_idx(e.x())
            if abs(idx - self._low) <= abs(idx - self._high):
                self._low = max(0, min(idx, self._high))
            else:
                self._high = max(self._low, min(idx, self._count - 1))
            self.update()
            self.range_changed.emit(self._low, self._high)

    def mouseMoveEvent(self, e):
        if self._dragging is None:
            return
        idx = self._x_to_idx(e.x())
        if self._dragging == "low":
            self._low = max(0, min(idx, self._high))
        else:
            self._high = max(self._low, min(idx, self._count - 1))
        self.update()
        self.range_changed.emit(self._low, self._high)

    def mouseReleaseEvent(self, _):
        self._dragging = None


# ──────────────────────────────────────────────────────────
# Colour dot + label row
# ──────────────────────────────────────────────────────────
class TaskRow(QWidget):
    """Single task row: dot | name | bar | duration | sessions | clock btn."""

    clock_in_requested  = pyqtSignal(str)
    clock_out_requested = pyqtSignal(str)

    def __init__(self, task_name: str, colour: str,
                 total_sec: float = 0, max_sec: float = 1,
                 n_sessions: int = 0, clocked_in: bool = False,
                 elapsed_sec: float = 0, compact: bool = False,
                 parent=None):
        super().__init__(parent)
        self._name       = task_name
        self._colour     = colour
        self._clocked_in = clocked_in

        pad = PAD_SM if compact else PAD_MD
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, pad // 2, 0, pad // 2)
        layout.setSpacing(8)

        # Colour dot
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {colour}; font-size: 10px;")
        dot.setFixedWidth(14)
        layout.addWidget(dot)

        # Task name
        name_lbl = QLabel(task_name)
        name_lbl.setStyleSheet(f"color: {TEXT}; font-size: 11px;")
        name_lbl.setMinimumWidth(170)
        name_lbl.setMaximumWidth(220)
        layout.addWidget(name_lbl)

        # Progress bar (custom painted)
        self._bar = _MiniBar(total_sec, max_sec, colour)
        layout.addWidget(self._bar, stretch=1)

        # Duration label
        from ..core.models import fmt_dur
        self._dur_lbl = QLabel(fmt_dur(total_sec, short=True))
        self._dur_lbl.setStyleSheet(
            f"color: {TEXT}; font-size: 11px; font-weight: 600;"
            f" min-width: 64px;"
        )
        self._dur_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self._dur_lbl)

        # Session count
        sess_lbl = QLabel(f"{n_sessions} sess.")
        sess_lbl.setStyleSheet(f"color: {MUTED}; font-size: 10px; min-width: 48px;")
        sess_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(sess_lbl)

        # Clock elapsed (shown only when clocked in)
        self._elapsed_lbl = QLabel()
        self._elapsed_lbl.setStyleSheet(
            f"color: {SUCCESS}; font-size: 10px; min-width: 56px;"
        )
        self._elapsed_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._elapsed_lbl.setVisible(clocked_in)
        if clocked_in:
            self._elapsed_lbl.setText(fmt_dur(elapsed_sec, short=True))
        layout.addWidget(self._elapsed_lbl)

        # Clock button
        self._btn = QPushButton()
        self._btn.setFixedSize(72, 24)
        self._update_button()
        self._btn.clicked.connect(self._on_clock)
        layout.addWidget(self._btn)

        # Separator
        self.setStyleSheet(
            f"QWidget {{ border-bottom: 1px solid {BORDER}; }}"
        )

    def _update_button(self) -> None:
        if self._clocked_in:
            self._btn.setText("Clock Out")
            self._btn.setStyleSheet(
                f"QPushButton {{ background: {DANGER}; color: white;"
                f" border-radius: 4px; font-size: 10px; font-weight: 600; }}"
                f" QPushButton:hover {{ background: #c0392b; }}"
            )
        else:
            self._btn.setText("Clock In")
            self._btn.setStyleSheet(
                f"QPushButton {{ background: {SUCCESS}; color: white;"
                f" border-radius: 4px; font-size: 10px; font-weight: 600; }}"
                f" QPushButton:hover {{ background: #388E3C; }}"
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
        self._update_button()


class _MiniBar(QWidget):
    def __init__(self, value: float, maximum: float,
                 colour: str, parent=None):
        super().__init__(parent)
        self._value   = value
        self._maximum = max(1.0, maximum)
        self._colour  = colour
        self.setFixedHeight(6)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(BORDER))
        p.drawRoundedRect(0, 0, w, h, 3, 3)
        fill_w = int(w * min(1.0, self._value / self._maximum))
        if fill_w > 0:
            p.setBrush(QColor(self._colour))
            p.drawRoundedRect(0, 0, fill_w, h, 3, 3)


# ──────────────────────────────────────────────────────────
# Goal progress bar
# ──────────────────────────────────────────────────────────
class GoalBar(QWidget):
    """Thin colour-coded bar showing progress toward a goal."""

    def __init__(self, task_name: str, colour: str, parent=None):
        super().__init__(parent)
        self._colour = colour
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        layout.addWidget(label(task_name, TEXT, size=10))
        self._bar = _MiniBar(0, 1, colour)
        self._bar.setFixedHeight(8)
        layout.addWidget(self._bar, stretch=1)
        self._pct_lbl  = label("0%",  TEXT, size=10)
        self._eta_lbl  = label("",    MUTED, size=9)
        layout.addWidget(self._pct_lbl)
        layout.addWidget(self._eta_lbl)

    def update(self, progress: float, eta_days: Optional[float],
               goal_hours: float) -> None:  # type: ignore[override]
        self._bar._value   = progress
        self._bar._maximum = 1.0
        self._bar.update()
        pct_int = int(progress * 100)
        colour  = SUCCESS if pct_int >= 80 else (WARNING if pct_int >= 40 else DANGER)
        self._pct_lbl.setText(f"{pct_int}%")
        self._pct_lbl.setStyleSheet(
            f"color: {colour}; font-size: 10px;"
        )
        if eta_days is not None:
            self._eta_lbl.setText(f"~{eta_days:.0f} d left")
        else:
            self._eta_lbl.setText(f"goal: {goal_hours:.0f}h")


# ──────────────────────────────────────────────────────────
# Preset date-range buttons
# ──────────────────────────────────────────────────────────
class PresetBar(QWidget):
    preset_selected = pyqtSignal(str)

    PRESETS = ["Last 7d", "Last 30d", "This month", "Last month",
               "This week", "Last week", "All"]

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(label("Quick:", MUTED, size=10))
        for p in self.PRESETS:
            btn = QPushButton(p)
            btn.setFixedHeight(22)
            btn.setStyleSheet(
                f"QPushButton {{ background: {BG3}; color: {MUTED};"
                f" border: 1px solid {BORDER}; border-radius: 4px;"
                f" font-size: 10px; padding: 0 8px; }}"
                f" QPushButton:hover {{ color: {TEXT}; }}"
            )
            btn.clicked.connect(lambda _, preset=p: self.preset_selected.emit(preset))
            layout.addWidget(btn)
        layout.addStretch()
