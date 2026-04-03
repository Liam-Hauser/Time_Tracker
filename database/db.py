"""
database/db.py — SQLAlchemy engine and session factory.

Uses SQLite. The database file is stored in:
  - Frozen (exe): %LOCALAPPDATA%/TimeTracker/timetracker.db
  - Dev:          <project root>/timetracker.db
"""
import os
import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def _get_db_path() -> Path:
    if getattr(sys, "frozen", False):
        local_appdata = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        db_dir = Path(local_appdata) / "TimeTracker"
        db_dir.mkdir(parents=True, exist_ok=True)
        return db_dir / "timetracker.db"
    else:
        return Path(__file__).parent.parent / "timetracker.db"


_db_path = _get_db_path()
engine = create_engine(
    f"sqlite:///{_db_path}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine)
