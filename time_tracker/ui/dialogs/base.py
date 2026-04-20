"""
ui/dialogs/base.py — BaseFormDialog: shared styling for all dialogs.
"""
from __future__ import annotations
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QPushButton, QWidget,
)
from ..theme import (
    BG, BG2, BG3, BORDER, BORDER2, TEXT, MUTED, FAINT, ACCENT, DANGER,
    FONT_UI, FONT_MONO, RADIUS, RADIUS_LG, PAD, PAD_MD,
    SS,
)


class BaseFormDialog(QDialog):
    """Base class for all Time Tracker form dialogs.

    Provides consistent layout, header, footer, and field helpers.
    Subclasses call _build() in their __init__ and connect _ok_btn / _cancel_btn.
    """

    def __init__(self, title: str, width: int = 380, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedWidth(width)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._apply_style()

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(0, 0, 0, 0)
        self._root.setSpacing(0)

    def _apply_style(self) -> None:
        self.setStyleSheet(
            f"QDialog {{"
            f"  background: {BG2}; color: {TEXT};"
            f"  border: 1px solid {BORDER2};"
            f"}}"
            f"QLabel {{ background: transparent; color: {TEXT};"
            f"  font-family: {FONT_UI}; }}"
        )

    def _make_header(self, title: str) -> QFrame:
        hdr = QFrame()
        hdr.setFixedHeight(32)
        hdr.setStyleSheet(
            f"QFrame {{ background: {BG3}; border: none;"
            f" border-bottom: 1px solid {BORDER}; }}"
        )
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(PAD_MD, 0, PAD_MD, 0)
        lbl = QLabel(title.upper())
        lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 9px; font-family: {FONT_MONO};"
            f" letter-spacing: 1.0px; font-weight: 600; background: transparent;"
        )
        hl.addWidget(lbl)
        hl.addStretch()
        return hdr

    def _make_body(self, padding: int = PAD_MD) -> tuple[QWidget, QVBoxLayout]:
        """Return (body_widget, body_layout) for the form content."""
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(padding, padding, padding, padding)
        lay.setSpacing(PAD)
        return body, lay

    def _make_footer(self, ok_label: str = "OK",
                     cancel_label: str = "Cancel") -> tuple[QFrame, QPushButton, QPushButton]:
        footer = QFrame()
        footer.setStyleSheet(
            f"QFrame {{ background: {BG3}; border: none;"
            f" border-top: 1px solid {BORDER}; }}"
        )
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(PAD_MD, PAD, PAD_MD, PAD)
        fl.setSpacing(PAD)
        fl.addStretch()

        cancel_btn = QPushButton(cancel_label)
        cancel_btn.setStyleSheet(SS.button("ghost"))
        cancel_btn.setFixedHeight(28)
        cancel_btn.clicked.connect(self.reject)
        fl.addWidget(cancel_btn)

        ok_btn = QPushButton(ok_label)
        ok_btn.setStyleSheet(SS.button("primary"))
        ok_btn.setFixedHeight(28)
        fl.addWidget(ok_btn)

        self._ok_btn = ok_btn
        self._cancel_btn = cancel_btn
        return footer, ok_btn, cancel_btn

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            f"color: {MUTED}; font-size: 9px; font-family: {FONT_MONO};"
            f" letter-spacing: 0.9px; background: transparent;"
        )
        return lbl

    def _h_line(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {BORDER}; border: none;")
        return line
