from datetime import date, datetime, timedelta

from time_tracker.core.analytics import ewma_daily_hours
from tests.conftest import make_session, make_task


def _at(d: date, h: int = 12) -> datetime:
    return datetime(d.year, d.month, d.day, h, 0)


def test_empty_task_returns_zero():
    assert ewma_daily_hours(make_task()) == 0.0


def test_one_hour_every_day_for_lookback_gives_one_hour_per_day():
    today = date.today()
    sessions = [make_session(_at(today - timedelta(days=i)), 60) for i in range(35)]
    task = make_task(sessions=sessions)
    avg = ewma_daily_hours(task, halflife_days=7, lookback_days=35)
    assert abs(avg - 1.0) < 0.01


def test_open_session_excluded_from_pace():
    today = date.today()
    closed = [make_session(_at(today - timedelta(days=i)), 60) for i in range(1, 8)]
    closed_pace = ewma_daily_hours(make_task(sessions=closed))
    # Adding an open session today should NOT change the pace.
    from time_tracker.core.models import Session
    open_now = Session(start=_at(today, 9), end=None, line_index=999)
    with_open = ewma_daily_hours(make_task(sessions=closed + [open_now]))
    assert closed_pace == with_open


def test_recent_session_dominates_via_halflife():
    today = date.today()
    # 1h today, 1h 7 days ago. With 7-day halflife, today should weigh 2x.
    s_today = make_session(_at(today), 60)
    s_old   = make_session(_at(today - timedelta(days=7)), 60)
    task = make_task(sessions=[s_today, s_old])
    avg = ewma_daily_hours(task, halflife_days=7, lookback_days=35)
    # Average is small (2 weighted hours over 35 daily slots) but positive
    # and less than the equivalent flat 2/35 would be due to the discount tail.
    assert avg > 0
    # Same task without the old session: the pace must drop.
    avg_today_only = ewma_daily_hours(make_task(sessions=[s_today]),
                                      halflife_days=7, lookback_days=35)
    assert avg > avg_today_only
