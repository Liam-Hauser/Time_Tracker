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


def run_pending_migrations(_env_path: Path | None = None) -> None:
    from sqlalchemy import inspect as sa_inspect
    from alembic.config import Config
    from alembic import command
    from database.db import engine

    # Locate alembic scripts — bundled inside exe or next to this file in dev
    if getattr(sys, "frozen", False):
        scripts_dir = Path(sys._MEIPASS) / "database" / "alembic"
    else:
        scripts_dir = Path(__file__).parent / "alembic"

    cfg = Config()
    cfg.set_main_option("script_location", str(scripts_dir))
    cfg.set_main_option("sqlalchemy.url", str(engine.url))

    tables = set(sa_inspect(engine).get_table_names())
    has_data = "tasks" in tables
    has_version = "alembic_version" in tables

    if has_data and not has_version:
        # Existing install predates Alembic tracking — mark as current so
        # future migrations apply without re-running the initial create.
        command.stamp(cfg, "head")
    else:
        command.upgrade(cfg, "head")
