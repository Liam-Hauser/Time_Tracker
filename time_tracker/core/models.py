"""
core/models.py — Pure data models. No UI, no file I/O.

Field naming note: Task.start_line holds the DB tasks.id, and
Session.line_index holds the DB clock record id.  The db_id properties
below provide clearer names; start_line / line_index are kept for
backwards-compatibility with existing callers.
"""

from __future__ import annotations
import colorsys as _colorsys
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Optional
import re


# ──────────────────────────────────────────────────────────
# Mathematical colour generation
# ──────────────────────────────────────────────────────────

# Named tag → base hue (degrees, 0–360).
# Hues are intentionally well-separated so named tags don't look alike.
_TAG_HUES: dict[str, int] = {
    "blue":   210,
    "red":    5,
    "yellow": 48,
    "green":  130,
    "purple": 270,
    "brown":  25,
    "white":  185,   # teal-cyan — clearly distinct from blue (210)
    "black":  315,   # pink-magenta — distinct from purple (270) and blue
    "none":   35,    # amber-orange fallback, away from all named tags
}

# No longer used for lookups; kept as an empty dict so old imports don't crash.
CATEGORY_COLOUR_TAG: dict[str, str] = {}


def hue_for_tag(colour_tag: str | None) -> int:
    """Return hue (0–360) for a colour_tag — accepts named tags or numeric strings."""
    if not colour_tag:
        return _TAG_HUES["none"]
    try:
        return int(colour_tag) % 360
    except (ValueError, TypeError):
        return _TAG_HUES.get(colour_tag, _TAG_HUES["none"])


def hsl_to_hex(h: float, s: float, l: float) -> str:  # noqa: E741
    """Convert HSL (h: 0–360, s: 0–100, l: 0–100) to '#rrggbb'."""
    r, g, b = _colorsys.hls_to_rgb(h / 360.0, l / 100.0, s / 100.0)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def generate_category_colors(colour_tag: str | None, n: int) -> list[str]:
    """Generate *n* visually distinct gradient colors within a single hue family.

    The lightness/saturation range is intentionally wide so even categories with
    many tasks (10+) have clearly different shades. Dark end = index 0 (most
    saturated), light end = last index.
    """
    hue = hue_for_tag(colour_tag)
    if n == 0:
        return []
    if n == 1:
        return [hsl_to_hex(hue, 82, 42)]

    L_DARK, L_LIGHT = 24, 55   # lightness span
    S_DARK, S_LIGHT = 90, 68   # saturation (dark end = rich, light end = still vibrant)

    return [
        hsl_to_hex(
            hue,
            S_DARK + (S_LIGHT - S_DARK) * i / (n - 1),
            L_DARK + (L_LIGHT - L_DARK) * i / (n - 1),
        )
        for i in range(n)
    ]


def category_swatch(colour_tag: str | None) -> str:
    """Representative midpoint hex for a colour_tag (used in UI swatches)."""
    return hsl_to_hex(hue_for_tag(colour_tag), 82, 42)


def colour_for_tag(tag: str, index: int) -> str:
    """Legacy shim — returns a single color for a (tag, position) pair."""
    n = max(index + 1, 3)
    colors = generate_category_colors(tag, n)
    return colors[min(index, len(colors) - 1)]


# TAG_PALETTES kept for any code that still imports it — now math-generated.
TAG_PALETTES: dict[str, list[str]] = {
    name: generate_category_colors(str(hue), 3)
    for name, hue in _TAG_HUES.items()
}


# ──────────────────────────────────────────────────────────
# Session
# ──────────────────────────────────────────────────────────
@dataclass
class Session:
    start: datetime
    end: Optional[datetime]   # None = currently clocked in
    line_index: int           # holds DB clock record id
    note: str = ""

    @property
    def db_id(self) -> int:
        return self.line_index

    @property
    def is_open(self) -> bool:
        return self.end is None

    @property
    def duration(self) -> timedelta:
        if self.is_open:
            return datetime.now() - self.start
        return self.end - self.start  # type: ignore[operator]

    @property
    def duration_seconds(self) -> float:
        return self.duration.total_seconds()

    @property
    def date(self) -> date:
        return self.start.date()

    @property
    def hour(self) -> int:
        return self.start.hour


