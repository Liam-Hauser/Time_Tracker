"""
ui/dialogs/goal_dialogs.py — AddGoalDialog, EditGoalDialog.
"""
from __future__ import annotations
from datetime import date
from typing import Optional

from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDoubleSpinBox, QDateEdit, QComboBox, QWidget,
)
from PyQt5.QtGui import QColor

from .base import BaseFormDialog
from ..theme import (
    BG3, BORDER, BORDER2, TEXT, MUTED, ACCENT, SUCCESS, WARNING, DANGER,
    FONT_UI, FONT_MONO, RADIUS, PAD, PAD_MD, SS,
)
from ...core.models import Task, GoalSpec


class AddGoalDialog(BaseFormDialog):
    """Pick a task and set hours + optional deadline."""

    def __init__(self, tasks: list[Task], goals: dict[str, GoalSpec], parent=None):
        super().__init__("New Goal", width=380, parent=parent)
        self._tasks = tasks
        self._goals = goals
        self._spin:  Optional[QDoubleSpinBox] = None
        self._de:    Optional[QDateEdit]      = None
        self._no_dl: Optional[QPushButton]    = None

        header = self._make_header("New Goal")
        self._root.addWidget(header)

        body, lay = self._make_body()
        self._root.addWidget(body)

        lay.addWidget(self._field_label("Task"))
        self._task_combo = QComboBox()
        self._task_combo.setStyleSheet(SS.combo())
        for t in tasks:
            self._task_combo.addItem(f"● {t.name}", userData=t.name)
            idx = self._task_combo.count() - 1
            self._task_combo.setItemData(idx, QColor(t.colour), Qt.ForegroundRole)
        lay.addWidget(self._task_combo)

        lay.addWidget(self._h_line())

        self._form_slot = QVBoxLayout()
        self._form_slot.setContentsMargins(0, 0, 0, 0)
        self._form_slot.setSpacing(0)
        self._form_container: Optional[QWidget] = None
        lay.addLayout(self._form_slot)
        lay.addStretch()

        footer, ok_btn, _ = self._make_footer("Add Goal")
        ok_btn.clicked.connect(self._on_accept)
        self._root.addWidget(footer)

        self._task_combo.currentIndexChanged.connect(self._rebuild_form)
        self._rebuild_form()

    def _rebuild_form(self) -> None:
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
        form_lay.setSpacing(PAD)
        self._form_slot.addWidget(self._form_container)

        gs = self._goals.get(t.name, GoalSpec())
        self._spin, self._de, _, self._no_dl = _make_goal_form(
            form_lay, t.total_hours, gs
        )

    def _on_accept(self) -> None:
        if self._spin is None:
            return
        self.accept()

    def values(self) -> tuple[str, GoalSpec]:
        task_name = self._task_combo.currentData()
        dl = None if self._no_dl.isChecked() else _qdate_to_date(self._de.date())
        return task_name, GoalSpec(hours=self._spin.value(), deadline=dl)


class EditGoalDialog(BaseFormDialog):
    """Edit hours + deadline for a specific task goal."""

    def __init__(self, task: Task, gs: GoalSpec, parent=None):
        super().__init__(f"Edit Goal — {task.name}", width=380, parent=parent)

        header = self._make_header(f"Edit Goal — {task.name}")
        self._root.addWidget(header)

        body, lay = self._make_body()
        self._root.addWidget(body)

        self._spin, self._de, _, self._no_dl = _make_goal_form(
            lay, task.total_hours, gs
        )
        lay.addStretch()

        footer, ok_btn, _ = self._make_footer("Save")
        ok_btn.clicked.connect(self.accept)
        self._root.addWidget(footer)

    def values(self) -> GoalSpec:
        dl = None if self._no_dl.isChecked() else _qdate_to_date(self._de.date())
        return GoalSpec(hours=self._spin.value(), deadline=dl)


# ── Shared helpers ────────────────────────────────────────────────────────────

def _qdate_to_date(qd: QDate) -> date:
    return date(qd.year(), qd.month(), qd.day())


