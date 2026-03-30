"""Add categories table and seed initial categories

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INITIAL_CATEGORIES = [
    ("Mathematics",       "blue"),
    ("EOR",               "red"),
    ("Personal Projects", "yellow"),
    ("Personal Growth",   "white"),
    ("Interview Prep",    "purple"),
]


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id",         sa.Integer(), nullable=False),
        sa.Column("name",       sa.String(),  nullable=True),
        sa.Column("colour_tag", sa.String(),  nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    conn = op.get_bind()
    for name, colour_tag in _INITIAL_CATEGORIES:
        conn.execute(
            sa.text(
                "INSERT INTO categories (name, colour_tag) VALUES (:name, :tag)"
            ),
            {"name": name, "tag": colour_tag},
        )


def downgrade() -> None:
    op.drop_table("categories")
