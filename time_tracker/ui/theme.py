"""
ui/theme.py — Design tokens.  Linear/Vercel-inspired dark palette.
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
