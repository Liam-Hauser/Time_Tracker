from datetime import date, datetime, timedelta

from tests.conftest import make_session, make_task


def test_required_daily_hours_returns_none_without_deadline():
    t = make_task(goal_hours=10)
    assert t.required_daily_hours() is None


def test_required_daily_hours_returns_none_for_zero_goal():
    t = make_task(goal_hours=0, goal_deadline=date.today() + timedelta(days=7))
    assert t.required_daily_hours() is None


def test_required_daily_hours_returns_none_after_deadline():
    t = make_task(goal_hours=10, goal_deadline=date.today() - timedelta(days=1))
    assert t.required_daily_hours() is None


def test_required_daily_hours_returns_remaining_per_day_left():
    t = make_task(goal_hours=10, goal_deadline=date.today() + timedelta(days=10))
    # No work logged → need 1.0 h/day for 10 days.
    assert abs(t.required_daily_hours() - 1.0) < 1e-6


def test_goal_progress_caps_at_one():
    today = date.today()
    sessions = [make_session(datetime(today.year, today.month, today.day, 9, 0), 600)]
    t = make_task(sessions=sessions, goal_hours=5)  # 10h logged, 5h goal → 200%, capped
    assert t.goal_progress() == 1.0


def test_goal_progress_zero_for_zero_goal():
    assert make_task(goal_hours=0).goal_progress() == 0.0
