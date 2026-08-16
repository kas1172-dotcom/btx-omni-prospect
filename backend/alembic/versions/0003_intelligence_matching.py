"""add intelligence and commercial matching read models

Revision ID: 0003_intelligence
Revises: 0002_decisioning
"""
from alembic import op
from btx_omni.persistence.models import commercial_matches, intelligence_signals

revision = "0003_intelligence"
down_revision = "0002_decisioning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    intelligence_signals.create(op.get_bind())
    commercial_matches.create(op.get_bind())


def downgrade() -> None:
    commercial_matches.drop(op.get_bind())
    intelligence_signals.drop(op.get_bind())
