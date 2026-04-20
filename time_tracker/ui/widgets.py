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
    QDialog, QDialogButtonBox, QDateTimeEdit, QGraphicsOpacityEffect,
)
from PyQt5.QtCore import QDateTime

from .theme import (
    BG, BG2, BG3, BG4, BORDER, BORDER2,
    TEXT, DIM, MUTED, FAINT, ACCENT, ACCENT_DIM,
    SUCCESS, SUCCESS_DIM, WARNING, WARNING_DIM, DANGER, DANGER_DIM,
    FONT_UI, FONT_MONO, RADIUS, RADIUS_LG,
    PAD, PAD_MD, PAD_LG,
    PAD_XS, PAD_SM,  # backwards-compat
    SS,
)

# Re-export dialog classes so existing imports from widgets still work
from .dialogs.session_dialogs import EditSessionDialog, AddSessionDialog  # noqa: F401


# ──────────────────────────────────────────────────────────
# Primitive helpers
# ──────────────────────────────────────────────────────────

def _dim_effect(parent: QWidget, opacity: float = 0.4) -> QGraphicsOpacityEffect:
    eff = QGraphicsOpacityEffect(parent)
    eff.setOpacity(opacity)
    return eff

def h_line() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setFixedHeight(1)
    f.setStyleSheet(f"background: {BORDER}; border: none;")
    return f


def v_line() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.VLine)
    f.setFixedWidth(1)
    f.setStyleSheet(f"background: {BORDER}; border: none;")
    return f


def label(text: str, colour: str = TEXT, bold: bool = False,
          size: int = 11, mono: bool = False) -> QLabel:
    lbl = QLabel(text)
    w   = "600" if bold else "400"
    ff  = FONT_MONO if mono else FONT_UI
    lbl.setStyleSheet(
        f"color: {colour}; font-size: {size}px; font-weight: {w};"
        f" font-family: {ff}; background: transparent; border: none;"
    )
    return lbl


def section_label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(
        f"color: {MUTED}; font-size: 9px; font-family: {FONT_MONO};"
        f" letter-spacing: 1.2px; font-weight: 600; background: transparent;"
    )
    return lbl


def card_frame(parent=None) -> QFrame:
    f = QFrame(parent)
    f.setStyleSheet(
        f"QFrame {{ background: {BG2}; border-radius: {RADIUS_LG}px;"
        f" border: 1px solid {BORDER}; }}"
    )
    return f


# ──────────────────────────────────────────────────────────
# Panel widget  (titled container for charts / content)
# ──────────────────────────────────────────────────────────

class PanelWidget(QFrame):
    """Card-style container with a thin header bar and content body."""

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"PanelWidget {{ background: {BG2}; border-radius: {RADIUS_LG}px;"
            f" border: 1px solid {BORDER}; }}"
        )
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        if title:
            hdr = QFrame()
            hdr.setFixedHeight(26)
            hdr.setStyleSheet(
                f"QFrame {{ background: {BG3};"
                f" border-top-left-radius: {RADIUS_LG}px;"
                f" border-top-right-radius: {RADIUS_LG}px;"
                f" border: none; border-bottom: 1px solid {BORDER}; }}"
            )
            hl = QHBoxLayout(hdr)
            hl.setContentsMargins(PAD_MD, 0, PAD_MD, 0)
            hl.setSpacing(0)
            lbl = QLabel(title.upper())
            lbl.setStyleSheet(
                f"color: {MUTED}; font-size: 9px; font-family: {FONT_MONO};"
                f" letter-spacing: 1.0px; font-weight: 600; background: transparent;"
            )
            hl.addWidget(lbl)
            hl.addStretch()
            outer.addWidget(hdr)

        self._body = QVBoxLayout()
        self._body.setContentsMargins(0, 0, 0, 0)
        self._body.setSpacing(0)
        outer.addLayout(self._body)

    def add_widget(self, w: QWidget) -> None:
        self._body.addWidget(w)


# ──────────────────────────────────────────────────────────
# Metric card  (top of right panel, 4 across)
# ──────────────────────────────────────────────────────────

