"""
core/db_store.py — PostgreSQL-backed data access.
Replaces VaultParser / VaultWriter with database reads and writes.

Task.start_line  is repurposed to hold the DB tasks.id.
Session.line_index is repurposed to hold the DB clock record id.
"""
from __future__ import annotations

import threading
from datetime import datetime
from typing import Optional

from .models import Task, Session, GoalSpec, colour_for_tag, CATEGORY_COLOUR_TAG
from .parser import ParseResult


class DBStore:
    """Thread-safe reads and writes against the PostgreSQL database."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    # ── Load ─────────────────────────────────────────────────

    def load(self) -> ParseResult:
        """Query all tasks and clock records; return an immutable ParseResult."""
        from database.db import SessionLocal
        from database.models import (
            Task as DBTask, HistoricClock, CurrentClock,
        )

        with SessionLocal() as db:
            db_tasks   = db.query(DBTask).all()
            historics  = db.query(HistoricClock).all()
            currents   = db.query(CurrentClock).all()

            # Group clocks by task id
            hist_by_task: dict[int, list] = {}
            for hc in historics:
                hist_by_task.setdefault(hc.tasks_id, []).append(hc)

            curr_by_task = {cc.task_id: cc for cc in currents}

            tag_counters: dict[str, int] = {}
            tasks: list[Task] = []

            for db_task in db_tasks:
                tag = db_task.category or "none"
                idx = tag_counters.get(tag, 0)
                tag_counters[tag] = idx + 1

                # Prefer stored colour; fall back to derived
                colour = db_task.color or colour_for_tag(tag, idx)

                sessions: list[Session] = []

                for hc in hist_by_task.get(db_task.id, []):
                    if hc.start_time and hc.end_time:
                        sessions.append(Session(
                            start=hc.start_time,
                            end=hc.end_time,
                            line_index=hc.id,   # repurposed: DB record id
                        ))

                cc = curr_by_task.get(db_task.id)
                if cc and cc.start_time:
                    sessions.append(Session(
                        start=cc.start_time,
                        end=None,
                        line_index=cc.id,       # repurposed: DB record id
                    ))

                tasks.append(Task(
                    name=db_task.name or "",
                    tag=tag,
                    colour=colour,
                    start_line=db_task.id,      # repurposed: DB task id
                    sessions=sessions,
                ))

        return ParseResult(tasks=tasks, raw_lines=[], parsed_at=datetime.now())

    # ── Create task ──────────────────────────────────────────

    def create_task(self, name: str, category: str) -> None:
        """Insert a new task row. Derives and stores the colour immediately."""
        from database.db import SessionLocal
        from database.models import Task as DBTask

        with self._lock:
            with SessionLocal() as db:
                existing = db.query(DBTask).filter_by(name=name).first()
                if existing:
                    raise ValueError(f"A task named '{name}' already exists")
                colour_tag = CATEGORY_COLOUR_TAG.get(category, "none")
                count  = db.query(DBTask).filter_by(category=category).count()
                colour = colour_for_tag(colour_tag, count)
                db.add(DBTask(name=name, category=category, color=colour))
                db.commit()

    # ── Task editing ─────────────────────────────────────────

    def rename_task(self, task_id: int, new_name: str) -> None:
        from database.db import SessionLocal
        from database.models import Task as DBTask, Goal as DBGoal

        with self._lock:
            with SessionLocal() as db:
                if db.query(DBTask).filter_by(name=new_name).first():
                    raise ValueError(f"A task named '{new_name}' already exists")
                task = db.get(DBTask, task_id)
                if task is None:
                    raise ValueError(f"Task id {task_id} not found")
                task.name = new_name
                for goal in db.query(DBGoal).filter_by(tasks_id=task_id).all():
                    goal.name = new_name
                db.commit()

    def move_task(self, task_id: int, new_category: str) -> None:
        from database.db import SessionLocal
        from database.models import Task as DBTask

        with self._lock:
            with SessionLocal() as db:
                task = db.get(DBTask, task_id)
                if task is None:
                    raise ValueError(f"Task id {task_id} not found")
                task.category = new_category
                count = db.query(DBTask).filter_by(category=new_category).count()
                colour_tag = CATEGORY_COLOUR_TAG.get(new_category, "none")
                task.color = colour_for_tag(colour_tag, count - 1)
                db.commit()

    def delete_task(self, task_id: int) -> None:
        from database.db import SessionLocal
        from database.models import (
            Task as DBTask, CurrentClock, HistoricClock, Goal as DBGoal,
        )

        with self._lock:
            with SessionLocal() as db:
                db.query(CurrentClock).filter_by(task_id=task_id).delete()
                db.query(HistoricClock).filter_by(tasks_id=task_id).delete()
                db.query(DBGoal).filter_by(tasks_id=task_id).delete()
                task = db.get(DBTask, task_id)
                if task:
                    db.delete(task)
                db.commit()

    # ── Categories ───────────────────────────────────────────

    def load_categories(self) -> list[tuple[str, str]]:
        """Return list of (name, colour_tag) for all categories."""
        from database.db import SessionLocal
        from database.models import Category as DBCategory

        with SessionLocal() as db:
            rows = db.query(DBCategory).order_by(DBCategory.name).all()
            return [(r.name, r.colour_tag or "none") for r in rows]

    def create_category(self, name: str, colour_tag: str) -> None:
        """Insert a new category row."""
        from database.db import SessionLocal
        from database.models import Category as DBCategory

        with self._lock:
            with SessionLocal() as db:
                existing = db.query(DBCategory).filter_by(name=name).first()
                if existing:
                    raise ValueError(f"A category named '{name}' already exists")
                db.add(DBCategory(name=name, colour_tag=colour_tag))
                db.commit()

    # ── Goals ────────────────────────────────────────────────

    def load_goals(self) -> dict[str, GoalSpec]:
        """Return a mapping of task name → GoalSpec from the goals table."""
        from database.db import SessionLocal
        from database.models import Goal as DBGoal, Task as DBTask

        with SessionLocal() as db:
            rows = (
                db.query(DBGoal, DBTask)
                .join(DBTask, DBGoal.tasks_id == DBTask.id)
                .all()
            )
            return {
                db_task.name: GoalSpec(
                    hours=float(goal.target_hours or 0),
                    deadline=goal.by_date.date() if goal.by_date else None,
                )
                for goal, db_task in rows
            }

    def save_goals(self, goals: dict[str, GoalSpec],
                   tasks: list[Task]) -> None:
        """Upsert goals for each task. tasks must come from a ParseResult
        produced by load() so that Task.start_line holds the DB task id."""
        from database.db import SessionLocal
        from database.models import Goal as DBGoal

        task_id_by_name = {t.name: t.start_line for t in tasks}

        with SessionLocal() as db:
            for task_name, gs in goals.items():
                task_id = task_id_by_name.get(task_name)
                if task_id is None:
                    continue
                by_date = (
                    datetime(gs.deadline.year, gs.deadline.month, gs.deadline.day)
                    if gs.deadline else None
                )
                existing = db.query(DBGoal).filter_by(tasks_id=task_id).first()
                if existing:
                    existing.target_hours = int(round(gs.hours))
                    existing.by_date      = by_date
                    existing.name         = task_name
                else:
                    db.add(DBGoal(
                        tasks_id=task_id,
                        name=task_name,
                        target_hours=int(round(gs.hours)),
                        by_date=by_date,
                    ))
            db.commit()

    # ── Clock in / out ───────────────────────────────────────

    def clock_in(self, task_name: str, result: ParseResult) -> None:
        task = result.task_by_name(task_name)
        if task is None:
            raise ValueError(f"Task '{task_name}' not found")
        if task.is_clocked_in:
            raise RuntimeError(f"'{task_name}' is already clocked in")

        from database.db import SessionLocal
        from database.models import CurrentClock

        with self._lock:
            with SessionLocal() as db:
                db.add(CurrentClock(
                    task_id=task.start_line,
                    start_time=datetime.now(),
                ))
                db.commit()

    def clock_out(self, task_name: str, result: ParseResult) -> None:
        task = result.task_by_name(task_name)
        if task is None:
            raise ValueError(f"Task '{task_name}' not found")
        open_s = task.open_session
        if open_s is None:
            raise RuntimeError(f"'{task_name}' is not clocked in")

        from database.db import SessionLocal
        from database.models import CurrentClock, HistoricClock

        with self._lock:
            with SessionLocal() as db:
                cc = db.get(CurrentClock, open_s.line_index)
                if cc is None:
                    raise RuntimeError("Current clock record not found in database")
                now       = datetime.now()
                total_sec = int((now - cc.start_time).total_seconds())
                db.add(HistoricClock(
                    tasks_id=cc.task_id,
                    total_sec=total_sec,
                    start_time=cc.start_time,
                    end_time=now,
                ))
                db.delete(cc)
                db.commit()

    # ── Session management ───────────────────────────────────

    def add_session(self, task_id: int,
                    start_dt: datetime, end_dt: datetime) -> None:
        """Insert a manually-logged historic session."""
        from database.db import SessionLocal
        from database.models import HistoricClock
        total_sec = int((end_dt - start_dt).total_seconds())
        with self._lock:
            with SessionLocal() as db:
                db.add(HistoricClock(
                    tasks_id=task_id,
                    total_sec=total_sec,
                    start_time=start_dt,
                    end_time=end_dt,
                ))
                db.commit()

    def update_session(self, session_id: int,
                       new_start: datetime, new_end: datetime) -> None:
        """Update start/end times of a HistoricClock record."""
        from database.db import SessionLocal
        from database.models import HistoricClock
        with self._lock:
            with SessionLocal() as db:
                hc = db.get(HistoricClock, session_id)
                if hc is None:
                    raise ValueError(f"Session {session_id} not found")
                hc.start_time = new_start
                hc.end_time   = new_end
                hc.total_sec  = int((new_end - new_start).total_seconds())
                db.commit()

    def delete_session(self, session_id: int, is_open: bool = False) -> None:
        """Delete a clock record (HistoricClock or CurrentClock)."""
        from database.db import SessionLocal
        from database.models import HistoricClock, CurrentClock
        with self._lock:
            with SessionLocal() as db:
                rec = (
                    db.get(CurrentClock, session_id)
                    if is_open
                    else db.get(HistoricClock, session_id)
                )
                if rec:
                    db.delete(rec)
                    db.commit()
