from datetime import date, timedelta

from time_tracker.core.analytics import (
    monday_of, this_week_range, last_week_range, last_n_days,
)


def test_monday_of_returns_monday_for_each_weekday():
    sun = date(2026, 5, 3)   # Sunday
    mon = date(2026, 5, 4)   # Monday
    tue = date(2026, 5, 5)
    sat = date(2026, 5, 9)
    assert monday_of(sun) == date(2026, 4, 27)
    assert monday_of(mon) == mon
    assert monday_of(tue) == mon
    assert monday_of(sat) == mon


def test_last_n_days_window_is_inclusive():
    start, end = last_n_days(7)
    assert end == date.today()
    assert (end - start).days == 6  # 7 days inclusive


def test_this_and_last_week_are_contiguous():
    tw_s, tw_e = this_week_range()
    lw_s, lw_e = last_week_range()
    assert tw_e == date.today()
    assert lw_e + timedelta(days=1) == tw_s
    assert (lw_e - lw_s).days == 6
