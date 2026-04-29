"""
ui/dialogs/category_dialogs.py — NewCategoryDialog, RenameCategoryDialog,
                                   RecolorCategoryDialog.
"""
from __future__ import annotations
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QGridLayout, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox, QLabel,
)
from PyQt5.QtGui import QColor

from .base import BaseFormDialog
from ..theme import DANGER, TEXT, MUTED, BG3, BORDER, BORDER2, RADIUS, SS
from ...core.models import hue_for_tag, hsl_to_hex, category_swatch, TAG_PALETTES

# 20 evenly-spaced hues around the wheel
_PICKER_HUES = list(range(0, 360, 18))
_PICKER_COLS = 5


def _swatch_hex(colour_tag: str) -> str:
    """Representative hex for a colour_tag (used in dropdown swatches)."""
    return category_swatch(colour_tag)


class _HuePicker(QWidget):
    """5-column grid of coloured swatches for selecting a hue."""

    hue_selected = pyqtSignal(int)

    def __init__(self, initial_hue: int = 210, parent=None):
        super().__init__(parent)
        self._hue = initial_hue
        self._labels: dict[int, QLabel] = {}

        lay = QGridLayout(self)
        lay.setSpacing(5)
        lay.setContentsMargins(0, 0, 0, 0)

        for i, hue in enumerate(_PICKER_HUES):
            color = hsl_to_hex(hue, 75, 45)
            lbl = QLabel()
            lbl.setFixedSize(40, 28)
            lbl.setCursor(Qt.PointingHandCursor)
            self._labels[hue] = lbl
            lbl.mousePressEvent = lambda _e, h=hue: self._select(h)
            lay.addWidget(lbl, i // _PICKER_COLS, i % _PICKER_COLS)

        self._refresh_styles()

    def _select(self, hue: int) -> None:
        self._hue = hue
        self._refresh_styles()
        self.hue_selected.emit(hue)

    def _refresh_styles(self) -> None:
        for hue, lbl in self._labels.items():
            color = hsl_to_hex(hue, 75, 45)
            selected = hue == self._hue
            border = f"2px solid {TEXT}" if selected else f"2px solid transparent"
            lbl.setStyleSheet(
                f"background: {color}; border: {border}; border-radius: {RADIUS}px;"
            )

    def set_hue(self, hue: int) -> None:
        closest = min(_PICKER_HUES, key=lambda h: min(abs(h - hue), 360 - abs(h - hue)))
        self._hue = closest
        self._refresh_styles()

    @property
    def selected_hue(self) -> int:
        return self._hue


class NewCategoryDialog(BaseFormDialog):
    """Create a new category."""

    def __init__(self, parent=None):
        super().__init__("New Category", width=360, parent=parent)

        self._root.addWidget(self._make_header("New Category"))
        body, lay = self._make_body()
        self._root.addWidget(body)

        lay.addWidget(self._field_label("Category name"))
        self._name = QLineEdit()
        self._name.setPlaceholderText("e.g. Side Projects")
        self._name.setStyleSheet(SS.input())
        lay.addWidget(self._name)

        lay.addWidget(self._field_label("Colour"))
        self._picker = _HuePicker(initial_hue=210)
        lay.addWidget(self._picker)
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
        return self._name.text().strip(), str(self._picker.selected_hue)


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
            swatch = _swatch_hex(colour_tag)
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


class RecolorCategoryDialog(BaseFormDialog):
    """Pick a category and choose a new colour."""

    def __init__(self, categories: list[tuple[str, str]], parent=None):
        super().__init__("Recolor Category", width=360, parent=parent)

        self._root.addWidget(self._make_header("Recolor Category"))
        body, lay = self._make_body()
        self._root.addWidget(body)

        lay.addWidget(self._field_label("Category"))
        self._category = QComboBox()
        self._category.setStyleSheet(SS.combo())
        for cat_name, colour_tag in categories:
            swatch = _swatch_hex(colour_tag)
            self._category.addItem(f"● {cat_name}", userData=(cat_name, colour_tag))
            idx = self._category.count() - 1
            self._category.setItemData(idx, QColor(swatch), Qt.ForegroundRole)
        lay.addWidget(self._category)

        lay.addWidget(self._field_label("New colour"))
        initial_hue = hue_for_tag(categories[0][1]) if categories else 210
        self._picker = _HuePicker(initial_hue=initial_hue)
        lay.addWidget(self._picker)
        lay.addStretch()

        self._category.currentIndexChanged.connect(self._on_cat_changed)

        footer, ok_btn, _ = self._make_footer("Apply")
        ok_btn.clicked.connect(self.accept)
        self._root.addWidget(footer)

    def _on_cat_changed(self, _idx: int) -> None:
        data = self._category.currentData()
        if data:
            _name, colour_tag = data
            self._picker.set_hue(hue_for_tag(colour_tag))

    def values(self) -> tuple[str, str]:
        """Return (category_name, new_colour_tag_as_numeric_string)."""
        data = self._category.currentData()
        cat_name = data[0] if data else ""
        return cat_name, str(self._picker.selected_hue)