def _make_goal_form(
    lay: QVBoxLayout,
    task_total_hours: float,
    gs: GoalSpec,
) -> tuple[QDoubleSpinBox, QDateEdit, QLabel, QPushButton]:
    """Build the shared goal form body into *lay*. Returns (spin, de, pace_lbl, no_dl_btn)."""

    lay.addWidget(_field_lbl("Target Hours"))
    spin = QDoubleSpinBox()
    spin.setRange(0.5, 9999)
    spin.setSingleStep(0.5)
    spin.setValue(gs.hours if gs.hours > 0 else 10.0)
    spin.setStyleSheet(SS.spinbox())
    lay.addWidget(spin)

    lay.addWidget(_field_lbl("Deadline (optional)"))

    no_dl_row = QHBoxLayout()
    no_dl_row.setSpacing(PAD)
    no_dl_btn = QPushButton("No deadline")
    no_dl_btn.setCheckable(True)
    no_dl_btn.setChecked(gs.deadline is None)
    no_dl_btn.setFixedHeight(28)
    no_dl_btn.setStyleSheet(
        f"QPushButton {{"
        f"  background: {BG3}; color: {MUTED}; border: 1px solid {BORDER};"
        f"  border-radius: {RADIUS}px; font-size: 10px; padding: 0 10px;"
        f"  font-family: {FONT_UI};"
        f"}}"
        f"QPushButton:checked {{"
        f"  background: {ACCENT}; color: #fff; border-color: {ACCENT};"
        f"}}"
    )
    no_dl_row.addWidget(no_dl_btn)

    de = QDateEdit()
    de.setCalendarPopup(True)
    de.setDisplayFormat("dd MMM yyyy")
    de.setStyleSheet(SS.date_edit())
    de.setEnabled(gs.deadline is not None)
    if gs.deadline:
        de.setDate(QDate(gs.deadline.year, gs.deadline.month, gs.deadline.day))
    else:
        de.setDate(QDate.currentDate().addMonths(1))
    no_dl_row.addWidget(de, stretch=1)
    lay.addLayout(no_dl_row)
    no_dl_btn.toggled.connect(lambda checked: de.setEnabled(not checked))

    pace_lbl = QLabel("—")
    pace_lbl.setStyleSheet(
        f"color: {MUTED}; font-size: 11px; background: transparent;"
        f" font-family: {FONT_MONO};"
    )
    lay.addWidget(pace_lbl)

    def _update_pace() -> None:
        h    = spin.value()
        done = task_total_hours
        if no_dl_btn.isChecked():
            if done >= h:
                pace_lbl.setText("Goal already reached!")
                pace_lbl.setStyleSheet(_pace_css(SUCCESS))
            else:
                pace_lbl.setText(f"{h - done:.1f}h remaining · no deadline")
                pace_lbl.setStyleSheet(_pace_css(MUTED))
            return
        dl        = _qdate_to_date(de.date())
        days_left = (dl - date.today()).days
        if done >= h:
            pace_lbl.setText("Goal already reached!")
            pace_lbl.setStyleSheet(_pace_css(SUCCESS))
        elif days_left <= 0:
            pace_lbl.setText("Deadline has passed!")
            pace_lbl.setStyleSheet(_pace_css(DANGER))
        else:
            req = (h - done) / days_left
            col = SUCCESS if req <= 2 else (WARNING if req <= 4 else DANGER)
            pace_lbl.setText(f"{req:.2f} h/day needed · {days_left}d left")
            pace_lbl.setStyleSheet(_pace_css(col))

    spin.valueChanged.connect(lambda _: _update_pace())
    de.dateChanged.connect(lambda _: _update_pace())
    no_dl_btn.toggled.connect(lambda _: _update_pace())
    _update_pace()

    return spin, de, pace_lbl, no_dl_btn


def _field_lbl(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(
        f"color: {MUTED}; font-size: 9px; font-family: {FONT_MONO};"
        f" letter-spacing: 0.9px; background: transparent;"
    )
    return lbl


def _pace_css(color: str) -> str:
    return (
        f"color: {color}; font-size: 11px; background: transparent;"
        f" font-family: {FONT_MONO};"
    )
