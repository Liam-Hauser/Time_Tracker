"""
core/analytics.py — All data aggregation and derived metrics.
Pure functions operating on ParseResult / Task lists.
"""

from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from .models import Task, Session, GoalSpec, fmt_dur
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

    def required_daily_hours(self, task_name: str) -> Optional[float]:
        t = next((t for t in self.tasks if t.name == task_name), None)
        if t is None:
            return None
        return t.required_daily_hours()

    def is_on_pace(self, task_name: str) -> Optional[bool]:
        req = self.required_daily_hours(task_name)
        if req is None:
            return None
        avg = self.daily_avg_hours(task_name)
        return avg >= req


# ──────────────────────────────────────────────────────────
# Per-task session stats
# ──────────────────────────────────────────────────────────
class TaskSessionStats:
    """All aggregations scoped to a single task within a date range."""

    def __init__(self, task: Task, start: date, end: date):
        self.task   = task
        self.start  = start
        self.end    = end
        self.sessions = task.sessions_in_range(start, end)
        self.closed   = [s for s in self.sessions if not s.is_open]
        self.session_durations: list[float] = [s.duration_seconds for s in self.closed]

        self.daily_seconds: dict[date, float] = defaultdict(float)
        for s in self.sessions:
            self.daily_seconds[s.date] += s.duration_seconds

        self.hour_seconds: dict[int, float] = defaultdict(float)
        for s in self.sessions:
            self.hour_seconds[s.hour] += s.duration_seconds

    @property
    def total_seconds(self) -> float:
        return sum(self.session_durations)

    @property
    def session_count(self) -> int:
        return len(self.closed)

    @property
    def avg_session_seconds(self) -> float:
        if not self.closed:
            return 0.0
        return self.total_seconds / len(self.closed)

    def session_length_buckets(self, bucket_min: int = 15) -> dict[int, int]:
        """Returns {bucket_start_minutes: count} histogram."""
        buckets: dict[int, int] = defaultdict(int)
        for sec in self.session_durations:
            m = int(sec / 60)
            bucket = (m // bucket_min) * bucket_min
            buckets[bucket] += 1
        return dict(sorted(buckets.items()))

    def cumulative_hours_by_date(self, dates: list[date]) -> list[float]:
        """Running total of hours up to each date."""
        cumul = 0.0
        result = []
        for d in dates:
            cumul += self.daily_seconds.get(d, 0.0) / 3600
            result.append(cumul)
        return result


# ──────────────────────────────────────────────────────────
# Category insights helper
# ──────────────────────────────────────────────────────────
def category_insights(category: str, tasks: list[Task],
                      stats: RangeStats) -> list[Insight]:
    """Produce a short list of Insight objects scoped to one category."""
    insights: list[Insight] = []
    cat_tasks = [t for t in tasks if t.tag == category]
    if not cat_tasks:
        return insights

    # Top task by hours in range
    top = max(cat_tasks, key=lambda t: stats.task_seconds.get(t.name, 0), default=None)
    if top and stats.task_seconds.get(top.name, 0) > 0:
        insights.append(Insight(
            "🏆", "Top task",
            top.name[:20],
            fmt_dur(stats.task_seconds[top.name], short=True) + " in range",
            "positive",
        ))

    # Category total vs last week
    try:
        comp_tw = RangeStats(cat_tasks, *this_week_range())
        comp_lw = RangeStats(cat_tasks, *last_week_range())
        delta = comp_tw.grand_total_seconds - comp_lw.grand_total_seconds
        sign  = "+" if delta >= 0 else "−"
        senti = "positive" if delta > 0 else ("negative" if delta < -900 else "neutral")
        insights.append(Insight(
            "📈" if delta >= 0 else "📉",
            "vs last week",
            f"{sign}{fmt_dur(abs(delta), short=True)}",
            f"this week: {fmt_dur(comp_tw.grand_total_seconds, short=True)}",
            senti,
        ))
    except Exception:
        pass

    # Most active hour within category
    if stats.by_hour:
        cat_names = {t.name for t in cat_tasks}
        hour_totals = {
            h: sum(v for k, v in secs.items() if k in cat_names)
            for h, secs in stats.by_hour.items()
        }
        if hour_totals:
            peak_h = max(hour_totals, key=hour_totals.__getitem__)
            if hour_totals[peak_h] > 0:
                insights.append(Insight(
                    "⏰", "Peak hour",
                    f"{peak_h:02d}:00–{peak_h+1:02d}:00",
                    fmt_dur(hour_totals[peak_h] / max(1, stats.n_days), short=True) + " avg/day",
                    "neutral",
                ))

    return insights


# ──────────────────────────────────────────────────────────
# Streak
# ──────────────────────────────────────────────────────────
def streak_days(tasks: list[Task], end_date: Optional[date] = None) -> int:
    """Consecutive days (ending at end_date) with any logged session."""
    end_date = end_date or date.today()
    logged = {s.date for t in tasks for s in t.sessions if not s.is_open}
    streak, check = 0, end_date
    while check in logged:
        streak += 1
        check -= timedelta(days=1)
    return streak


# ──────────────────────────────────────────────────────────
# Insight engine
# ──────────────────────────────────────────────────────────
@dataclass
class Insight:
    icon:      str
    label:     str
    value:     str
    sub:       str       = ""
    sentiment: str       = "neutral"   # positive | neutral | warning | negative


class InsightEngine:
    """Computes a list of Insight objects from current stats + goals."""

    def __init__(self, tasks: list[Task], stats: RangeStats,
                 goals: Optional[dict[str, GoalSpec]] = None):
        self._tasks  = tasks
        self._stats  = stats
        self._goals  = goals or {}

    def compute(self) -> list[Insight]:
        insights: list[Insight] = []

        # 1 — Best single day in range
        if self._stats.total_by_day:
            best_d, best_s = max(self._stats.total_by_day.items(),
                                 key=lambda kv: kv[1])
            insights.append(Insight("📅", "Best day in range",
                                    fmt_dur(best_s, short=True),
                                    best_d.strftime("%a %d %b").replace(" 0", " ") if hasattr(best_d, 'strftime') else str(best_d),
                                    "positive"))

        # 3 — Week-over-week delta
        try:
            comp = WeeklyComparison(self._tasks)
            delta = comp.total_delta()
            tw    = comp.this_week.grand_total_seconds
            senti = "positive" if delta > 0 else ("negative" if delta < -900 else "neutral")
            sign  = "+" if delta >= 0 else "−"
            insights.append(Insight(
                "📈" if delta >= 0 else "📉",
                "vs last week",
                f"{sign}{fmt_dur(abs(delta), short=True)}",
                f"this week: {fmt_dur(tw, short=True)}",
                senti,
            ))
        except Exception:
            pass

        # 4 — Most productive hour
        if self._stats.by_hour:
            peak_h = max(self._stats.by_hour,
                         key=lambda h: sum(self._stats.by_hour[h].values()))
            peak_s = sum(self._stats.by_hour[peak_h].values())
            insights.append(Insight("⏰", "Peak hour",
                                    f"{peak_h:02d}:00–{peak_h+1:02d}:00",
                                    fmt_dur(peak_s / max(1, self._stats.n_days),
                                            short=True) + " avg/day",
                                    "neutral"))

        # 5 — Best weekday
        wd = self._stats.most_consistent_weekday()
        if wd is not None:
            from ..ui.theme import WEEKDAY_NAMES  # late import avoids cycle
            insights.append(Insight("📆", "Most active day",
                                    WEEKDAY_NAMES[wd], "", "neutral"))

        return insights