class MetricCard(QFrame):
    """KPI stat cell matching Quant Workstation StatCell design."""

    def __init__(self, title: str, big: bool = False,
                 right_border: bool = True, parent=None):
        super().__init__(parent)
        self._big = big
        val_size = 22 if big else 17
        self.setStyleSheet(
            f"QFrame {{ background: {BG2};"
            f" border: none;"
            + (f" border-right: 1px solid {BORDER};" if right_border else "")
            + f" }}"
        )
        self.setMinimumWidth(100)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(PAD_MD, PAD, PAD_MD, PAD)
        lay.setSpacing(2)

        self._title = QLabel(title.upper())
        self._title.setStyleSheet(
            f"color: {MUTED}; font-size: 9px; font-family: {FONT_MONO};"
            f" letter-spacing: 1.1px; font-weight: 600; background: transparent;"
        )
        self._value = QLabel("—")
        self._value.setStyleSheet(
            f"color: {TEXT}; font-size: {val_size}px; font-weight: 600;"
            f" font-family: {FONT_MONO}; letter-spacing: -0.2px;"
            f" background: transparent;"
        )
        self._sub = QLabel("")
        self._sub.setStyleSheet(
            f"color: {DIM}; font-size: 10px; font-family: {FONT_MONO};"
            f" background: transparent;"
        )

        lay.addWidget(self._title)
        lay.addWidget(self._value)
        lay.addWidget(self._sub)
        lay.addStretch()

    def update_value(self, value: str, sub: str = "",
                     colour: str = "") -> None:
        self._value.setText(value)
        val_size = 22 if self._big else 17
        _col = colour if colour else TEXT
        self._value.setStyleSheet(
            f"color: {_col}; font-size: {val_size}px; font-weight: 600;"
            f" font-family: {FONT_MONO}; letter-spacing: -0.2px;"
            f" background: transparent;"
        )
        self._sub.setText(sub)


# ──────────────────────────────────────────────────────────
# Insight strip  (row of small insight cards)
# ──────────────────────────────────────────────────────────

class InsightCard(QFrame):
    def __init__(self, icon: str, label_txt: str, value: str,
                 sub: str, sentiment: str, parent=None):
        super().__init__(parent)
        _colors = {
            "positive": (SUCCESS, SUCCESS_DIM),
            "warning":  (WARNING, WARNING_DIM),
            "negative": (DANGER,  DANGER_DIM),
            "neutral":  (MUTED,   BG3),
        }
        fg, bg = _colors.get(sentiment, (MUTED, BG3))
        self.setStyleSheet(
            f"QFrame {{ background: {bg}; border-radius: {RADIUS_LG}px;"
            f" border: 1px solid {BORDER}; }}"
        )
        self.setFixedHeight(72)
        self.setMinimumWidth(150)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(PAD_MD, PAD, PAD_MD, PAD)
        lay.setSpacing(2)

        top = QHBoxLayout()
        top.setSpacing(5)
        top.addWidget(label(icon, fg, size=13))
        top.addWidget(label(label_txt, MUTED, size=10))
        top.addStretch()
        lay.addLayout(top)

        lay.addWidget(label(value, fg, bold=True, size=15, mono=True))
        if sub:
            lay.addWidget(label(sub, MUTED, size=9, mono=True))


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
            if w := item.widget():
                w.hide()
                w.deleteLater()

        for ins in insights:
            card = InsightCard(ins.icon, ins.label, ins.value,
                               ins.sub, ins.sentiment)
            self._lay.insertWidget(self._lay.count() - 1, card)

        self.setVisible(len(insights) > 0)


# ──────────────────────────────────────────────────────────
# Chart panel  (titled container for QPainter charts)
# ──────────────────────────────────────────────────────────

