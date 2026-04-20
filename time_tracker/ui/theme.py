"""
ui/theme.py — Design tokens: Quant Workstation palette.
Supports dark/light mode toggle via set_dark_mode() / set_light_mode().
"""
import sys as _sys

# ── Surfaces ─────────────────────────────────────────────
BG       = "#0b0d10"   # window background
BG2      = "#10131a"   # panels, sidebar surface
BG3      = "#161a22"   # inputs, hover backgrounds
BG4      = "#1d2230"   # selected/active cells

# ── Borders ──────────────────────────────────────────────
BORDER   = "#232938"   # subtle dividers
BORDER2  = "#313a4e"   # active/hover border

# ── Text ─────────────────────────────────────────────────
TEXT     = "#e6e8ee"   # primary
DIM      = "#a0a5b0"   # secondary labels
MUTED    = "#6b7280"   # tertiary / section labels
FAINT    = "#3a414f"   # ghost / disabled

# ── Semantic ─────────────────────────────────────────────
ACCENT      = "#58b8ff"   # cyan (primary action)
ACCENT2     = "#a78bfa"   # purple
ACCENT_DIM  = "#0d2340"   # cyan tint background
SUCCESS     = "#34d399"   # green
SUCCESS_DIM = "#0a2e1f"
WARNING     = "#fbbf24"   # amber
WARNING_DIM = "#2e1f00"
DANGER      = "#f87171"   # red
DANGER_DIM  = "#2e0a0a"

# ── Typography ───────────────────────────────────────────
FONT_UI   = "Geist, Segoe UI, -apple-system, sans-serif"
FONT_MONO = "Geist Mono, Cascadia Mono, Consolas, monospace"

# ── Geometry ─────────────────────────────────────────────
RADIUS    = 6    # standard border-radius px
RADIUS_LG = 10   # cards, modals
PAD       = 8    # dense padding px
PAD_MD    = 12   # standard padding
PAD_LG    = 16   # section padding

# backwards-compat aliases
PAD_XS = 4
PAD_SM = PAD
PAD_XL = 24
PAD_MD_OLD = PAD_SM
PAD_LG_OLD = PAD_MD

# ── Calendar helpers ─────────────────────────────────────
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday",
                 "Thursday", "Friday", "Saturday", "Sunday"]
WEEKDAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# ── Chart palette ────────────────────────────────────────
CHART_COLORS = [
    "#58b8ff", "#a78bfa", "#34d399", "#fbbf24",
    "#f87171", "#22d3ee", "#f472b6", "#84cc16",
]

# legacy alias (some chart code uses CHART_PALETTE)
CHART_PALETTE = CHART_COLORS

# ── Theme toggle ─────────────────────────────────────────

IS_DARK: bool = True

_DARK_PALETTE: dict = dict(
    BG="#0b0d10", BG2="#10131a", BG3="#161a22", BG4="#1d2230",
    BORDER="#232938", BORDER2="#313a4e",
    TEXT="#e6e8ee", DIM="#a0a5b0", MUTED="#6b7280", FAINT="#3a414f",
    ACCENT="#58b8ff", ACCENT2="#a78bfa", ACCENT_DIM="#0d2340",
    SUCCESS="#34d399", SUCCESS_DIM="#0a2e1f",
    WARNING="#fbbf24", WARNING_DIM="#2e1f00",
    DANGER="#f87171", DANGER_DIM="#2e0a0a",
    CHART_COLORS=[
        "#58b8ff", "#a78bfa", "#34d399", "#fbbf24",
        "#f87171", "#22d3ee", "#f472b6", "#84cc16",
    ],
    CHART_PALETTE=[
        "#58b8ff", "#a78bfa", "#34d399", "#fbbf24",
        "#f87171", "#22d3ee", "#f472b6", "#84cc16",
    ],
)

_LIGHT_PALETTE: dict = dict(
    BG="#f7f8fa", BG2="#eef0f3", BG3="#ffffff", BG4="#f2f4f7",
    BORDER="#e3e6eb", BORDER2="#ced3db",
    TEXT="#0f1419", DIM="#4b5563", MUTED="#6b7280", FAINT="#cbd0d8",
    ACCENT="#2563eb", ACCENT2="#7c3aed", ACCENT_DIM="#dbeafe",
    SUCCESS="#059669", SUCCESS_DIM="#dcfce7",
    WARNING="#d97706", WARNING_DIM="#fef9c3",
    DANGER="#dc2626", DANGER_DIM="#fee2e2",
    CHART_COLORS=[
        "#2563eb", "#7c3aed", "#059669", "#d97706",
        "#dc2626", "#0891b2", "#db2777", "#65a30d",
    ],
    CHART_PALETTE=[
        "#2563eb", "#7c3aed", "#059669", "#d97706",
        "#dc2626", "#0891b2", "#db2777", "#65a30d",
    ],
)


def set_dark_mode() -> None:
    global IS_DARK
    IS_DARK = True
    mod = _sys.modules[__name__]
    for k, v in _DARK_PALETTE.items():
        setattr(mod, k, v)
    _propagate_to_consumers()


