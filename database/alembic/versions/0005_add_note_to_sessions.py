"""Add note column to historic_clocks and current_clocks

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-20
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0005'
down_revision: Union[str, Sequence[str], None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('historic_clocks', sa.Column('note', sa.Text(), nullable=True))
    op.add_column('current_clocks',  sa.Column('note', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('historic_clocks', 'note')
    op.drop_column('current_clocks',  'note')
