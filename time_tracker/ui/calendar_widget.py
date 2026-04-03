"""
ui/calendar_widget.py — Calendar tab.

Layout:
  1. ContributionGraph  — 52-week heat map, percentile-based colours, no title.
  2. Week navigation bar.
  3. WeekGridWidget     — QGraphicsView with a 7-column timeline.
                          Session blocks are QGraphicsObject items (proper hover,
                          precise font-metrics text, no overlap).
                          Sticky header + time labels drawn in drawForeground.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

from PyQt5.QtCore import (
    Qt, QTimer, pyqtSignal,
    QRect, QRectF, QPointF, QSize,
    QDateTime, QDate, QTime,
)
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QFont, QFontMetrics, QBrush, QPainterPath,
)
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSizePolicy,
    QPushButton, QFrame, QLabel,
    QGraphicsView, QGraphicsScene, QGraphicsObject,
    QToolTip, QDialog, QDialogButtonBox, QComboBox,
    QDateTimeEdit, QMessageBox,
)

from ..core.models import Task, Session, fmt_dur
from ..core.parser import ParseResult
from ..core.db_store import DBStore
from .theme import (
    BG, BG2, BG3, BG4, BORDER, BORDER2,
    TEXT, MUTED, FAINT, ACCENT,
    DANGER,
    PAD_SM, PAD_MD, PAD_LG,
)
from .widgets import label, EditSessionDialog


# ─────────────────────────────────────────────────────────────────────────────
# Shared CSS snippets
# ─────────────────────────────────────────────────────────────────────────────

_COMBO_CSS = (
    f"QComboBox {{ background: {BG3}; color: {TEXT};"
    f" border: 1px solid {BORDER}; border-radius: 5px;"
    f" padding: 4px 10px; font-size: 11px; }}"
    f" QComboBox::drop-down {{ border: none; }}"
    f" QComboBox QAbstractItemView {{ background: {BG2}; color: {TEXT};"
    f" selection-background-color: {ACCENT}; }}"
)
_DT_CSS = (
    f"QDateTimeEdit {{ background: {BG3}; color: {TEXT};"
    f" border: 1px solid {BORDER}; border-radius: 5px;"
    f" padding: 4px 8px; font-size: 11px; }}"
    f" QDateTimeEdit:focus {{ border-color: {ACCENT}; }}"
)
_BTN_CSS = (
    f"QPushButton {{ background: transparent; color: {MUTED};"
    f" border: 1px solid {BORDER}; border-radius: 4px;"
    f" font-size: 10px; padding: 0 8px; }}"
    f" QPushButton:hover {{ color: {TEXT}; background: {BG4};"
    f" border-color: {BORDER2}; }}"
)


# ─────────────────────────────────────────────────────────────────────────────
# Heat-map: percentile colouring
# ─────────────────────────────────────────────────────────────────────────────

_MONTH_NAMES = [
    "Jan","Feb","Mar","Apr","May","Jun",
    "Jul","Aug","Sep","Oct","Nov","Dec",
]
_DAY_SHORT = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

_HEAT = [
    "#1c1c1c",  # 0 — no data
    "#0d3320",  # 1 — bottom 20 %
    "#145a32",  # 2
    "#1e8449",  # 3
    "#27ae60",  # 4
    "#2ecc71",  # 5 — top 10 %
]
# Cell geometry for contribution graph
_CELL, _GAP  = 12, 2
_STEP        = _CELL + _GAP
_WEEKS       = 53
_CG_LEFT     = 32   # room for day labels
_CG_TOP      = 18   # room for month labels


def _percentile_colours(total_by_day: dict[date, float]) -> dict[date, str]:
    """Returns only non-zero days; zero/missing days are rendered with BG3 in paintEvent."""
    non_zero = sorted(v for v in total_by_day.values() if v > 0)
    if not non_zero:
        return {}
    n = len(non_zero)
    out: dict[date, str] = {}
    for d, secs in total_by_day.items():
        if secs <= 0:
            continue   # handled in paintEvent using current BG3
        rank = sum(1 for v in non_zero if v <= secs) / n
        out[d] = (_HEAT[5] if rank >= 0.90 else
                  _HEAT[4] if rank >= 0.70 else
                  _HEAT[3] if rank >= 0.40 else
                  _HEAT[2] if rank >= 0.20 else _HEAT[1])
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 1. Contribution graph (unchanged, no title)
# ─────────────────────────────────────────────────────────────────────────────

class ContributionGraph(QWidget):
    day_clicked = pyqtSignal(object)   # Python date

    _MARGIN = 16   # horizontal margin on each side

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hours:   dict[date, float] = {}
        self._colours: dict[date, str]   = {}
        self._hovered: Optional[date]    = None
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _dyn_step(self) -> int:
        """Cell step (cell+gap) sized to fill widget width, capped 12–22 px."""
        avail = self.width() - _CG_LEFT - self._MARGIN * 2
        step = max(_STEP, min(avail // _WEEKS, 22))
        return step

    def sizeHint(self):
        step = self._dyn_step()
        return QSize(_CG_LEFT + _WEEKS * step + self._MARGIN * 2,
                     _CG_TOP + 7 * step + 8)

    def minimumSizeHint(self):
        return self.sizeHint()

    def refresh(self, total_by_day: dict[date, float]) -> None:
        self._hours   = {d: s / 3600 for d, s in total_by_day.items()}
        self._colours = _percentile_colours(total_by_day)
        self.update()

    def _grid_start(self) -> date:
        today = date.today()
        return (today - timedelta(days=today.weekday())) - timedelta(weeks=52)

    def _cell_rect(self, w: int, dow: int) -> QRect:
        step = self._dyn_step()
        cell = step - 2
        ox = self._MARGIN
        return QRect(_CG_LEFT + ox + w * step, _CG_TOP + dow * step, cell, cell)

    def _pos_to_date(self, x: int, y: int) -> Optional[date]:
        step = self._dyn_step()
        ox = self._MARGIN
        col = (x - _CG_LEFT - ox) // step
        row = (y - _CG_TOP)        // step
        if 0 <= col < _WEEKS and 0 <= row < 7:
            d = self._grid_start() + timedelta(weeks=col, days=row)
            if d <= date.today():
                return d
        return None

    def paintEvent(self, _):
        p     = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        start = self._grid_start()
        today = date.today()
        step  = self._dyn_step()
        ox    = self._MARGIN

        # Update height to match dynamic step
        new_h = _CG_TOP + 7 * step + 8
        if self.height() != new_h:
            self.setFixedHeight(new_h)

        p.setFont(QFont("", 8))
        p.setPen(QColor(MUTED))
        last_mo = -1
        for w in range(_WEEKS):
            d = start + timedelta(weeks=w)
            if d.month != last_mo:
                last_mo = d.month
                p.drawText(_CG_LEFT + ox + w * step, _CG_TOP - 3,
                           _MONTH_NAMES[d.month - 1])

        for dow in (0, 2, 4):
            p.drawText(ox, _CG_TOP + dow * step + step - 4,
                       _DAY_SHORT[dow][:3])

        for w in range(_WEEKS):
            for dow in range(7):
                d = start + timedelta(weeks=w, days=dow)
                if d > today:
                    continue
                rc = self._cell_rect(w, dow)
                p.setBrush(QColor(self._colours.get(d, BG3)))
                p.setPen(QPen(QColor(TEXT), 1)
                         if d == self._hovered else Qt.NoPen)
                p.drawRoundedRect(rc, 2, 2)
        p.end()

    def mouseMoveEvent(self, e):
        d = self._pos_to_date(e.x(), e.y())
        if d != self._hovered:
            self._hovered = d; self.update()
        if d:
            QToolTip.showText(e.globalPos(),
                f"{d.strftime('%A, %d %b %Y')}  ·  "
                f"{self._hours.get(d, 0.0):.1f} h", self)
        else:
            QToolTip.hideText()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            d = self._pos_to_date(e.x(), e.y())
            if d:
                self.day_clicked.emit(d)

    def leaveEvent(self, _):
        self._hovered = None; self.update()


# ─────────────────────────────────────────────────────────────────────────────
# 2. "Add session" dialog with task picker
# ─────────────────────────────────────────────────────────────────────────────

class _CalendarAddSessionDialog(QDialog):
    def __init__(self, day: date, tasks: list[Task],
                 preset_start: Optional[datetime] = None,
                 preset_end:   Optional[datetime] = None,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Session")
        self.setFixedWidth(400)
        self.setStyleSheet(f"background: {BG}; color: {TEXT};"
                           f" QLabel {{ background: transparent; }}")
        root = QVBoxLayout(self)
        root.setSpacing(PAD_SM)

        root.addWidget(label("Task", MUTED, size=10))
        self._combo = QComboBox()
        self._combo.setStyleSheet(_COMBO_CSS)
        for t in tasks:
            self._combo.addItem(f"● {t.name}", userData=t.start_line)
            self._combo.setItemData(self._combo.count() - 1,
                                    QColor(t.colour), Qt.ForegroundRole)
        root.addWidget(self._combo)

        ds = preset_start or datetime(day.year, day.month, day.day, 9, 0)
        de = preset_end   or datetime(day.year, day.month, day.day, 10, 0)
        for txt, attr, val in [("Start","_s",ds), ("End","_e",de)]:
            root.addWidget(label(txt, MUTED, size=10))
            w = QDateTimeEdit()
            w.setDisplayFormat("yyyy-MM-dd  HH:mm")
            w.setCalendarPopup(True)
            w.setStyleSheet(_DT_CSS)
            w.setDateTime(QDateTime(QDate(val.year, val.month, val.day),
                                    QTime(val.hour, val.minute, 0)))
            setattr(self, attr, w)
            root.addWidget(w)

        root.addStretch()
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.setStyleSheet(f"color: {TEXT};")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    def _on_accept(self) -> None:
        if self._s.dateTime() >= self._e.dateTime():
            self._e.setStyleSheet(
                _DT_CSS + f" QDateTimeEdit {{ border-color: {DANGER}; }}")
            return
        self.accept()

    def values(self) -> tuple[int, datetime, datetime]:
        def _dt(q):
            d, t = q.date(), q.time()
            return datetime(d.year(), d.month(), d.day(),
                            t.hour(), t.minute(), t.second())
        return self._combo.currentData(), _dt(self._s), _dt(self._e)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Session block — QGraphicsObject (proper hover + font-metrics text)
# ─────────────────────────────────────────────────────────────────────────────

_PX_H   = 64     # pixels per hour
_T_COL  = 58     # time-label column width
_HDR_H  = 40     # sticky header height
_MIN_H  = 4      # min block height px
_DEL_W  = 18     # delete-button width
_DEL_H  = 14     # delete-button height


class _SessionItem(QGraphicsObject):
    """A session block — handles its own hover, paint and click dispatch."""

    edit_clicked   = pyqtSignal(object)   # Session
    delete_clicked = pyqtSignal(object)   # Session

    # Fonts (class-level so metrics are computed once)
    _F_NAME = QFont("", 8, QFont.Bold)
    _F_TIME = QFont("", 7)

    def __init__(self, w: float, h: float,
                 sess: Session, name: str, colour: str):
        super().__init__()
        self._w     = w
        self._h     = max(float(_MIN_H), h)
        self._sess  = sess
        self._name  = name
        self._base  = QColor(colour)
        self._hover = False
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setZValue(1)

    # ── Geometry ─────────────────────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._w, self._h)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRoundedRect(self.boundingRect(), 4, 4)
        return path

    def _del_zone(self) -> QRectF:
        return QRectF(self._w - _DEL_W - 2, 2, _DEL_W, _DEL_H)

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paint(self, p: QPainter, option, widget) -> None:
        rc  = self.boundingRect()
        h   = self._h

        # Background
        fill = self._base.lighter(118) if self._hover else self._base
        p.setBrush(QBrush(fill))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(rc, 4, 4)

        # Left accent stripe
        p.fillRect(QRectF(0, 0, 3, h), self._base.darker(160))

        if h < _MIN_H + 4:
            return

        # ── Text ─────────────────────────────────────────────────────────
        PAD_L    = 7
        PAD_T    = 4
        # Reduce text width when delete button is visible
        avail_w  = self._w - PAD_L - (_DEL_W + 6 if self._hover else 4)

        if avail_w < 16:
            return

        fm_name = QFontMetrics(self._F_NAME)
        fm_time = QFontMetrics(self._F_TIME)

        name_h  = fm_name.height()   # ascent + descent
        time_h  = fm_time.height()

        # Task name
        if h >= PAD_T + name_h:
            p.setPen(QColor("#ffffff"))
            p.setFont(self._F_NAME)
            elided = fm_name.elidedText(self._name, Qt.ElideRight, int(avail_w))
            # drawText baseline = PAD_T + ascent
            p.drawText(QPointF(PAD_L, PAD_T + fm_name.ascent()), elided)

            # Time + duration — only when the block is tall enough to fit both
            time_top = PAD_T + name_h + 3   # 3 px gap below name
            if h >= time_top + time_h:
                if self._sess.end:
                    txt = (f"{self._sess.start.strftime('%H:%M')} – "
                           f"{self._sess.end.strftime('%H:%M')}"
                           f"  ·  {fmt_dur(self._sess.duration_seconds, short=True)}")
                else:
                    txt = (f"{self._sess.start.strftime('%H:%M')} – now"
                           f"  ·  {fmt_dur(self._sess.duration_seconds, short=True)}")
                p.setFont(self._F_TIME)
                p.setPen(QColor(220, 220, 220, 180))
                p.drawText(
                    QPointF(PAD_L, time_top + fm_time.ascent()),
                    fm_time.elidedText(txt, Qt.ElideRight, int(avail_w)),
                )

        # ── Hover: delete button ──────────────────────────────────────────
        if self._hover:
            dr = self._del_zone()
            p.setBrush(QColor(DANGER))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(dr, 3, 3)
            p.setPen(QColor("#ffffff"))
            p.setFont(QFont("", 7, QFont.Bold))
            p.drawText(dr.toRect(), Qt.AlignCenter, "✕")

    # ── Events ────────────────────────────────────────────────────────────────

    def hoverEnterEvent(self, e):
        self._hover = True;  self.update()

    def hoverLeaveEvent(self, e):
        self._hover = False; self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            if self._del_zone().contains(e.pos()):
                self.delete_clicked.emit(self._sess)
            else:
                self.edit_clicked.emit(self._sess)
            e.accept()
        else:
            super().mousePressEvent(e)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Week grid — QGraphicsView
# ─────────────────────────────────────────────────────────────────────────────

class WeekGridWidget(QGraphicsView):
    """7-column week timeline built on QGraphicsView.

    * Session blocks are _SessionItem instances (proper scene items).
    * drawBackground  — scrollable time grid (hour lines, column fills).
    * drawForeground  — sticky day header + sticky time labels (resetTransform).
    * mousePressEvent — empty-space click → add_requested.
    """

    edit_requested   = pyqtSignal(object)        # Session
    delete_requested = pyqtSignal(object)        # Session
    add_requested    = pyqtSignal(object, float) # (date, start_hour_float)

    _SCENE_H = _HDR_H + 24 * _PX_H

    def __init__(self, parent=None):
        super().__init__(QGraphicsScene(), parent)
        self._monday: date         = self._this_monday()
        self._day_sessions: dict[date, list[tuple[Session, str, str]]] = {}
        self._session_items: list[_SessionItem] = []
        self._time_items:    list              = []   # current-time line + dot

        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        self.setBackgroundBrush(QBrush(QColor(BG)))
        self.viewport().setCursor(Qt.CrossCursor)
        self.setStyleSheet(
            f"QScrollBar:vertical {{ background: {BG2}; width: 6px; border: none; }}"
            f"QScrollBar::handle:vertical {{ background: {BORDER2};"
            f" border-radius: 3px; min-height: 20px; }}"
            f"QScrollBar::add-line:vertical,"
            f"QScrollBar::sub-line:vertical {{ height: 0; }}"
        )

        # Refresh current-time indicator every 60 s
        self._tick = QTimer(self)
        self._tick.timeout.connect(self._refresh_time_line)
        self._tick.start(60_000)

    # ── Public ───────────────────────────────────────────────────────────────

    @staticmethod
    def _this_monday() -> date:
        today = date.today()
        return today - timedelta(days=today.weekday())

    def set_week(self, monday: date) -> None:
        self._monday = monday - timedelta(days=monday.weekday())
        self._rebuild()

    def refresh(self, tasks: list[Task]) -> None:
        ds: dict[date, list] = {}
        for t in tasks:
            for s in t.sessions:
                d = s.start.date()
                ds.setdefault(d, []).append((s, t.name, t.colour))
        for d in ds:
            ds[d].sort(key=lambda x: x[0].start)
        self._day_sessions = ds
        self._rebuild()

    def scroll_to_hour(self, hour: int) -> None:
        y = _HDR_H + max(0, hour - 1) * _PX_H
        self.verticalScrollBar().setValue(y)

    # ── Layout helpers ────────────────────────────────────────────────────────

    def _col_w(self) -> float:
        return max(1.0, (self.viewport().width() - _T_COL) / 7.0)

    def _col_x(self, col: int) -> float:
        return _T_COL + col * self._col_w()

    def _hour_y(self, h: float) -> float:
        return _HDR_H + h * _PX_H

    # ── Build / rebuild ───────────────────────────────────────────────────────

    def _rebuild(self) -> None:
        sc = self.scene()

        # Remove old session items
        for item in self._session_items:
            sc.removeItem(item)
        self._session_items.clear()

        # Update scene rect to match viewport
        vw = float(max(1, self.viewport().width()))
        sc.setSceneRect(0, 0, vw, float(self._SCENE_H))

        cw = self._col_w()

        # Add session items for the current week
        for col in range(7):
            d = self._monday + timedelta(days=col)
            for sess, tname, tcol in self._day_sessions.get(d, []):
                sh  = (sess.start.hour
                       + sess.start.minute / 60.0
                       + sess.start.second / 3600.0)
                dh  = sess.duration.total_seconds() / 3600.0
                x   = self._col_x(col) + 2
                y   = self._hour_y(sh)
                bw  = max(4.0, cw - 4)
                bh  = max(float(_MIN_H), dh * _PX_H)

                item = _SessionItem(bw, bh, sess, tname, tcol)
                item.setPos(x, y)
                item.edit_clicked.connect(self.edit_requested)
                item.delete_clicked.connect(self.delete_requested)
                sc.addItem(item)
                self._session_items.append(item)

        self._refresh_time_line()
        sc.update()

    def _refresh_time_line(self) -> None:
        sc = self.scene()
        for item in self._time_items:
            sc.removeItem(item)
        self._time_items.clear()

        now = datetime.now()
        if not (self._monday <= now.date()
                <= self._monday + timedelta(days=6)):
            return

        col    = now.date().weekday()
        hour_f = now.hour + now.minute / 60.0
        y      = self._hour_y(hour_f)
        x0     = self._col_x(col)
        x1     = x0 + self._col_w()

        pen  = QPen(QColor(DANGER), 2)
        line = sc.addLine(x0, y, x1, y, pen)
        dot  = sc.addEllipse(x0 - 4, y - 4, 8, 8,
                             QPen(Qt.NoPen), QBrush(QColor(DANGER)))
        for obj in (line, dot):
            obj.setZValue(2)
            obj.setAcceptedMouseButtons(Qt.NoButton)
        self._time_items = [line, dot]

    # ── Drawing ───────────────────────────────────────────────────────────────

    def drawBackground(self, p: QPainter, rect: QRectF) -> None:
        """Scrollable grid: column fills + hour lines + column separators."""
        today = date.today()
        cw    = self._col_w()
        sw    = self.scene().width()

        # Column fills
        for col in range(7):
            d  = self._monday + timedelta(days=col)
            x  = self._col_x(col)
            bg = QColor(BG4) if d == today else QColor(BG2)
            p.fillRect(QRectF(x, _HDR_H, cw, self._SCENE_H - _HDR_H), bg)

        # Hour lines (full)
        for hour in range(25):
            y   = self._hour_y(hour)
            pen = QPen(QColor(BORDER2 if hour % 6 == 0 else BORDER), 1)
            p.setPen(pen)
            p.drawLine(QPointF(_T_COL, y), QPointF(sw, y))

        # Half-hour lines (dotted)
        p.setPen(QPen(QColor(FAINT), 1, Qt.DotLine))
        for hour in range(24):
            y = self._hour_y(hour + 0.5)
            p.drawLine(QPointF(_T_COL, y), QPointF(sw, y))

        # Column separators
        p.setPen(QPen(QColor(BORDER), 1))
        for col in range(8):
            x = self._col_x(col)
            p.drawLine(QPointF(x, 0), QPointF(x, self._SCENE_H))

    def drawForeground(self, p: QPainter, rect: QRectF) -> None:
        """Sticky overlays (viewport coords) via resetTransform."""
        p.save()
        p.resetTransform()
        p.setRenderHint(QPainter.TextAntialiasing)

        vw  = self.viewport().width()
        vh  = self.viewport().height()
        sv  = self.verticalScrollBar().value()   # scroll offset in scene px
        cw  = self._col_w()
        today = date.today()

        # ── Day header strip ──────────────────────────────────────────────
        p.fillRect(QRect(0, 0, vw, _HDR_H), QColor(BG3))
        p.setPen(QPen(QColor(BORDER), 1))
        p.drawLine(0, _HDR_H, vw, _HDR_H)

        for col in range(7):
            d        = self._monday + timedelta(days=col)
            x        = int(self._col_x(col))
            cw_i     = int(cw)
            is_today = (d == today)

            # Day abbreviation
            p.setFont(QFont("", 8, QFont.Bold if is_today else QFont.Normal))
            p.setPen(QColor(ACCENT if is_today else MUTED))
            p.drawText(QRect(x, 4, cw_i, 14), Qt.AlignCenter,
                       _DAY_SHORT[col].upper())

            # Day number — circle for today
            num = str(d.day)
            num_rect = QRect(x, _HDR_H - 20, cw_i, 18)
            if is_today:
                cx = x + cw_i // 2
                cy = _HDR_H - 11
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(ACCENT))
                p.drawEllipse(cx - 9, cy - 7, 18, 16)
                p.setPen(QColor("#ffffff"))
                p.setBrush(Qt.NoBrush)
            else:
                p.setPen(QColor(TEXT))
            p.setFont(QFont("", 9, QFont.Bold if is_today else QFont.Normal))
            p.drawText(num_rect, Qt.AlignCenter, num)

        # ── Time-label column ─────────────────────────────────────────────
        # Draw over the scrolled content
        p.setRenderHint(QPainter.Antialiasing, False)
        p.fillRect(QRect(0, _HDR_H, _T_COL, vh - _HDR_H), QColor(BG))
        p.setFont(QFont("", 8))
        p.setPen(QColor(FAINT))

        for hour in range(1, 24):
            scene_y = int(self._hour_y(hour))
            vy      = scene_y - sv              # viewport y (no-zoom)
            if _HDR_H <= vy <= vh - 8:
                p.drawText(
                    QRect(6, vy - 7, _T_COL - 10, 14),
                    Qt.AlignRight | Qt.AlignVCenter,
                    f"{hour:02d}:00",
                )

        # ── Top-left corner (covers both overlays) ────────────────────────
        p.fillRect(QRect(0, 0, _T_COL, _HDR_H), QColor(BG3))

        p.restore()

    # ── Qt events ────────────────────────────────────────────────────────────

    def resizeEvent(self, e):
        super().resizeEvent(e)
        vw = float(max(1, self.viewport().width()))
        self.scene().setSceneRect(0, 0, vw, float(self._SCENE_H))
        self._rebuild()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            item = self.itemAt(e.pos())
            if not isinstance(item, _SessionItem):
                sp = self.mapToScene(e.pos())
                if sp.x() >= _T_COL and sp.y() >= _HDR_H:
                    col = int((sp.x() - _T_COL) / self._col_w())
                    if 0 <= col < 7:
                        d      = self._monday + timedelta(days=col)
                        hour_f = (sp.y() - _HDR_H) / _PX_H
                        self.add_requested.emit(d, hour_f)
                        return
        super().mousePressEvent(e)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Top-level CalendarWidget
# ─────────────────────────────────────────────────────────────────────────────

class CalendarWidget(QWidget):
    """Calendar tab: contribution strip + week timeline."""

    reload_needed = pyqtSignal()

    def __init__(self, store: DBStore, parent=None):
        super().__init__(parent)
        self._store   = store
        self._result: Optional[ParseResult] = None
        self._monday  = WeekGridWidget._this_monday()
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Contribution graph (no title) ──────────────────────────────
        strip = QFrame()
        strip.setStyleSheet(
            f"QFrame {{ background: {BG2};"
            f" border-bottom: 1px solid {BORDER}; }}"
        )
        sl = QVBoxLayout(strip)
        sl.setContentsMargins(0, PAD_SM, 0, PAD_SM)
        sl.setSpacing(0)
        self._contrib = ContributionGraph()
        self._contrib.day_clicked.connect(self._on_contrib_click)
        sl.addWidget(self._contrib)
        outer.addWidget(strip)

        # ── Week navigation bar ────────────────────────────────────────
        nav = QFrame()
        nav.setFixedHeight(42)
        nav.setStyleSheet(
            f"QFrame {{ background: {BG3};"
            f" border-bottom: 1px solid {BORDER}; }}"
        )
        nl = QHBoxLayout(nav)
        nl.setContentsMargins(PAD_LG, 0, PAD_MD, 0)
        nl.setSpacing(PAD_SM)
        prev_btn = self._mk_nav_btn("‹")
        prev_btn.clicked.connect(self._prev_week)
        nl.addWidget(prev_btn)
        self._week_lbl = QLabel(self._week_str())
        self._week_lbl.setStyleSheet(
            f"color: {TEXT}; font-size: 13px; font-weight: 600;"
            f" background: transparent; border: none; min-width: 220px;"
        )
        nl.addWidget(self._week_lbl)
        nl.addStretch()
        tw_btn = QPushButton("This week")
        tw_btn.setFixedHeight(26)
        tw_btn.setStyleSheet(_BTN_CSS)
        tw_btn.clicked.connect(self._go_this_week)
        nl.addWidget(tw_btn)
        next_btn = self._mk_nav_btn("›")
        next_btn.clicked.connect(self._next_week)
        nl.addWidget(next_btn)
        outer.addWidget(nav)

        # ── Week grid (QGraphicsView handles its own scrolling) ────────
        self._grid = WeekGridWidget()
        self._grid.edit_requested.connect(self._on_edit)
        self._grid.delete_requested.connect(self._on_delete)
        self._grid.add_requested.connect(self._on_add)
        outer.addWidget(self._grid, stretch=1)

        QTimer.singleShot(120, lambda: self._grid.scroll_to_hour(
            datetime.now().hour))

    # ── Public ────────────────────────────────────────────────────────────

    def refresh(self, result: ParseResult) -> None:
        self._result = result
        tbd: dict[date, float] = defaultdict(float)
        for t in result.tasks:
            for s in t.sessions:
                tbd[s.start.date()] += s.duration_seconds
        self._contrib.refresh(dict(tbd))
        self._grid.refresh(result.tasks)

    # ── Navigation ────────────────────────────────────────────────────────

    def _week_str(self) -> str:
        end = self._monday + timedelta(days=6)
        if self._monday.month == end.month:
            return f"{self._monday.strftime('%d')} – {end.strftime('%d %b %Y')}"
        return (f"{self._monday.strftime('%d %b')} – "
                f"{end.strftime('%d %b %Y')}")

    def _update_week_label(self) -> None:
        self._week_lbl.setText(self._week_str())

    def _prev_week(self) -> None:
        self._monday -= timedelta(weeks=1)
        self._grid.set_week(self._monday)
        self._update_week_label()

    def _next_week(self) -> None:
        self._monday += timedelta(weeks=1)
        self._grid.set_week(self._monday)
        self._update_week_label()

    def _go_this_week(self) -> None:
        self._monday = WeekGridWidget._this_monday()
        self._grid.set_week(self._monday)
        self._update_week_label()
        self._grid.scroll_to_hour(datetime.now().hour)

    def _on_contrib_click(self, d: date) -> None:
        self._monday = d - timedelta(days=d.weekday())
        self._grid.set_week(self._monday)
        self._update_week_label()

    # ── Session operations ─────────────────────────────────────────────────

    def _on_edit(self, sess: Session) -> None:
        if sess.is_open:
            QMessageBox.information(self, "Session active",
                "Clock out first before editing an open session.")
            return
        dlg = EditSessionDialog(sess.start, sess.end, parent=self)
        if dlg.exec_() != QDialog.Accepted:
            return
        new_start, new_end = dlg.values()
        try:
            self._store.update_session(sess.line_index, new_start, new_end)
        except Exception as exc:
            QMessageBox.warning(self, "Edit failed", str(exc)); return
        self.reload_needed.emit()

    def _on_delete(self, sess: Session) -> None:
        if QMessageBox.question(
            self, "Delete session",
            "Delete this session? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        try:
            self._store.delete_session(sess.line_index, is_open=sess.is_open)
        except Exception as exc:
            QMessageBox.warning(self, "Delete failed", str(exc)); return
        self.reload_needed.emit()

    def _on_add(self, d: date, start_hour_f: float) -> None:
        if not self._result or not self._result.tasks:
            return
        tm  = int(start_hour_f * 60)
        tm  = (tm // 15) * 15
        tm  = min(tm, 23 * 60 + 44)
        s_dt = datetime(d.year, d.month, d.day, tm // 60, tm % 60)
        e_dt = min(s_dt + timedelta(hours=1),
                   datetime(d.year, d.month, d.day, 23, 59))
        dlg = _CalendarAddSessionDialog(d, self._result.tasks,
                                        preset_start=s_dt, preset_end=e_dt,
                                        parent=self)
        if dlg.exec_() != QDialog.Accepted:
            return
        task_id, s, e = dlg.values()
        try:
            self._store.add_session(task_id, s, e)
        except Exception as exc:
            QMessageBox.warning(self, "Add failed", str(exc)); return
        self.reload_needed.emit()

    # ── Helpers ───────────────────────────────────────────────────────────

    def _mk_nav_btn(self, txt: str) -> QPushButton:
        btn = QPushButton(txt)
        btn.setFixedSize(30, 26)
        btn.setStyleSheet(
            f"QPushButton {{ background: {BG4}; color: {TEXT};"
            f" border: 1px solid {BORDER}; border-radius: 5px;"
            f" font-size: 15px; font-weight: 700; }}"
            f" QPushButton:hover {{ background: {BG3};"
            f" border-color: {BORDER2}; }}"
        )
        return btn
