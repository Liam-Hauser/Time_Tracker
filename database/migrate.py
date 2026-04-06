"""
database/migrate.py — Runs Alembic migrations on every app launch.

Three cases handled automatically:
  1. Fresh DB (no tables)         → runs all migrations from scratch
  2. Existing DB + alembic_version → applies any pending migrations
  3. Existing DB, no alembic_version (pre-Alembic install) → stamps head,
     then future migrations will apply on top
"""
from __future__ import annotations

import sys
from pathlib import Path


def _ensure_columns(engine, sa_inspect) -> None:
    """Idempotently add columns that Alembic migrations may have missed."""
    import sqlalchemy as sa

    existing = {c["name"] for c in sa_inspect(engine).get_columns("tasks")}
    with engine.begin() as conn:
        if "archived" not in existing:
            conn.execute(sa.text(
                "ALTER TABLE tasks ADD COLUMN archived BOOLEAN NOT NULL DEFAULT 0"
            ))


def run_pending_migrations(_env_path: Path | None = None) -> None:
    from sqlalchemy import inspect as sa_inspect
    from alembic.config import Config
    from alembic import command
    from database.db import engine

    # Locate alembic scripts — bundled inside exe or next to this file in dev
    if getattr(sys, "frozen", False):
        scripts_dir = Path(sys._MEIPASS) / "database" / "alembic"
        # Alembic imports migration scripts by file path; sys._MEIPASS must be
        # on sys.path so those imports resolve inside the frozen bundle.
        meipass = str(sys._MEIPASS)
        if meipass not in sys.path:
            sys.path.insert(0, meipass)
    else:
        scripts_dir = Path(__file__).parent / "alembic"

    cfg = Config()
    cfg.set_main_option("script_location", str(scripts_dir))
    cfg.set_main_option("sqlalchemy.url", str(engine.url))

    tables = set(sa_inspect(engine).get_table_names())
    has_data = "tasks" in tables
    has_version = "alembic_version" in tables

    if has_data and not has_version:
        # Existing install predates Alembic tracking — stamp at the initial
        # revision (not head) so pending migrations like 0002+ still run.
        command.stamp(cfg, "0001")

    command.upgrade(cfg, "head")

    # Safety net: Alembic can silently fail to discover migration scripts in a
    # frozen exe (PyInstaller). Apply any schema changes that are cheap to
    # verify idempotently with raw SQL so the app never crashes on a missing
    # column even if the Alembic runner misbehaves.
    _ensure_columns(engine, sa_inspect)
