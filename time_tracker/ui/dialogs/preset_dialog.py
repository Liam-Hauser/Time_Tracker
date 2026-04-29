"""ui/dialogs/preset_dialog.py — AddCustomPresetDialog."""
from __future__ import annotations
from datetime import date
from typing import Optional

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QRadioButton, QButtonGroup, QDateEdit,
)

from .base import BaseFormDialog
from ..theme import TEXT, SS


class AddCustomPresetDialog(BaseFormDialog):
    """Dialog to create a custom date-range preset button (max 5)."""

    def __init__(self, parent=None):
        super().__init__("Add Date Preset", width=360, parent=parent)

        self._root.addWidget(self._make_header("Add Date Preset"))
        body, lay = self._make_body()
        self._root.addWidget(body)

        lay.addWidget(self._field_label("Label (optional — auto-generated if blank)"))
        self._label_edit = QLineEdit()
        self._label_edit.setPlaceholderText("e.g. This semester")
        self._label_edit.setStyleSheet(SS.input())
        lay.addWidget(self._label_edit)

        lay.addWidget(self._field_label("From date"))
        self._from_edit = QDateEdit(QDate.currentDate())
        self._from_edit.setCalendarPopup(True)
        self._from_edit.setDisplayFormat("dd MMM yyyy")
        self._from_edit.setStyleSheet(SS.date_edit())
        lay.addWidget(self._from_edit)

        lay.addWidget(self._field_label("To date"))
        radio_row = QWidget()
        radio_row.setStyleSheet("background: transparent;")
        rlay = QHBoxLayout(radio_row)
        rlay.setContentsMargins(0, 0, 0, 0)
        rlay.setSpacing(14)
        self._radio_now   = QRadioButton("Till now (rolling)")
        self._radio_fixed = QRadioButton("Fixed date")
        self._radio_now.setChecked(True)
        _rb_ss = f"QRadioButton {{ color: {TEXT}; background: transparent; }}"
        self._radio_now.setStyleSheet(_rb_ss)
        self._radio_fixed.setStyleSheet(_rb_ss)
        self._radio_grp = QButtonGroup(self)
        self._radio_grp.addButton(self._radio_now)
        self._radio_grp.addButton(self._radio_fixed)
        rlay.addWidget(self._radio_now)
        rlay.addWidget(self._radio_fixed)
        rlay.addStretch()
        lay.addWidget(radio_row)

        self._to_edit = QDateEdit(QDate.currentDate())
        self._to_edit.setCalendarPopup(True)
        self._to_edit.setDisplayFormat("dd MMM yyyy")
        self._to_edit.setStyleSheet(SS.date_edit())
        self._to_edit.setEnabled(False)
        lay.addWidget(self._to_edit)

        self._radio_now.toggled.connect(lambda checked: self._to_edit.setEnabled(not checked))
        lay.addStretch()

        footer, ok_btn, _ = self._make_footer("Add Preset")
        ok_btn.clicked.connect(self.accept)
        self._root.addWidget(footer)

    def values(self) -> tuple[str, date, Optional[date]]:
        from_d = self._from_edit.date()
        from_d = date(from_d.year(), from_d.month(), from_d.day())
        if self._radio_fixed.isChecked():
            qd    = self._to_edit.date()
            to_d  = date(qd.year(), qd.month(), qd.day())
        else:
            to_d = None
        lbl = self._label_edit.text().strip()
        if not lbl:
            if to_d:
                lbl = f"{from_d.strftime('%d %b %y')} – {to_d.strftime('%d %b %y')}"
            else:
                lbl = f"Since {from_d.strftime('%d %b %y')}"
        return lbl, from_d, to_d
