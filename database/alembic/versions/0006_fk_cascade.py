"""Add ondelete=CASCADE to task foreign keys.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-07

SQLite has no ALTER TABLE for foreign keys, so each child table is
recreated with the new FK constraint. The original FKs were anonymous,
so a raw-SQL table-copy is more robust than alembic batch operations.
"""
from typing import Sequence, Union
from alembic import op

revision: str = '0006'
down_revision: Union[str, Sequence[str], None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _recreate(create_sql: str, table: str, columns: list[str]) -> None:
    new_table = f"{table}__new"
    cols = ", ".join(columns)
    op.execute(create_sql.replace(f"CREATE TABLE {table}",
                                  f"CREATE TABLE {new_table}"))
    op.execute(f"INSERT INTO {new_table} ({cols}) SELECT {cols} FROM {table}")
    op.execute(f"DROP TABLE {table}")
    op.execute(f"ALTER TABLE {new_table} RENAME TO {table}")


def upgrade() -> None:
    op.execute("PRAGMA foreign_keys=OFF")
    _recreate(
        """
        CREATE TABLE historic_clocks (
            id INTEGER PRIMARY KEY,
            tasks_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
            total_sec INTEGER,
            start_time DATETIME,
            end_time DATETIME,
            note TEXT
        )
        """,
        "historic_clocks",
        ["id", "tasks_id", "total_sec", "start_time", "end_time", "note"],
    )
    _recreate(
        """
        CREATE TABLE current_clocks (
            id INTEGER PRIMARY KEY,
            task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
            start_time DATETIME,
            note TEXT
        )
        """,
        "current_clocks",
        ["id", "task_id", "start_time", "note"],
    )
    _recreate(
        """
        CREATE TABLE goals (
            id INTEGER PRIMARY KEY,
            tasks_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
            name VARCHAR,
            target_hours INTEGER,
            by_date DATETIME,
            completed_on DATETIME,
            archived BOOLEAN NOT NULL DEFAULT '0'
        )
        """,
        "goals",
        ["id", "tasks_id", "name", "target_hours", "by_date",
         "completed_on", "archived"],
    )
    op.execute("PRAGMA foreign_keys=ON")


def downgrade() -> None:
    op.execute("PRAGMA foreign_keys=OFF")
    _recreate(
        """
        CREATE TABLE historic_clocks (
            id INTEGER PRIMARY KEY,
            tasks_id INTEGER REFERENCES tasks(id),
            total_sec INTEGER,
            start_time DATETIME,
            end_time DATETIME,
            note TEXT
        )
        """,
        "historic_clocks",
        ["id", "tasks_id", "total_sec", "start_time", "end_time", "note"],
    )
    _recreate(
        """
        CREATE TABLE current_clocks (
            id INTEGER PRIMARY KEY,
            task_id INTEGER REFERENCES tasks(id),
            start_time DATETIME,
            note TEXT
        )
        """,
        "current_clocks",
        ["id", "task_id", "start_time", "note"],
    )
    _recreate(
        """
        CREATE TABLE goals (
            id INTEGER PRIMARY KEY,
            tasks_id INTEGER REFERENCES tasks(id),
            name VARCHAR,
            target_hours INTEGER,
            by_date DATETIME,
            completed_on DATETIME,
            archived BOOLEAN NOT NULL DEFAULT '0'
        )
        """,
        "goals",
        ["id", "tasks_id", "name", "target_hours", "by_date",
         "completed_on", "archived"],
    )
    op.execute("PRAGMA foreign_keys=ON")