# ──────────────────────────────────────────────────────────
# Task
# ──────────────────────────────────────────────────────────
@dataclass
class GoalSpec:
    """Portable goal config stored on MainWindow and written onto Tasks."""
    hours:        float          = 0.0
    deadline:     Optional[date] = None
    completed_on: Optional[date] = None  # set when goal first reaches 100%
    archived:     bool           = False  # manually archived by user

    def progress(self, task: "Task") -> float:
        """0.0–1.0 completion ratio, capped at 1."""
        if self.hours <= 0:
            return 0.0
        return min(1.0, task.total_hours / self.hours)

    def is_on_track(self, task: "Task") -> bool:
        """True if current pace would meet the deadline."""
        if not self.deadline or self.hours <= 0:
            return True
        days_elapsed = max(1, (date.today() - task.sessions[0].date).days) if task.sessions else 1
        daily_actual = task.total_hours / days_elapsed
        days_left = (self.deadline - date.today()).days
        if days_left <= 0:
            return task.total_hours >= self.hours
        required = max(0.0, self.hours - task.total_hours) / days_left
        return daily_actual >= required * 0.9

    def days_remaining(self) -> Optional[int]:
        if not self.deadline:
            return None
        return (self.deadline - date.today()).days


@dataclass
class Task:
    name: str
    tag: str
    colour: str
    start_line: int          # holds DB tasks.id
    sessions:      list[Session]   = field(default_factory=list)

    @property
    def db_id(self) -> int:
        return self.start_line
    goal_hours:    float           = 0.0   # target total hours (0 = no goal)
    goal_deadline: Optional[date]  = None  # optional deadline
    archived:      bool            = False

    # ── Clock state ──────────────────────────
    @property
    def open_session(self) -> Optional[Session]:
        for s in self.sessions:
            if s.is_open:
                return s
        return None

    @property
    def is_clocked_in(self) -> bool:
        return self.open_session is not None

    # ── Aggregates (all time) ────────────────
    @property
    def total_seconds(self) -> float:
        return sum(s.duration_seconds for s in self.sessions)

    @property
    def total_hours(self) -> float:
        return self.total_seconds / 3600

    @property
    def session_count(self) -> int:
        return len(self.sessions)

    @property
    def avg_session_seconds(self) -> float:
        closed = [s for s in self.sessions if not s.is_open]
        if not closed:
            return 0.0
        return sum(s.duration_seconds for s in closed) / len(closed)

    # ── Filtered aggregates ──────────────────
    def sessions_in_range(self, start: date, end: date) -> list[Session]:
        return [s for s in self.sessions if start <= s.date <= end]

    def seconds_in_range(self, start: date, end: date) -> float:
        return sum(s.duration_seconds for s in self.sessions_in_range(start, end))

    def hours_in_range(self, start: date, end: date) -> float:
        return self.seconds_in_range(start, end) / 3600

    # ── Goal helpers ─────────────────────────
    def goal_progress(self) -> float:
        """0.0–1.0, capped at 1."""
        if self.goal_hours <= 0:
            return 0.0
        return min(1.0, self.total_hours / self.goal_hours)

    def days_to_goal(self, daily_avg_hours: float) -> Optional[float]:
        """Estimated days to reach goal at current daily pace."""
        if self.goal_hours <= 0 or daily_avg_hours <= 0:
            return None
        remaining = max(0.0, self.goal_hours - self.total_hours)
        return remaining / daily_avg_hours

    def hours_remaining(self) -> float:
        return max(0.0, self.goal_hours - self.total_hours)

    def required_daily_hours(self) -> Optional[float]:
        """Hours/day needed to hit deadline. None if no deadline or already done."""
        if not self.goal_deadline or self.goal_hours <= 0:
            return None
        days_left = (self.goal_deadline - date.today()).days
        if days_left <= 0:
            return None
        remaining = self.hours_remaining()
        if remaining <= 0:
            return None
        return remaining / days_left

    def deadline_days_left(self) -> Optional[int]:
        if not self.goal_deadline:
            return None
        return (self.goal_deadline - date.today()).days


# ──────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────
def fmt_dur(seconds: float, short: bool = False) -> str:
    seconds = int(seconds)
    h, rem  = divmod(seconds, 3600)
    m, s    = divmod(rem, 60)
    if short:
        if h:   return f"{h}h {m:02d}m"
        if m:   return f"{m}m"
        return  f"{s}s"
    if h:   return f"{h}h {m:02d}m"
    if m:   return f"{m}m {s:02d}s"
    return  f"{s}s"


def fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def parse_dt(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")


CLOCK_PATTERN = re.compile(
    r"\[clock::(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})--([\dT:\-]*)\]"
)
TASK_PATTERN  = re.compile(r"^-\s+\[([ x])\]\s+(.*)")
TAG_PATTERN   = re.compile(r"#([\w-]+)")
