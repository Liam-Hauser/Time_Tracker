"""
ui/dialogs/session_dialogs.py — EditSessionDialog, AddSessionDialog.
"""
from __future__ import annotations
from datetime import datetime, timedelta

from PyQt5.QtCore import QDateTime, QDate, QTime
from PyQt5.QtWidgets import QVBoxLayout, QDateTimeEdit, QLineEdit, QTextEdit

from .base import BaseFormDialog
from ..theme import DANGER, SS


def _qdatetime_to_dt(qdt: QDateTime) -> datetime:
    d = qdt.date()
    t = qdt.time()
    return datetime(d.year(), d.month(), d.day(), t.hour(), t.minute(), t.second())


def _dt_to_qdatetime(dt: datetime) -> QDateTime:
    return QDateTime(
        QDate(dt.year, dt.month, dt.day),
        QTime(dt.hour, dt.minute, dt.second),
    )


class EditSessionDialog(BaseFormDialog):
    """Edit the start, end times, and note of an existing session."""

    def __init__(self, start: datetime, end: datetime, note: str = "", parent=None):
        super().__init__("Edit Session", width=400, parent=parent)

        self._root.addWidget(self._make_header("Edit Session"))
        body, lay = self._make_body()
        self._root.addWidget(body)

        for lbl_text, attr, dt_val in [
            ("Start", "_start_edit", start),
            ("End",   "_end_edit",   end),
        ]:
            lay.addWidget(self._field_label(lbl_text))
            edit = QDateTimeEdit()
            edit.setDisplayFormat("yyyy-MM-dd  HH:mm:ss")
            edit.setCalendarPopup(True)
            edit.setStyleSheet(SS.date_edit())
            if dt_val:
                edit.setDateTime(_dt_to_qdatetime(dt_val))
            setattr(self, attr, edit)
            lay.addWidget(edit)

        lay.addWidget(self._field_label("Note"))
        self._note_edit = QTextEdit()
        self._note_edit.setPlaceholderText("Optional note…")
        self._note_edit.setPlainText(note)
        self._note_edit.setMinimumHeight(120)
        self._note_edit.setStyleSheet(SS.input())
        lay.addWidget(self._note_edit)

        footer, ok_btn, _ = self._make_footer("Save")
        ok_btn.clicked.connect(self._on_accept)
        self._root.addWidget(footer)

    def _on_accept(self) -> None:
        if self._start_edit.dateTime() >= self._end_edit.dateTime():
            self._end_edit.setStyleSheet(
                SS.date_edit() + f" QDateTimeEdit {{ border-color: {DANGER}; }}"
            )
            return
        self.accept()

    def values(self) -> tuple[datetime, datetime, str]:
        return (
            _qdatetime_to_dt(self._start_edit.dateTime()),
            _qdatetime_to_dt(self._end_edit.dateTime()),
            self._note_edit.toPlainText().strip(),
        )


class AddSessionDialog(BaseFormDialog):
    """Log a manual session retroactively."""

    def __init__(self, parent=None):
        super().__init__("Add Manual Session", width=400, parent=parent)

        self._root.addWidget(self._make_header("Add Session"))
        body, lay = self._make_body()
        self._root.addWidget(body)

        now = datetime.now().replace(second=0, microsecond=0)
        for lbl_text, attr, dt_val in [
            ("Start", "_start_edit", now - timedelta(hours=1)),
            ("End",   "_end_edit",   now),
        ]:
            lay.addWidget(self._field_label(lbl_text))
            edit = QDateTimeEdit()
            edit.setDisplayFormat("yyyy-MM-dd  HH:mm:ss")
            edit.setCalendarPopup(True)
            edit.setStyleSheet(SS.date_edit())
            edit.setDateTime(_dt_to_qdatetime(dt_val))
            setattr(self, attr, edit)
            lay.addWidget(edit)

        lay.addWidget(self._field_label("Note"))
        self._note_edit = QTextEdit()
        self._note_edit.setPlaceholderText("Optional note…")
        self._note_edit.setMinimumHeight(120)
        self._note_edit.setStyleSheet(SS.input())
        lay.addWidget(self._note_edit)

        footer, ok_btn, _ = self._make_footer("Add Session")
        ok_btn.clicked.connect(self._on_accept)
        self._root.addWidget(footer)

    def _on_accept(self) -> None:
        if self._start_edit.dateTime() >= self._end_edit.dateTime():
            self._end_edit.setStyleSheet(
                SS.date_edit() + f" QDateTimeEdit {{ border-color: {DANGER}; }}"
            )
            return
        self.accept()

    def values(self) -> tuple[datetime, datetime, str]:
        return (
            _qdatetime_to_dt(self._start_edit.dateTime()),
            _qdatetime_to_dt(self._end_edit.dateTime()),
            self._note_edit.toPlainText().strip(),
        )