class ChartPanel(QWidget):
    """Titled container for QPainter chart widgets. Uses PanelWidget styling."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        hdr = QFrame()
        hdr.setFixedHeight(30)
        hdr.setStyleSheet(
            f"QFrame {{ background: {BG3};"
            f" border-top-left-radius: {RADIUS_LG}px;"
            f" border-top-right-radius: {RADIUS_LG}px;"
            f" border: 1px solid {BORDER}; border-bottom: none; }}"
        )
        self._hl = QHBoxLayout(hdr)
        self._hl.setContentsMargins(PAD_MD, 4, PAD_MD, 4)
        ttl = QLabel(title.upper())
        ttl.setStyleSheet(
            f"color: {MUTED}; font-size: 9px; font-family: {FONT_MONO};"
            f" letter-spacing: 1.0px; font-weight: 600; background: transparent;"
        )
        self._hl.addWidget(ttl)
        self._hl.addStretch()
        outer.addWidget(hdr)

        self._content = QFrame()
        self._content.setStyleSheet(
            f"QFrame {{ background: {BG2};"
            f" border-bottom-left-radius: {RADIUS_LG}px;"
            f" border-bottom-right-radius: {RADIUS_LG}px;"
            f" border: 1px solid {BORDER}; border-top: none; }}"
        )
        cl = QVBoxLayout(self._content)
        cl.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._content)
        self._cl = cl

    def add_widget(self, w: QWidget) -> None:
        self._cl.addWidget(w)

    def add_header_widget(self, w: QWidget) -> None:
        """Append a widget to the right side of the panel header."""
        self._hl.addWidget(w)


# ──────────────────────────────────────────────────────────
# Resizable chart panel  (drag handle at bottom grows page)
# ──────────────────────────────────────────────────────────

class ResizableChartPanel(QWidget):
    """Chart panel whose height can be changed by dragging a handle at its bottom.

    Changing the height emits a geometry update that causes a parent
    QScrollArea (with setWidgetResizable=True) to grow the page, making
    the content scrollable rather than capping at window height.

    When *title* is empty the header bar is omitted and the panel acts as
    a transparent wrapper — useful for containing a horizontal QSplitter
    with two individually titled ChartPanels side by side.
    """

    _MIN_H = 80

    def __init__(self, title: str, default_height: int = 200, parent=None):
        super().__init__(parent)
        from PyQt5.QtCore import QEvent as _QEvent
        self._QEvent = _QEvent
        self.setMinimumHeight(self._MIN_H)
        self.setMaximumHeight(16_777_215)   # Qt QWIDGETSIZE_MAX

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        if title:
            hdr = QFrame()
            hdr.setFixedHeight(30)
            hdr.setStyleSheet(
                f"QFrame {{ background: {BG3};"
                f" border-top-left-radius: {RADIUS_LG}px;"
                f" border-top-right-radius: {RADIUS_LG}px;"
                f" border: 1px solid {BORDER}; border-bottom: none; }}"
            )
            self._hl = QHBoxLayout(hdr)
            self._hl.setContentsMargins(PAD_MD, 4, PAD_MD, 4)
            ttl = QLabel(title.upper())
            ttl.setStyleSheet(
                f"color: {MUTED}; font-size: 9px; font-family: {FONT_MONO};"
                f" letter-spacing: 1.0px; font-weight: 600; background: transparent;"
            )
            self._hl.addWidget(ttl)
            self._hl.addStretch()
            outer.addWidget(hdr)

            content = QFrame()
            content.setStyleSheet(
                f"QFrame {{ background: {BG2};"
                f" border-bottom-left-radius: {RADIUS_LG}px;"
                f" border-bottom-right-radius: {RADIUS_LG}px;"
                f" border: 1px solid {BORDER}; border-top: none; }}"
            )
            self._cl = QVBoxLayout(content)
            self._cl.setContentsMargins(0, 0, 0, 0)
            outer.addWidget(content, stretch=1)
        else:
            self._hl = None
            plain = QWidget()
            plain.setStyleSheet("background: transparent;")
            self._cl = QVBoxLayout(plain)
            self._cl.setContentsMargins(0, 0, 0, 0)
            outer.addWidget(plain, stretch=1)

        # Drag handle — thin strip at the very bottom
        self._handle = QFrame()
        self._handle.setObjectName("ResizeHandle")
        self._handle.setFixedHeight(6)
        self._handle.setCursor(Qt.SizeVerCursor)
        self._handle.setStyleSheet(
            f"QFrame#ResizeHandle {{ background: {BORDER}; border-radius: 3px; }}"
            f"QFrame#ResizeHandle:hover {{ background: {BORDER2}; }}"
        )
        self._handle.setAttribute(Qt.WA_Hover, True)
        self._handle.installEventFilter(self)
        outer.addWidget(self._handle)

        # Set height AFTER layout is built so the layout can calculate properly
        self.setFixedHeight(default_height)

        self._dragging = False
        self._drag_y   = 0
        self._drag_h   = 0

    def eventFilter(self, obj, event) -> bool:
        if obj is self._handle:
            t = event.type()
            if t == self._QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                self._dragging = True
                self._drag_y   = event.globalPos().y()
                self._drag_h   = self.height()
                return True
            if t == self._QEvent.MouseMove and self._dragging:
                dy    = event.globalPos().y() - self._drag_y
                new_h = max(self._MIN_H, self._drag_h + dy)
                self.setFixedHeight(new_h)
                return True
            if t == self._QEvent.MouseButtonRelease and self._dragging:
                self._dragging = False
                return True
        return super().eventFilter(obj, event)

    def add_widget(self, w: QWidget) -> None:
        self._cl.addWidget(w)

    def add_header_widget(self, w: QWidget) -> None:
        if self._hl is not None:
            self._hl.addWidget(w)


def make_resizable_chart_panel(
    title: str, chart_widget: QWidget, default_height: int = 220
) -> ResizableChartPanel:
    """Wrap a chart widget in a ResizableChartPanel."""
    pan = ResizableChartPanel(title, default_height=default_height)
    pan.add_widget(chart_widget)
    return pan


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
        header.setFixedHeight(30)
        header.setStyleSheet(
            f"QFrame {{ background: {BG3}; border-radius: {RADIUS}px;"
            f" border: 1px solid {BORDER}; }}"
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(PAD, 0, PAD, 0)
        hl.setSpacing(PAD)

        self._arrow = label("▾", MUTED, size=10)
        self._arrow.setFixedWidth(12)
        hl.addWidget(self._arrow)
        hl.addWidget(label(title, TEXT, bold=True, size=10))
        hl.addStretch()
        header.mousePressEvent = lambda _: self._toggle()
        outer.addWidget(header)

        self._content = QFrame()
        self._content.setStyleSheet(
            f"QFrame {{ background: {BG2}; border-radius: {RADIUS}px;"
            f" border: 1px solid {BORDER}; }}"
        )
        cl = QVBoxLayout(self._content)
        cl.setContentsMargins(PAD, PAD, PAD, PAD)
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
        lay.setSpacing(4)
        for display, key in zip(self.PRESETS, self.PRESET_KEYS):
            btn = QPushButton(display)
            btn.setFixedHeight(22)
            btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {MUTED};"
                f" border: 1px solid {BORDER}; border-radius: {RADIUS}px;"
                f" font-size: 10px; font-family: {FONT_UI}; padding: 0 7px; }}"
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
    archive_requested   = pyqtSignal(str, bool)   # name, archived
    clicked             = pyqtSignal(str)

    def __init__(self, task_name: str, colour: str,
                 total_sec: float = 0, max_sec: float = 1,
                 n_sessions: int = 0, clocked_in: bool = False,
                 elapsed_sec: float = 0, category_colour: str = "",
                 archived: bool = False,
                 parent=None):
        super().__init__(parent)
        self._name       = task_name
        self._colour     = colour
        self._clocked_in = clocked_in
        self._archived   = archived

        if archived:
            self.setGraphicsEffect(_dim_effect(self, opacity=0.45))

        self._update_row_style()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Active indicator bar (2px left border shown via wrapper)
        self._indicator = QFrame()
        self._indicator.setFixedWidth(2)
        self._indicator.setStyleSheet(
            f"background: {ACCENT if clocked_in else 'transparent'}; border: none;"
        )

        row_w = QWidget()
        row_w.setStyleSheet("background: transparent;")
        lay = QHBoxLayout(row_w)
        lay.setContentsMargins(14, 5, PAD_MD, 5)
        lay.setSpacing(PAD)

        # Dot
        dot = QLabel("●")
        dot.setStyleSheet(
            f"color: {colour}; font-size: 8px; background: transparent; border: none;"
        )
        dot.setFixedWidth(10)
        lay.addWidget(dot)

        # Name + sub-row (name + hours)
        name_col = QVBoxLayout()
        name_col.setContentsMargins(0, 0, 0, 0)
        name_col.setSpacing(1)
        self._name_lbl = QLabel(task_name)
        self._name_lbl.setStyleSheet(
            f"color: {TEXT}; font-size: 11px; font-family: {FONT_UI};"
            f" background: transparent; border: none;"
        )
        from ..core.models import fmt_dur
        self._hours_lbl = QLabel(fmt_dur(total_sec, short=True))
        self._hours_lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 9px; font-family: {FONT_MONO};"
            f" background: transparent; border: none;"
        )
        name_col.addWidget(self._name_lbl)
        name_col.addWidget(self._hours_lbl)
        lay.addLayout(name_col, stretch=1)

        # Progress bar (40×3px)
        self._bar = _MiniBar(total_sec, max_sec, colour)
        self._bar.setFixedWidth(40)
        self._bar.setFixedHeight(3)
        lay.addWidget(self._bar)

        # Elapsed (shown when clocked in — subtle, monospace)
        self._elapsed_lbl = QLabel()
        self._elapsed_lbl.setStyleSheet(
            f"color: {ACCENT}; font-size: 9px; font-family: {FONT_MONO};"
            f" background: transparent; border: none;"
        )
        self._elapsed_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._elapsed_lbl.setVisible(clocked_in)
        if clocked_in:
            self._elapsed_lbl.setText(fmt_dur(elapsed_sec, short=True))
        lay.addWidget(self._elapsed_lbl)

        # Clock button (compact ghost/danger style)
        self._btn = QPushButton()
        self._btn.setFixedSize(68, 22)
        self._update_btn()
        self._btn.clicked.connect(self._on_clock)
        lay.addWidget(self._btn)

        # Assemble with indicator
        hbox = QHBoxLayout()
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.setSpacing(0)
        hbox.addWidget(self._indicator)
        hbox.addWidget(row_w, stretch=1)
        outer.addLayout(hbox)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {BORDER}; border: none;")
        outer.addWidget(sep)

    def _update_row_style(self) -> None:
        self.setStyleSheet("TaskRow { background: transparent; }")

    def _update_btn(self) -> None:
        if self._clocked_in:
            self._btn.setText("Stop")
            self._btn.setStyleSheet(
                f"QPushButton {{ background: transparent; color: {DANGER};"
                f" border: 1px solid {DANGER}; border-radius: {RADIUS}px;"
                f" font-size: 10px; font-family: {FONT_UI}; }}"
                f" QPushButton:hover {{ background: {DANGER_DIM}; }}"
            )
        else:
            self._btn.setText("Clock In")
            self._btn.setStyleSheet(
                f"QPushButton {{ background: {ACCENT}; color: {BG};"
                f" border: 1px solid {ACCENT}; border-radius: {RADIUS}px;"
                f" font-size: 10px; font-family: {FONT_UI}; }}"
                f" QPushButton:hover {{ opacity: 0.85; }}"
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
        self._indicator.setStyleSheet(
            f"background: {ACCENT if state else 'transparent'}; border: none;"
        )
        self._update_btn()

    def mousePressEvent(self, e) -> None:
        # Left-click on the row (not on the clock button) opens the task tab
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self._name)
        super().mousePressEvent(e)

    def contextMenuEvent(self, e) -> None:
        menu = QMenu()
        menu.setStyleSheet(
            f"QMenu {{"
            f"  background: {BG3}; color: {TEXT};"
            f"  border: 1px solid {BORDER2}; border-radius: {RADIUS}px;"
            f"  padding: 4px 0; font-family: {FONT_UI};"
            f"}}"
            f"QMenu::item {{"
            f"  padding: 5px 14px; font-size: 11px;"
            f"  border-radius: {RADIUS}px; margin: 0 4px;"
            f"}}"
            f"QMenu::item:selected {{ background: {BG4}; color: {TEXT}; }}"
            f"QMenu::item:disabled {{ color: {FAINT}; }}"
            f"QMenu::separator {{ height: 1px; background: {BORDER}; margin: 3px 8px; }}"
        )
        menu.addAction("Rename…").triggered.connect(
            lambda: self.rename_requested.emit(self._name))
        menu.addAction("Move to category…").triggered.connect(
            lambda: self.move_requested.emit(self._name))
        menu.addSeparator()
        arch_label = "Unarchive" if self._archived else "Archive"
        arch_act = menu.addAction(arch_label)
        arch_act.triggered.connect(
            lambda: self.archive_requested.emit(self._name, not self._archived))
        menu.addSeparator()
        del_act = menu.addAction("Delete task…")
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

class _LogbookEntry(QWidget):
    """A single session card in the logbook view."""

    edit_requested   = pyqtSignal(int, object, object, str)
    delete_requested = pyqtSignal(int, bool)

    def __init__(self, session_id: int, is_open: bool,
                 start, end, dur_str: str, note: str = "", parent=None):
        super().__init__(parent)
        self._id      = session_id
        self._is_open = is_open
        self._start   = start
        self._end     = end
        self._note    = note

        self.setObjectName("LogEntry")
        self.setAttribute(Qt.WA_Hover, True)
        self.setStyleSheet(
            f"#LogEntry {{ background: {BG3}; border: 1px solid {BORDER};"
            f" border-radius: {RADIUS}px; }}"
            f"#LogEntry:hover {{ border-color: {BORDER2}; background: {BG4}; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(6)

        # Top row: time range + duration on left, action buttons on right
        top = QHBoxLayout()
        top.setSpacing(8)
        top.setContentsMargins(0, 0, 0, 0)

        end_str = end.strftime("%H:%M") if end else "now"
        status = " (active)" if is_open else ""
        time_lbl = QLabel(f"{start.strftime('%H:%M')} – {end_str}  ·  {dur_str}{status}")
        time_lbl.setStyleSheet(
            f"color: {TEXT}; font-size: 12px; font-family: {FONT_MONO};"
            f" background: transparent; border: none;"
        )
        top.addWidget(time_lbl, stretch=1)

        self._edit_btn = QPushButton("Edit")
        self._edit_btn.setFixedSize(46, 22)
        self._edit_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {MUTED};"
            f" border: 1px solid {BORDER}; border-radius: 4px; font-size: 10px; }}"
            f" QPushButton:hover {{ color: {TEXT}; background: {BG2}; border-color: {BORDER2}; }}"
        )
        self._edit_btn.setVisible(False)
        if not is_open:
            self._edit_btn.clicked.connect(
                lambda: self.edit_requested.emit(self._id, self._start, self._end, self._note)
            )
        top.addWidget(self._edit_btn)

        self._del_btn = QPushButton("×")
        self._del_btn.setFixedSize(26, 22)
        self._del_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {DANGER};"
            f" border: 1px solid {DANGER}; border-radius: 4px; font-size: 14px; }}"
            f" QPushButton:hover {{ background: {DANGER_DIM}; }}"
        )
        self._del_btn.setVisible(False)
        self._del_btn.clicked.connect(
            lambda: self.delete_requested.emit(self._id, self._is_open)
        )
        top.addWidget(self._del_btn)
        root.addLayout(top)

        # Note body — full multi-line display
        if note:
            note_lbl = QLabel(note)
            note_lbl.setWordWrap(True)
            note_lbl.setTextFormat(Qt.PlainText)
            note_lbl.setStyleSheet(
                f"color: {DIM}; font-size: 13px; font-family: {FONT_UI};"
                f" background: transparent; border: none;"
            )
            root.addWidget(note_lbl)

    def enterEvent(self, e) -> None:
        if not self._is_open:
            self._edit_btn.setVisible(True)
        self._del_btn.setVisible(True)
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        self._edit_btn.setVisible(False)
        self._del_btn.setVisible(False)
        super().leaveEvent(e)


def export_sessions_to_csv(rows: list, filename_hint: str, parent=None) -> None:
    """Open a save dialog and write session rows to CSV.

    rows: list of (date_str, start_str, end_str, duration_h, task_name, category, note)
    """
    import csv
    from PyQt5.QtWidgets import QFileDialog
    path, _ = QFileDialog.getSaveFileName(
        parent, "Export sessions", filename_hint, "CSV files (*.csv)"
    )
    if not path:
        return
    if not path.lower().endswith(".csv"):
        path += ".csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Date", "Start", "End", "Duration (h)", "Task", "Category", "Note"])
        w.writerows(rows)


class LogbookWidget(QWidget):
    """Scrollable logbook of session entries grouped by date.

    Signals
    -------
    edit_requested(int, object, object, str)  — session_id, start, end, note
    delete_requested(int, bool)               — session_id, is_open
    """

    edit_requested   = pyqtSignal(int, object, object, str)
    delete_requested = pyqtSignal(int, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(200)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(SS.scrollarea() + f" QScrollArea {{ background: {BG2}; }}")
        self._container = QWidget()
        self._container.setStyleSheet(f"background: {BG2};")
        self._list_lay = QVBoxLayout(self._container)
        self._list_lay.setContentsMargins(8, 8, 8, 8)
        self._list_lay.setSpacing(0)
        self._list_lay.addStretch()
        scroll.setWidget(self._container)
        root.addWidget(scroll)

        # Cached rows for CSV export: (date, start, end, dur_h, task, category, note)
        self._export_rows: list = []

    def refresh(self, task, start, end) -> None:
        from ..core.models import fmt_dur
        from collections import defaultdict

        while self._list_lay.count() > 1:
            item = self._list_lay.takeAt(0)
            if w := item.widget():
                w.hide()
                w.deleteLater()

        sessions = sorted(
            task.sessions_in_range(start, end),
            key=lambda s: s.start,
            reverse=True,
        )

        self._export_rows = []

        # Group by date
        by_date: dict = defaultdict(list)
        for s in sessions:
            by_date[s.date].append(s)

        insert_at = 0
        for d in sorted(by_date.keys(), reverse=True):
            # Date header
            day_lbl = QLabel(d.strftime("%A, %d %b %Y"))
            day_lbl.setStyleSheet(
                f"color: {MUTED}; font-size: 10px; font-family: {FONT_MONO};"
                f" letter-spacing: 0.5px; background: transparent; border: none;"
                f" padding: 12px 4px 4px 4px;"
            )
            self._list_lay.insertWidget(insert_at, day_lbl)
            insert_at += 1

            for s in sorted(by_date[d], key=lambda x: x.start, reverse=True):
                dur_str = fmt_dur(s.duration_seconds, short=True)
                entry = _LogbookEntry(
                    session_id=s.line_index,
                    is_open=s.is_open,
                    start=s.start,
                    end=s.end,
                    dur_str=dur_str,
                    note=s.note,
                    parent=self._container,
                )
                entry.edit_requested.connect(self.edit_requested)
                entry.delete_requested.connect(self.delete_requested)
                self._list_lay.insertWidget(insert_at, entry)
                insert_at += 1

                end_str = s.end.strftime("%H:%M") if s.end else ""
                self._export_rows.append((
                    d.strftime("%Y-%m-%d"),
                    s.start.strftime("%H:%M"),
                    end_str,
                    round(s.duration_seconds / 3600, 4),
                    task.name,
                    task.tag,
                    s.note,
                ))

            # Small spacer between date groups
            spacer = QWidget(self._container)
            spacer.setFixedHeight(4)
            self._list_lay.insertWidget(insert_at, spacer)
            insert_at += 1


# Keep old name as alias so any code using SessionTable still compiles
SessionTable = LogbookWidget


# ──────────────────────────────────────────────────────────
# Chart panel helper
# ──────────────────────────────────────────────────────────

def make_chart_panel(title: str, chart_widget: QWidget) -> "ChartPanel":
    """Wrap a chart widget in a titled ChartPanel."""
    pan = ChartPanel(title)
    pan.add_widget(chart_widget)
    return pan
