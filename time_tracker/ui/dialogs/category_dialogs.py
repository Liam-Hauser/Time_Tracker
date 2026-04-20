"""
ui/dialogs/category_dialogs.py — NewCategoryDialog, RenameCategoryDialog.
"""
from __future__ import annotations
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QVBoxLayout, QLineEdit, QComboBox
from PyQt5.QtGui import QColor

from .base import BaseFormDialog
from ..theme import DANGER, SS
from ...core.models import TAG_PALETTES

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


def _swatch_for_tag(colour_tag: str) -> str:
    palette = TAG_PALETTES.get(colour_tag, TAG_PALETTES["none"])
    return palette[1] if len(palette) > 1 else palette[0]


class NewCategoryDialog(BaseFormDialog):
    """Create a new category."""

    def __init__(self, parent=None):
        super().__init__("New Category", width=340, parent=parent)

        self._root.addWidget(self._make_header("New Category"))
        body, lay = self._make_body()
        self._root.addWidget(body)

        lay.addWidget(self._field_label("Category name"))
        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. Side Projects")
        self._name.setStyleSheet(SS.input())
        lay.addWidget(self._name)

        lay.addWidget(self._field_label("Colour"))
        self._colour = QComboBox()
        self._colour.setStyleSheet(SS.combo())
        for tag, hex_val in _PALETTE_SWATCHES.items():
            self._colour.addItem(f"● {tag}", userData=tag)
            idx = self._colour.count() - 1
            self._colour.setItemData(idx, QColor(hex_val), Qt.ForegroundRole)
        lay.addStretch()

        footer, ok_btn, _ = self._make_footer("Create")
        ok_btn.clicked.connect(self._on_accept)
        self._root.addWidget(footer)

    def _on_accept(self) -> None:
        name = self._name.text().strip()
        if not name:
            self._name.setStyleSheet(SS.input() + f" QLineEdit {{ border-color: {DANGER}; }}")
            return
        if name[0].islower():
            name = name[0].upper() + name[1:]
            self._name.setText(name)
        self.accept()

    def values(self) -> tuple[str, str]:
        return self._name.text().strip(), self._colour.currentData()


class RenameCategoryDialog(BaseFormDialog):
    """Pick a category and supply a new name."""

    def __init__(self, categories: list[tuple[str, str]], parent=None):
        super().__init__("Rename Category", width=340, parent=parent)

        self._root.addWidget(self._make_header("Rename Category"))
        body, lay = self._make_body()
        self._root.addWidget(body)

        lay.addWidget(self._field_label("Category to rename"))
        self._category = QComboBox()
        self._category.setStyleSheet(SS.combo())
        for cat_name, colour_tag in categories:
            swatch = _swatch_for_tag(colour_tag)
            self._category.addItem(f"● {cat_name}", userData=cat_name)
            idx = self._category.count() - 1
            self._category.setItemData(idx, QColor(swatch), Qt.ForegroundRole)
        lay.addWidget(self._category)

        lay.addWidget(self._field_label("New name"))
        self._name = QLineEdit()
        self._name.setPlaceholderText("New category name")
        self._name.setStyleSheet(SS.input())
        lay.addWidget(self._name)
        lay.addStretch()

        footer, ok_btn, _ = self._make_footer("Rename")
        ok_btn.clicked.connect(self._on_accept)
        self._root.addWidget(footer)

    def _on_accept(self) -> None:
        name = self._name.text().strip()
        if not name:
            self._name.setStyleSheet(SS.input() + f" QLineEdit {{ border-color: {DANGER}; }}")
            return
        if name[0].islower():
            name = name[0].upper() + name[1:]
            self._name.setText(name)
        self.accept()

    def values(self) -> tuple[str, str]:
        return self._category.currentData(), self._name.text().strip()
