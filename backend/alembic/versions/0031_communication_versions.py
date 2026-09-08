"""Prevent stale edits/reviews from overwriting communication content."""
import sqlalchemy as sa

from alembic import op

revision = '0031_communication_versions'
down_revision = '0030_ai_call_receipts'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('communication_drafts', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))


def downgrade():
    raise RuntimeError('Retain communication concurrency state; use compatible rollback or reviewed restore.')
