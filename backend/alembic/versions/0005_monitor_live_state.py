"""add Monitor 2.0 collection and clustering state

Revision ID: 0005_monitor_live
Revises: 0004_workflow
"""
from alembic import op

from btx_omni.persistence.models import (
    monitor_collection_runs,
    monitor_event_clusters,
    monitor_observations,
    monitor_source_health,
)

revision = "0005_monitor_live"
down_revision = "0004_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    monitor_observations.create(bind)
    monitor_collection_runs.create(bind)
    monitor_source_health.create(bind)
    monitor_event_clusters.create(bind)


def downgrade() -> None:
    bind = op.get_bind()
    monitor_event_clusters.drop(bind)
    monitor_source_health.drop(bind)
    monitor_collection_runs.drop(bind)
    monitor_observations.drop(bind)
