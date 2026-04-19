"""Add archived column to goals

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-19
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'goals',
        sa.Column('archived', sa.Boolean(), server_default='0', nullable=False),
    )


def downgrade() -> None:
    op.drop_column('goals', 'archived')
