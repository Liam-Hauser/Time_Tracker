"""Test configuration: make `time_tracker` importable when running pytest from
the repo root, and provide a few shared fixtures for building Tasks/Sessions."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from time_tracker.core.models import Task, Session  # noqa: E402


def make_session(start: datetime, duration_minutes: float, *,
                 line_index: int = 1) -> Session:
    return Session(
        start=start,
        end=start + timedelta(minutes=duration_minutes),
        line_index=line_index,
    )


def make_task(name: str = "T", sessions: list[Session] | None = None,
              goal_hours: float = 0.0,
              goal_deadline: date | None = None) -> Task:
    return Task(
        name=name,
        tag="none",
        colour="#aaaaaa",
        start_line=1,
        sessions=list(sessions or []),
        goal_hours=goal_hours,
        goal_deadline=goal_deadline,
    )


@pytest.fixture
def make_task_factory():
    return make_task


@pytest.fixture
def make_session_factory():
    return make_session
