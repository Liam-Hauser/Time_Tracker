"""
core/db_store.py — SQLite-backed data access via SQLAlchemy.

Task.start_line  holds the DB tasks.id.
Session.line_index holds the DB clock record id.
"""
from __future__ import annotations

import threading
from datetime import datetime
from typing import Optional

from .models import Task, Session, GoalSpec, generate_category_colors
from .parser import ParseResult


class DBStore:
    """Thread-safe reads and writes against the SQLite database."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    @staticmethod
    def _get_task(db, task_id: int):
        """Fetch a DB Task by id, raise ValueError if missing."""
        from database.models import Task as DBTask
        task = db.get(DBTask, task_id)
        if task is None:
            raise ValueError(f"Task id {task_id} not found")
        return task

    # ── Load ─────────────────────────────────────────────────

    def load(self) -> ParseResult:
        """Query all tasks and clock records; return an immutable ParseResult."""
        from database.db import SessionLocal
        from database.models import (
            Task as DBTask, HistoricClock, CurrentClock, Category as DBCategory,
        )

        with SessionLocal() as db:
            db_tasks   = db.query(DBTask).all()
            historics  = db.query(HistoricClock).all()
            currents   = db.query(CurrentClock).all()
            categories = db.query(DBCategory).all()

            cat_colour_tags = {c.name: (c.colour_tag or "none") for c in categories}

            # Group clocks by task id
            hist_by_task: dict[int, list] = {}
            for hc in historics:
                hist_by_task.setdefault(hc.tasks_id, []).append(hc)

            curr_by_task = {cc.task_id: cc for cc in currents}

            tasks: list[Task] = []

            for db_task in db_tasks:
                tag = db_task.category or "none"

                sessions: list[Session] = []

                for hc in hist_by_task.get(db_task.id, []):
                    if hc.start_time and hc.end_time:
                        sessions.append(Session(
                            start=hc.start_time,
                            end=hc.end_time,
                            line_index=hc.id,   # repurposed: DB record id
                            note=hc.note or "",
                        ))

                cc = curr_by_task.get(db_task.id)
                if cc and cc.start_time:
                    sessions.append(Session(
                        start=cc.start_time,
                        end=None,
                        line_index=cc.id,       # repurposed: DB record id
                        note=cc.note or "",
                    ))

                tasks.append(Task(
                    name=db_task.name or "",
                    tag=tag,
                    colour="#888888",           # placeholder; assigned below
                    start_line=db_task.id,      # repurposed: DB task id
                    sessions=sessions,
                    archived=bool(db_task.archived),
                ))

        # Assign gradient colors per category.
        # Sort by total seconds desc (most-used = index 0 = darkest) then by
        # db_id asc as a stable tie-breaker so colors don't shuffle on ties.
        from .models import hue_for_tag
        from collections import defaultdict

        tasks_by_cat: dict[str, list[Task]] = {}
        for t in tasks:
            tasks_by_cat.setdefault(t.tag, []).append(t)

        # Compute base hue per category, then spread any that share the same hue
        # so distinct categories never end up the same colour family.
        cat_hues: dict[str, int] = {
            cat: hue_for_tag(cat_colour_tags.get(cat, "none"))
            for cat in tasks_by_cat
        }
        hue_groups: dict[int, list[str]] = defaultdict(list)
        for cat, hue in cat_hues.items():
            hue_groups[hue].append(cat)

        for hue, shared_cats in hue_groups.items():
            if len(shared_cats) > 1:
                shared_cats = sorted(shared_cats)   # stable order
                n = len(shared_cats)
                step = 45                            # degrees between each sibling
                half_span = step * (n - 1) / 2
                for i, cat in enumerate(shared_cats):
                    cat_hues[cat] = int((hue + i * step - half_span) % 360)

        for cat_name, cat_tasks in tasks_by_cat.items():
            hue = cat_hues.get(cat_name, 210)
            cat_tasks.sort(key=lambda t: (-t.total_seconds, t.start_line))
            colors = generate_category_colors(str(hue), len(cat_tasks))
            for task, color in zip(cat_tasks, colors):
                task.colour = color

        return ParseResult(tasks=tasks, raw_lines=[], parsed_at=datetime.now())

    # ── Create task ──────────────────────────────────────────

    def create_task(self, name: str, category: str) -> None:
        """Insert a new task row. Color is computed dynamically on load()."""
        from database.db import SessionLocal
        from database.models import Task as DBTask

        with self._lock:
            with SessionLocal() as db:
                existing = db.query(DBTask).filter_by(name=name).first()
                if existing:
                    raise ValueError(f"A task named '{name}' already exists")
                db.add(DBTask(name=name, category=category))
                db.commit()

    # ── Task editing ─────────────────────────────────────────

    def rename_task(self, task_id: int, new_name: str) -> None:
        from database.db import SessionLocal
        from database.models import Task as DBTask, Goal as DBGoal

        with self._lock:
            with SessionLocal() as db:
                if db.query(DBTask).filter_by(name=new_name).first():
                    raise ValueError(f"A task named '{new_name}' already exists")
                task = self._get_task(db, task_id)
                task.name = new_name
                for goal in db.query(DBGoal).filter_by(tasks_id=task_id).all():
                    goal.name = new_name
                db.commit()

    def move_task(self, task_id: int, new_category: str) -> None:
        from database.db import SessionLocal
        from database.models import Task as DBTask

        with self._lock:
            with SessionLocal() as db:
                task = self._get_task(db, task_id)
                task.category = new_category
                db.commit()

    def set_archived(self, task_id: int, archived: bool) -> None:
        from database.db import SessionLocal

        with self._lock:
            with SessionLocal() as db:
                task = self._get_task(db, task_id)
                task.archived = archived
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

    def recolor_category(self, cat_name: str, new_colour_tag: str) -> None:
        """Update a category's colour_tag. Colors are recomputed on next load()."""
        from database.db import SessionLocal
        from database.models import Category as DBCategory

        with self._lock:
            with SessionLocal() as db:
                cat = db.query(DBCategory).filter_by(name=cat_name).first()
                if cat is None:
                    raise ValueError(f"Category '{cat_name}' not found")
                cat.colour_tag = new_colour_tag
                db.commit()

    def rename_category(self, old_name: str, new_name: str) -> None:
        """Rename a category and update all tasks that belong to it."""
        from database.db import SessionLocal
        from database.models import Category as DBCategory, Task as DBTask

        with self._lock:
            with SessionLocal() as db:
                cat = db.query(DBCategory).filter_by(name=old_name).first()
                if cat is None:
                    raise ValueError(f"Category '{old_name}' not found")
                if db.query(DBCategory).filter_by(name=new_name).first():
                    raise ValueError(f"A category named '{new_name}' already exists")
                cat.name = new_name
                db.query(DBTask).filter_by(category=old_name).update({"category": new_name})
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
                    completed_on=goal.completed_on.date() if goal.completed_on else None,
                    archived=bool(goal.archived),
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
                completed_on = (
                    datetime(gs.completed_on.year, gs.completed_on.month, gs.completed_on.day)
                    if gs.completed_on else None
                )
                existing = db.query(DBGoal).filter_by(tasks_id=task_id).first()
                if existing:
                    existing.target_hours = int(round(gs.hours))
                    existing.by_date      = by_date
                    existing.name         = task_name
                    existing.completed_on = completed_on
                    existing.archived     = gs.archived
                else:
                    db.add(DBGoal(
                        tasks_id=task_id,
                        name=task_name,
                        target_hours=int(round(gs.hours)),
                        by_date=by_date,
                        completed_on=completed_on,
                        archived=gs.archived,
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
                    start_dt: datetime, end_dt: datetime,
                    note: str = "") -> None:
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
                    note=note or None,
                ))
                db.commit()

    def update_session(self, session_id: int,
                       new_start: datetime, new_end: datetime,
                       note: str = "") -> None:
        """Update start/end times and note of a HistoricClock record."""
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
                hc.note       = note or None
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
