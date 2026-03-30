"""Rename categories from colour names to proper names; move Market Making to Personal Projects

Revision ID: a1b2c3d4e5f6
Revises: 807e00921abb
Create Date: 2026-03-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '807e00921abb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Colour → proper category name mapping
_RENAMES = {
    "blue":   "Mathematics",
    "red":    "EOR",
    "yellow": "Personal Projects",
    "white":  "Personal Growth",
    "purple": "Interview Prep",
}

# Middle shade for the yellow palette (used for Market Making after reassignment)
_YELLOW_COLOUR = "#FF9900"


def upgrade() -> None:
    conn = op.get_bind()

    # Rename colour-named categories to proper names
    for old_name, new_name in _RENAMES.items():
        conn.execute(
            sa.text("UPDATE tasks SET category = :new WHERE category = :old"),
            {"new": new_name, "old": old_name},
        )

    # Move Market Making from brown → Personal Projects (yellow colour)
    conn.execute(
        sa.text(
            "UPDATE tasks SET category = 'Personal Projects', color = :colour "
            "WHERE name = 'Market Making'"
        ),
        {"colour": _YELLOW_COLOUR},
    )


def downgrade() -> None:
    conn = op.get_bind()

    # Restore Market Making to brown
    conn.execute(
        sa.text(
            "UPDATE tasks SET category = 'brown', color = '#8B6C42' "
            "WHERE name = 'Market Making'"
        )
    )

    # Reverse category renames
    for old_name, new_name in _RENAMES.items():
        conn.execute(
            sa.text("UPDATE tasks SET category = :old WHERE category = :new"),
            {"old": old_name, "new": new_name},
        )
