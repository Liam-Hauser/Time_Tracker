"""
ui/theme.py — Design tokens.  Linear/Vercel-inspired dark palette.
Supports dark / light mode toggle via set_dark_mode() / set_light_mode().
No matplotlib dependency.
"""

# ── Surfaces ─────────────────────────────────────────────
BG       = "#0d0d0d"   # window background
BG2      = "#141414"   # card / panel surface
BG3      = "#1c1c1c"   # elevated surface / hover
BG4      = "#242424"   # control / input surface

# ── Borders ──────────────────────────────────────────────
BORDER   = "#2a2a2a"   # subtle  (most dividers)
BORDER2  = "#3d3d3d"   # active / hover border

# ── Text ─────────────────────────────────────────────────
TEXT     = "#ededed"   # primary
MUTED    = "#737373"   # secondary labels
FAINT    = "#383838"   # ghost / disabled

# ── Semantic ─────────────────────────────────────────────
ACCENT      = "#5B8DEF"   # blue  (primary action)
ACCENT_DIM  = "#1b3466"   # blue tint background
SUCCESS     = "#3DD68C"   # green
SUCCESS_DIM = "#0d3320"
WARNING     = "#F0A429"   # amber
WARNING_DIM = "#3d2600"
DANGER      = "#F04343"   # red
DANGER_DIM  = "#3d0a0a"

# ── Spacing ──────────────────────────────────────────────
PAD_XS = 4
PAD_SM = 8
PAD_MD = 14
PAD_LG = 20
PAD_XL = 28

# backwards-compat aliases used in older code
PAD_MD_OLD = PAD_SM   # was 8
PAD_LG_OLD = PAD_MD   # was 14

# ── Calendar ─────────────────────────────────────────────
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday",
                 "Thursday", "Friday", "Saturday", "Sunday"]
WEEKDAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# ── Chart fallback palette (when task has no colour) ─────
CHART_PALETTE = [
    "#5B8DEF", "#3DD68C", "#F0A429", "#F04343", "#AB7DF6",
    "#38BDF8", "#FB7185", "#34D399", "#FBBF24", "#A78BFA",
    "#60A5FA", "#F472B6",
]

# ── Theme toggle ─────────────────────────────────────────

IS_DARK: bool = True

_DARK_PALETTE: dict = dict(
    BG="#0d0d0d", BG2="#141414", BG3="#1c1c1c", BG4="#242424",
    BORDER="#2a2a2a", BORDER2="#3d3d3d",
    TEXT="#ededed", MUTED="#737373", FAINT="#383838",
    ACCENT_DIM="#1b3466",
    SUCCESS_DIM="#0d3320",
    WARNING_DIM="#3d2600",
    DANGER_DIM="#3d0a0a",
)

_LIGHT_PALETTE: dict = dict(
    BG="#f4f5f7", BG2="#ffffff", BG3="#f0f1f3", BG4="#e8e9eb",
    BORDER="#e2e3e5", BORDER2="#c8c9cb",
    TEXT="#111827", MUTED="#6b7280", FAINT="#d1d5db",
    ACCENT_DIM="#dbeafe",
    SUCCESS_DIM="#dcfce7",
    WARNING_DIM="#fef9c3",
    DANGER_DIM="#fee2e2",
)


def set_dark_mode() -> None:
    """Switch all surface/text tokens to the dark palette and rebuild consumers."""
    import sys
    global IS_DARK
    IS_DARK = True
    mod = sys.modules[__name__]
    for k, v in _DARK_PALETTE.items():
        setattr(mod, k, v)
    _propagate_to_consumers()


def set_light_mode() -> None:
    """Switch all surface/text tokens to the light palette and rebuild consumers."""
    import sys
    global IS_DARK
    IS_DARK = False
    mod = sys.modules[__name__]
    for k, v in _LIGHT_PALETTE.items():
        setattr(mod, k, v)
    _propagate_to_consumers()


def _propagate_to_consumers() -> None:
    """Push updated theme constants into consumer modules that used
    ``from .theme import X`` so they pick up the new values immediately."""
    import sys
    src = sys.modules[__name__]
    _keys = set(_DARK_PALETTE.keys())
    for mod_name in list(sys.modules):
        if "time_tracker" not in mod_name:
            continue
        mod = sys.modules[mod_name]
        for k in _keys:
            if hasattr(mod, k) and not callable(getattr(mod, k)):
                setattr(mod, k, getattr(src, k))
