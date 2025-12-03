"""add poll trend fields

Revision ID: 0002_trend_fields
Revises: 0001_initial
Create Date: 2025-12-02 19:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002_trend_fields'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade():
    """Add trend tracking fields to polls table."""
    # Add new columns for trend tracking
    op.add_column('polls', sa.Column('previous_place', sa.Integer, nullable=True))
    op.add_column('polls', sa.Column('place_trend', sa.String(10), nullable=True))
    op.add_column('polls', sa.Column('votes_ahead_second', sa.Integer, nullable=True))


def downgrade():
    """Remove trend tracking fields from polls table."""
    op.drop_column('polls', 'votes_ahead_second')
    op.drop_column('polls', 'place_trend')
    op.drop_column('polls', 'previous_place')
