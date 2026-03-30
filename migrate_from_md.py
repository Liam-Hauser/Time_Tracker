#!/usr/bin/env python3
"""
migrate_from_md.py — One-time import of an Obsidian markdown vault into PostgreSQL.

Usage:
    python migrate_from_md.py /path/to/vault.md

What it does:
  - Reads every task from the .md file
  - Inserts tasks into the `tasks` table (skips duplicates by name)
  - Closed sessions  → `historic_clocks`
  - Open sessions    → `current_clocks`
  - Goals are NOT migrated (they were stored only in memory in the old app)

Run it once. Re-running is safe: tasks that already exist are skipped.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from time_tracker.core.parser import VaultParser
from database.db import SessionLocal
from database.models import Task as DBTask, HistoricClock, CurrentClock


def migrate(md_path: Path) -> None:
    if not md_path.exists():
        print(f"Error: file not found: {md_path}")
        sys.exit(1)

    print(f"Parsing {md_path} …")
    result = VaultParser().parse(md_path)
    print(f"Found {len(result.tasks)} tasks\n")

    with SessionLocal() as db:
        skipped = 0
        migrated = 0

        for task in result.tasks:
            existing = db.query(DBTask).filter_by(name=task.name).first()
            if existing:
                print(f"  SKIP  '{task.name}' (already in DB)")
                skipped += 1
                continue

            db_task = DBTask(
                name=task.name,
                category=task.tag,
                color=task.colour,
            )
            db.add(db_task)
            db.flush()  # populate db_task.id before inserting clocks

            closed_count = 0
            open_count   = 0

            for session in task.sessions:
                if session.end is None:
                    db.add(CurrentClock(
                        task_id=db_task.id,
                        start_time=session.start,
                    ))
                    open_count += 1
                else:
                    total_sec = int((session.end - session.start).total_seconds())
                    db.add(HistoricClock(
                        tasks_id=db_task.id,
                        total_sec=total_sec,
                        start_time=session.start,
                        end_time=session.end,
                    ))
                    closed_count += 1

            tag_info = f"#{task.tag}" if task.tag != "none" else ""
            print(
                f"  OK    '{task.name}' {tag_info}"
                f"  —  {closed_count} sessions"
                + (f"  +1 open" if open_count else "")
            )
            migrated += 1

        db.commit()

    print(f"\nDone.  Migrated: {migrated}  |  Skipped: {skipped}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    migrate(Path(sys.argv[1]))
