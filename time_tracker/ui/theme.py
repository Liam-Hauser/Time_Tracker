"""
ui/theme.py — All colour/font/spacing constants in one place.
"""

# ── Dark palette ──────────────────────────────────────────
BG         = "#1a1a1a"   # window background
BG2        = "#242424"   # panel / card background
BG3        = "#2e2e2e"   # input / row hover
BORDER     = "#3a3a3a"   # subtle borders
TEXT       = "#e0e0e0"   # primary text
MUTED      = "#888888"   # secondary text
FAINT      = "#555555"   # disabled / hints
ACCENT     = "#378ADD"   # blue highlight
ACCENT2    = "#185FA5"   # darker accent
SUCCESS    = "#4CAF50"
WARNING    = "#FF9900"
DANGER     = "#E24B4A"

# ── Matplotlib colours (must be compatible with mpl) ─────
MPL_BG     = "#1a1a1a"
MPL_BG2    = "#242424"
MPL_TEXT   = "#e0e0e0"
MPL_MUTED  = "#666666"
MPL_GRID   = "#2e2e2e"

# ── Typography ────────────────────────────────────────────
FONT_FAMILY = "Segoe UI"   # falls back gracefully on Mac/Linux
FONT_SM     = ("Segoe UI", 10)
FONT_MD     = ("Segoe UI", 12)
FONT_LG     = ("Segoe UI", 14)
FONT_BOLD   = ("Segoe UI", 12, "bold")
FONT_TITLE  = ("Segoe UI", 18, "bold")

# ── Spacing ───────────────────────────────────────────────
PAD_SM = 4
PAD_MD = 8
PAD_LG = 16

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday",
                 "Thursday", "Friday", "Saturday", "Sunday"]
WEEKDAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def apply_matplotlib_theme() -> None:
    """Set global matplotlib rcParams to match the dark UI."""
    import matplotlib as mpl
    mpl.rcParams.update({
        "figure.facecolor":  MPL_BG,
        "axes.facecolor":    MPL_BG2,
        "axes.edgecolor":    MPL_GRID,
        "axes.labelcolor":   MPL_MUTED,
        "axes.titlecolor":   MPL_TEXT,
        "axes.grid":         True,
        "grid.color":        MPL_GRID,
        "grid.linewidth":    0.6,
        "xtick.color":       MPL_MUTED,
        "ytick.color":       MPL_MUTED,
        "xtick.labelsize":   9,
        "ytick.labelsize":   9,
        "legend.facecolor":  MPL_BG2,
        "legend.edgecolor":  BORDER,
        "legend.fontsize":   9,
        "text.color":        MPL_TEXT,
        "lines.linewidth":   1.5,
        "patch.edgecolor":   "none",
        "font.family":       "DejaVu Sans",
    })
