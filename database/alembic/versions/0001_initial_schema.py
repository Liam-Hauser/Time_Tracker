"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-03
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tasks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String()),
        sa.Column('category', sa.String()),
        sa.Column('color', sa.String()),
    )
    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(), unique=True),
        sa.Column('colour_tag', sa.String()),
    )
    op.create_table(
        'historic_clocks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tasks_id', sa.Integer(), sa.ForeignKey('tasks.id')),
        sa.Column('total_sec', sa.Integer()),
        sa.Column('start_time', sa.DateTime()),
        sa.Column('end_time', sa.DateTime()),
    )
    op.create_table(
        'current_clocks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('task_id', sa.Integer(), sa.ForeignKey('tasks.id')),
        sa.Column('start_time', sa.DateTime()),
    )
    op.create_table(
        'goals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tasks_id', sa.Integer(), sa.ForeignKey('tasks.id')),
        sa.Column('name', sa.String()),
        sa.Column('target_hours', sa.Integer()),
        sa.Column('by_date', sa.DateTime()),
    )


def downgrade() -> None:
    op.drop_table('goals')
    op.drop_table('current_clocks')
    op.drop_table('historic_clocks')
    op.drop_table('categories')
    op.drop_table('tasks')