def set_light_mode() -> None:
    global IS_DARK
    IS_DARK = False
    mod = _sys.modules[__name__]
    for k, v in _LIGHT_PALETTE.items():
        setattr(mod, k, v)
    _propagate_to_consumers()


def _propagate_to_consumers() -> None:
    """Push updated theme constants into consumer modules that used
    ``from .theme import X`` so they pick up the new values immediately."""
    src = _sys.modules[__name__]
    _keys = set(_DARK_PALETTE.keys())
    for mod_name in list(_sys.modules):
        if "time_tracker" not in mod_name:
            continue
        mod = _sys.modules[mod_name]
        for k in _keys:
            if hasattr(mod, k) and not callable(getattr(mod, k)):
                setattr(mod, k, getattr(src, k))


# ── Stylesheet factory ────────────────────────────────────

class SS:
    """Central CSS factory. All widget files call SS.xyz() instead of
    repeating inline f-strings. Methods read current theme globals at
    call time so dark/light mode works automatically."""

    @staticmethod
    def button(variant: str = "ghost") -> str:
        if variant == "primary":
            return (
                f"QPushButton {{"
                f"  background: {ACCENT}; color: {BG};"
                f"  border: 1px solid {ACCENT}; border-radius: {RADIUS}px;"
                f"  padding: 5px 12px; font-size: 11px; font-family: {FONT_UI};"
                f"}}"
                f"QPushButton:hover {{"
                f"  background: {ACCENT}; border-color: {ACCENT};"
                f"}}"
                f"QPushButton:disabled {{"
                f"  background: {FAINT}; color: {MUTED}; border-color: {FAINT};"
                f"}}"
            )
        if variant == "danger":
            return (
                f"QPushButton {{"
                f"  background: transparent; color: {DANGER};"
                f"  border: 1px solid {DANGER}; border-radius: {RADIUS}px;"
                f"  padding: 5px 12px; font-size: 11px; font-family: {FONT_UI};"
                f"}}"
                f"QPushButton:hover {{"
                f"  background: {DANGER_DIM};"
                f"}}"
                f"QPushButton:disabled {{ opacity: 0.5; }}"
            )
        if variant == "solid":
            return (
                f"QPushButton {{"
                f"  background: {BG3}; color: {TEXT};"
                f"  border: 1px solid {BORDER}; border-radius: {RADIUS}px;"
                f"  padding: 5px 12px; font-size: 11px; font-family: {FONT_UI};"
                f"}}"
                f"QPushButton:hover {{"
                f"  background: {BG4}; border-color: {BORDER2};"
                f"}}"
                f"QPushButton:disabled {{"
                f"  color: {MUTED}; border-color: {FAINT};"
                f"}}"
            )
        # ghost (default)
        return (
            f"QPushButton {{"
            f"  background: transparent; color: {DIM};"
            f"  border: 1px solid {BORDER}; border-radius: {RADIUS}px;"
            f"  padding: 5px 12px; font-size: 11px; font-family: {FONT_UI};"
            f"}}"
            f"QPushButton:hover {{"
            f"  border-color: {BORDER2}; color: {TEXT};"
            f"}}"
            f"QPushButton:disabled {{"
            f"  color: {FAINT}; border-color: {FAINT};"
            f"}}"
        )

    @staticmethod
    def icon_button(size: int = 24) -> str:
        return (
            f"QPushButton {{"
            f"  background: transparent; color: {MUTED};"
            f"  border: none; border-radius: {RADIUS}px;"
            f"  min-width: {size}px; max-width: {size}px;"
            f"  min-height: {size}px; max-height: {size}px;"
            f"  font-size: 13px;"
            f"}}"
            f"QPushButton:hover {{ color: {TEXT}; background: {BG3}; }}"
        )

    @staticmethod
    def input() -> str:
        return (
            f"QLineEdit {{"
            f"  background: {BG3}; color: {TEXT};"
            f"  border: 1px solid {BORDER}; border-radius: {RADIUS}px;"
            f"  padding: 5px 10px; font-size: 12px; font-family: {FONT_UI};"
            f"}}"
            f"QLineEdit:focus {{ border-color: {ACCENT}; }}"
            f"QLineEdit:disabled {{ color: {MUTED}; }}"
        )

    @staticmethod
    def combo() -> str:
        return (
            f"QComboBox {{"
            f"  background: {BG3}; color: {TEXT};"
            f"  border: 1px solid {BORDER}; border-radius: {RADIUS}px;"
            f"  padding: 5px 10px; font-size: 12px; font-family: {FONT_UI};"
            f"}}"
            f"QComboBox:focus {{ border-color: {ACCENT}; }}"
            f"QComboBox::drop-down {{ border: none; width: 20px; }}"
            f"QComboBox::down-arrow {{ width: 10px; height: 10px; }}"
            f"QComboBox QAbstractItemView {{"
            f"  background: {BG2}; color: {TEXT};"
            f"  border: 1px solid {BORDER2}; border-radius: {RADIUS}px;"
            f"  selection-background-color: {BG4};"
            f"  outline: none;"
            f"}}"
        )

    @staticmethod
    def spinbox() -> str:
        return (
            f"QSpinBox, QDoubleSpinBox {{"
            f"  background: {BG3}; color: {TEXT};"
            f"  border: 1px solid {BORDER}; border-radius: {RADIUS}px;"
            f"  padding: 5px 8px; font-size: 12px; font-family: {FONT_MONO};"
            f"}}"
            f"QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {ACCENT}; }}"
            f"QSpinBox::up-button, QSpinBox::down-button,"
            f"QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{"
            f"  background: {BG4}; border: none; width: 16px;"
            f"}}"
        )

    @staticmethod
    def date_edit() -> str:
        return (
            f"QDateEdit, QDateTimeEdit {{"
            f"  background: {BG3}; color: {TEXT};"
            f"  border: 1px solid {BORDER}; border-radius: {RADIUS}px;"
            f"  padding: 5px 8px; font-size: 12px; font-family: {FONT_MONO};"
            f"}}"
            f"QDateEdit:focus, QDateTimeEdit:focus {{ border-color: {ACCENT}; }}"
            f"QDateEdit::drop-down, QDateTimeEdit::drop-down {{"
            f"  border: none; width: 20px;"
            f"}}"
            f"QCalendarWidget QAbstractItemView {{"
            f"  background: {BG2}; color: {TEXT};"
            f"  selection-background-color: {ACCENT}; selection-color: {BG};"
            f"}}"
            f"QCalendarWidget QWidget {{ background: {BG2}; color: {TEXT}; }}"
        )

    @staticmethod
    def dialog() -> str:
        return (
            f"QDialog {{"
            f"  background: {BG2}; color: {TEXT};"
            f"  border: 1px solid {BORDER2}; border-radius: {RADIUS_LG}px;"
            f"}}"
            f"QLabel {{ background: transparent; color: {TEXT}; font-family: {FONT_UI}; }}"
            f"QLabel[role='field-label'] {{"
            f"  color: {MUTED}; font-size: 9px; font-family: {FONT_MONO};"
            f"  text-transform: uppercase; letter-spacing: 0.9px;"
            f"}}"
        )

    @staticmethod
    def scrollarea() -> str:
        return (
            f"QScrollArea {{ background: transparent; border: none; }}"
            f"QScrollBar:vertical {{"
            f"  background: transparent; width: 8px; margin: 0;"
            f"}}"
            f"QScrollBar::handle:vertical {{"
            f"  background: rgba(120,120,120,0.25); border-radius: 4px; min-height: 20px;"
            f"}}"
            f"QScrollBar::handle:vertical:hover {{ background: rgba(120,120,120,0.45); }}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
            f"QScrollBar:horizontal {{"
            f"  background: transparent; height: 8px; margin: 0;"
            f"}}"
            f"QScrollBar::handle:horizontal {{"
            f"  background: rgba(120,120,120,0.25); border-radius: 4px; min-width: 20px;"
            f"}}"
            f"QScrollBar::handle:horizontal:hover {{ background: rgba(120,120,120,0.45); }}"
            f"QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}"
        )

    @staticmethod
    def tab_widget() -> str:
        return (
            f"QTabWidget::pane {{"
            f"  border: none; background: {BG};"
            f"}}"
            f"QTabBar::tab {{"
            f"  background: {BG2}; color: {MUTED};"
            f"  padding: 6px 14px; font-size: 11px; font-family: {FONT_UI};"
            f"  border: none; border-bottom: 2px solid transparent;"
            f"  margin-right: 1px;"
            f"}}"
            f"QTabBar::tab:selected {{"
            f"  color: {TEXT}; background: {BG};"
            f"  border-bottom: 2px solid {ACCENT};"
            f"}}"
            f"QTabBar::tab:hover:!selected {{"
            f"  color: {DIM}; background: {BG3};"
            f"}}"
            f"QTabBar::tab:close-button {{"
            f"  image: none; width: 14px; padding: 0 2px;"
            f"}}"
            f"QTabBar {{ background: {BG2}; border-bottom: 1px solid {BORDER}; }}"
        )

    @staticmethod
    def section_label() -> str:
        return (
            f"QLabel {{"
            f"  color: {MUTED}; font-size: 9px; font-family: {FONT_MONO};"
            f"  letter-spacing: 1.2px; font-weight: 600;"
            f"  background: transparent;"
            f"}}"
        )

    @staticmethod
    def window() -> str:
        return (
            f"QMainWindow, QWidget#central {{"
            f"  background: {BG}; color: {TEXT}; font-family: {FONT_UI};"
            f"}}"
            f"QToolTip {{"
            f"  background: {BG4}; color: {TEXT}; border: 1px solid {BORDER2};"
            f"  padding: 4px 8px; border-radius: {RADIUS}px; font-size: 11px;"
            f"}}"
        )
