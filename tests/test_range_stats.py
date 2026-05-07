from datetime import date, datetime, timedelta

from time_tracker.core.analytics import RangeStats
from tests.conftest import make_session, make_task


def test_by_hour_distributes_session_across_clock_hours():
    # 09:30 to 11:30 → 30 min in h=9, 60 min in h=10, 30 min in h=11
    today = date.today()
    s = make_session(datetime(today.year, today.month, today.day, 9, 30), 120)
    task = make_task(sessions=[s])
    rs = RangeStats([task], today, today)
    assert abs(rs.by_hour[9][task.name]  - 1800) < 1
    assert abs(rs.by_hour[10][task.name] - 3600) < 1
    assert abs(rs.by_hour[11][task.name] - 1800) < 1


def test_open_session_contributes_live_time_to_by_hour():
    # An open session started 30 minutes ago should appear in the heatmap.
    now = datetime.now()
    half_hour_ago = now - timedelta(minutes=30)
    from time_tracker.core.models import Session
    open_s = Session(start=half_hour_ago, end=None, line_index=1)
    task = make_task(sessions=[open_s])
    rs = RangeStats([task], date.today(), date.today())
    total = sum(rs.by_hour[h][task.name] for h in range(24))
    assert total > 0


def test_daily_buckets_use_session_start_date():
    today = date.today()
    yesterday = today - timedelta(days=1)
    s_y = make_session(datetime(yesterday.year, yesterday.month, yesterday.day, 9, 0), 60)
    s_t = make_session(datetime(today.year, today.month, today.day, 9, 0), 30)
    task = make_task(sessions=[s_y, s_t])
    rs = RangeStats([task], yesterday, today)
    assert abs(rs.daily[yesterday][task.name] - 3600) < 1
    assert abs(rs.daily[today][task.name]     - 1800) < 1
