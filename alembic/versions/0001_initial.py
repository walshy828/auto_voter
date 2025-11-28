"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2025-11-26 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'polls',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('entryname', sa.String(255), nullable=False),
        sa.Column('pollid', sa.String(64), nullable=False),
        sa.Column('answerid', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=True),
    )

    op.create_table(
        'worker_processes',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('pid', sa.Integer, nullable=True),
        sa.Column('item_id', sa.Integer, nullable=False),
        sa.Column('log_path', sa.String(1024), nullable=True),
        sa.Column('start_time', sa.DateTime, nullable=True),
        sa.Column('end_time', sa.DateTime, nullable=True),
        sa.Column('exit_code', sa.Integer, nullable=True),
        sa.Column('result_msg', sa.Text, nullable=True),
    )

    op.create_table(
        'queue_items',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('poll_id', sa.Integer, nullable=True),
        sa.Column('pollid', sa.String(64), nullable=False),
        sa.Column('answerid', sa.String(64), nullable=False),
        sa.Column('votes', sa.Integer, nullable=True),
        sa.Column('threads', sa.Integer, nullable=True),
        sa.Column('per_run', sa.Integer, nullable=True),
        sa.Column('pause', sa.Integer, nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('pid', sa.Integer, nullable=True),
        sa.Column('exit_code', sa.Integer, nullable=True),
        sa.Column('worker_id', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('started_at', sa.DateTime, nullable=True),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('result_msg', sa.Text, nullable=True),
    )


def downgrade():
    op.drop_table('queue_items')
    op.drop_table('worker_processes')
    op.drop_table('polls')
