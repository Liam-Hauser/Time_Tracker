"""Add completed_on column to goals

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-19
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'goals',
        sa.Column('completed_on', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('goals', 'completed_on')
