"""
ui/dialogs/task_dialogs.py — NewTaskDialog, RenameTaskDialog, MoveTaskDialog.
"""
from __future__ import annotations
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QVBoxLayout, QLineEdit, QComboBox
from PyQt5.QtGui import QColor

from .base import BaseFormDialog
from ..theme import DANGER, SS


def _swatch_for_tag(colour_tag: str) -> str:
    from ...core.models import TAG_PALETTES
    palette = TAG_PALETTES.get(colour_tag, TAG_PALETTES["none"])
    return palette[1] if len(palette) > 1 else palette[0]


class NewTaskDialog(BaseFormDialog):
    """Create a new task under a category."""

    def __init__(self, categories: list[tuple[str, str]], parent=None):
        super().__init__("New Task", width=380, parent=parent)

        self._root.addWidget(self._make_header("New Task"))
        body, lay = self._make_body()
        self._root.addWidget(body)

        lay.addWidget(self._field_label("Task name"))
        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. Deep work")
        self._name.setStyleSheet(SS.input())
        lay.addWidget(self._name)

        lay.addWidget(self._field_label("Category"))
        self._category = QComboBox()
        self._category.setStyleSheet(SS.combo())
        for cat_name, colour_tag in categories:
            swatch = _swatch_for_tag(colour_tag)
            self._category.addItem(f"● {cat_name}", userData=cat_name)
            idx = self._category.count() - 1
            self._category.setItemData(idx, QColor(swatch), Qt.ForegroundRole)
        lay.addWidget(self._category)
        lay.addStretch()

        footer, ok_btn, _ = self._make_footer("Create Task")
        ok_btn.clicked.connect(self._on_accept)
        self._root.addWidget(footer)

    def _on_accept(self) -> None:
        if not self._name.text().strip():
            self._name.setStyleSheet(SS.input() + f" QLineEdit {{ border-color: {DANGER}; }}")
            return
        self.accept()

    def values(self) -> tuple[str, str]:
        return self._name.text().strip(), self._category.currentData()


class RenameTaskDialog(BaseFormDialog):
    """Rename an existing task."""

    def __init__(self, current_name: str, parent=None):
        super().__init__("Rename Task", width=340, parent=parent)

        self._root.addWidget(self._make_header("Rename Task"))
        body, lay = self._make_body()
        self._root.addWidget(body)

        lay.addWidget(self._field_label("New name"))
        self._name = QLineEdit(current_name)
        self._name.setStyleSheet(SS.input())
        self._name.selectAll()
        lay.addWidget(self._name)
        lay.addStretch()

        footer, ok_btn, _ = self._make_footer("Rename")
        ok_btn.clicked.connect(self._on_accept)
        self._root.addWidget(footer)

    def _on_accept(self) -> None:
        if not self._name.text().strip():
            self._name.setStyleSheet(SS.input() + f" QLineEdit {{ border-color: {DANGER}; }}")
            return
        self.accept()

    def value(self) -> str:
        return self._name.text().strip()


class MoveTaskDialog(BaseFormDialog):
    """Move a task to a different category."""

    def __init__(self, categories: list[tuple[str, str]], parent=None):
        super().__init__("Move to Category", width=340, parent=parent)

        self._root.addWidget(self._make_header("Move to Category"))
        body, lay = self._make_body()
        self._root.addWidget(body)

        lay.addWidget(self._field_label("Select category"))
        self._category = QComboBox()
        self._category.setStyleSheet(SS.combo())
        for cat_name, colour_tag in categories:
            swatch = _swatch_for_tag(colour_tag)
            self._category.addItem(f"● {cat_name}", userData=cat_name)
            idx = self._category.count() - 1
            self._category.setItemData(idx, QColor(swatch), Qt.ForegroundRole)
        lay.addWidget(self._category)
        lay.addStretch()

        footer, ok_btn, _ = self._make_footer("Move")
        ok_btn.clicked.connect(self.accept)
        self._root.addWidget(footer)

    def value(self) -> str:
        return self._category.currentData()
