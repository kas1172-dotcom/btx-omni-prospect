"""Persist bounded non-authoritative entity-candidate interpretations.

Revision ID: 0021_monitor_entity_candidate_resolutions
Revises: 0020_governed_explanations
"""
import sqlalchemy as sa
from alembic import op

revision = "0021_monitor_entity_candidate_resolutions"
down_revision = "0020_governed_explanations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("monitor_entity_candidate_resolutions", sa.Column("cache_key", sa.String(64), primary_key=True), sa.Column("projection", sa.Text(), nullable=False), sa.Column("provider", sa.String(64)), sa.Column("model", sa.String(120)), sa.Column("status", sa.String(32), nullable=False), sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False))


def downgrade() -> None:
    op.drop_table("monitor_entity_candidate_resolutions")
