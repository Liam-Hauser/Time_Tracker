"""
core/models.py — Pure data models. No UI, no file I/O.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Optional
import re


# ──────────────────────────────────────────────────────────
# Colour palette (mirrors the JS dashboard)
# ──────────────────────────────────────────────────────────
TAG_PALETTES: dict[str, list[str]] = {
    "blue":   ["#0C447C", "#185FA5", "#378ADD"],
    "red":    ["#A32D2D", "#DC3912", "#FF6655"],
    "yellow": ["#854F0B", "#FF9900", "#FFBB44"],
    "green":  ["#3B6D11", "#639922", "#97C459"],
    "purple": ["#534AB7", "#7F77DD", "#AFA9EC"],
    "brown":  ["#6B4F2E", "#8B6C42", "#A88B6A"],
    "white":  ["#888780", "#AAAAAA", "#CCCCCC"],
    "black":  ["#222222", "#444444", "#666666"],
    "none":   ["#5F5E5A", "#888780", "#B4B2A9"],
}


def colour_for_tag(tag: str, index: int) -> str:
    palette = TAG_PALETTES.get(tag, TAG_PALETTES["none"])
    return palette[min(index, len(palette) - 1)]


# ──────────────────────────────────────────────────────────
# Session
# ──────────────────────────────────────────────────────────
@dataclass
class Session:
    start: datetime
    end: Optional[datetime]   # None = currently clocked in
    line_index: int           # line in the source file

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
    hours:    float     = 0.0
    deadline: Optional[date] = None


@dataclass
class Task:
    name: str
    tag: str
    colour: str
    start_line: int
    sessions:      list[Session]   = field(default_factory=list)
    goal_hours:    float           = 0.0   # target total hours (0 = no goal)
    goal_deadline: Optional[date]  = None  # optional deadline

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
