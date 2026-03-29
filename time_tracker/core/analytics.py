"""
core/analytics.py — All data aggregation and derived metrics.
Pure functions operating on ParseResult / Task lists.
"""

from __future__ import annotations
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

import numpy as np

from .models import Task, Session, fmt_dur
from .parser import ParseResult


# ──────────────────────────────────────────────────────────
# Date helpers
# ──────────────────────────────────────────────────────────
def date_range(start: date, end: date) -> list[date]:
    days = []
    d = start
    while d <= end:
        days.append(d)
        d += timedelta(days=1)
    return days


def this_week_range() -> tuple[date, date]:
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return monday, today


def last_week_range() -> tuple[date, date]:
    monday, _ = this_week_range()
    end   = monday - timedelta(days=1)
    start = end - timedelta(days=6)
    return start, end


def this_month_range() -> tuple[date, date]:
    today = date.today()
    return today.replace(day=1), today


def last_month_range() -> tuple[date, date]:
    first_this = date.today().replace(day=1)
    last_prev  = first_this - timedelta(days=1)
    return last_prev.replace(day=1), last_prev


def last_n_days(n: int) -> tuple[date, date]:
    today = date.today()
    return today - timedelta(days=n - 1), today


# ──────────────────────────────────────────────────────────
# Filtered aggregates
# ──────────────────────────────────────────────────────────
class RangeStats:
    """Pre-computed stats for a given date range."""

    def __init__(self, tasks: list[Task], start: date, end: date):
        self.tasks      = tasks
        self.start      = start
        self.end        = end
        self.days       = date_range(start, end)
        self.n_days     = len(self.days)

        # task → total seconds in range
        self.task_seconds: dict[str, float] = {
            t.name: t.seconds_in_range(start, end) for t in tasks
        }

        # date → {task_name: seconds}
        self.daily: dict[date, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for t in tasks:
            for s in t.sessions_in_range(start, end):
                self.daily[s.date][t.name] += s.duration_seconds

        # weekday (0=Mon) → {task_name: seconds}
        self.by_weekday: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        # weekday → count of days in range that fall on that weekday
        weekday_counts: dict[int, int] = defaultdict(int)
        for d in self.days:
            weekday_counts[d.weekday()] += 1
        for d, tasks_sec in self.daily.items():
            wd = d.weekday()
            for name, sec in tasks_sec.items():
                self.by_weekday[wd][name] += sec
        # Convert to averages
        self.avg_by_weekday: dict[int, dict[str, float]] = {}
        for wd in range(7):
            cnt = max(1, weekday_counts[wd])
            self.avg_by_weekday[wd] = {
                name: sec / cnt
                for name, sec in self.by_weekday[wd].items()
            }

        # hour (0-23) → {task_name: seconds}
        self.by_hour: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for t in tasks:
            for s in t.sessions_in_range(start, end):
                self.by_hour[s.hour][t.name] += s.duration_seconds

        # total seconds per day (across all tasks)
        self.total_by_day: dict[date, float] = {
            d: sum(v.values()) for d, v in self.daily.items()
        }

    @property
    def grand_total_seconds(self) -> float:
        return sum(self.task_seconds.values())

    @property
    def active_tasks(self) -> list[Task]:
        return [t for t in self.tasks if self.task_seconds.get(t.name, 0) > 0]

    def most_consistent_weekday(self) -> Optional[int]:
        """Weekday (0=Mon) with the highest number of sessions."""
        wd_counts: dict[int, int] = defaultdict(int)
        for t in self.tasks:
            for s in t.sessions_in_range(self.start, self.end):
                wd_counts[s.date.weekday()] += 1
        if not wd_counts:
            return None
        return max(wd_counts, key=wd_counts.__getitem__)

    def avg_session_seconds(self, task_name: str) -> float:
        t = next((t for t in self.tasks if t.name == task_name), None)
        if not t:
            return 0.0
        sessions = [s for s in t.sessions_in_range(self.start, self.end)
                    if not s.is_open]
        if not sessions:
            return 0.0
        return sum(s.duration_seconds for s in sessions) / len(sessions)


# ──────────────────────────────────────────────────────────
# Weekly comparison
# ──────────────────────────────────────────────────────────
class WeeklyComparison:
    def __init__(self, tasks: list[Task]):
        tw_start, tw_end = this_week_range()
        lw_start, lw_end = last_week_range()
        self.this_week = RangeStats(tasks, tw_start, tw_end)
        self.last_week = RangeStats(tasks, lw_start, lw_end)

    def delta_seconds(self, task_name: str) -> float:
        return (self.this_week.task_seconds.get(task_name, 0)
                - self.last_week.task_seconds.get(task_name, 0))

    def total_delta(self) -> float:
        return (self.this_week.grand_total_seconds
                - self.last_week.grand_total_seconds)


# ──────────────────────────────────────────────────────────
# Goal tracking
# ──────────────────────────────────────────────────────────
class GoalTracker:
    def __init__(self, tasks: list[Task], stats: RangeStats):
        self.tasks = tasks
        self.stats = stats

    def daily_avg_hours(self, task_name: str) -> float:
        t = next((t for t in self.tasks if t.name == task_name), None)
        if not t:
            return 0.0
        active_days = {s.date for s in t.sessions if not s.is_open}
        if not active_days:
            return 0.0
        return t.total_hours / len(active_days)

    def eta_days(self, task_name: str) -> Optional[float]:
        t = next((t for t in self.tasks if t.name == task_name), None)
        if not t or t.goal_hours <= 0:
            return None
        daily_avg = self.daily_avg_hours(task_name)
        return t.days_to_goal(daily_avg)
