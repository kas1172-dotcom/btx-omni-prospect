"""persist normalized Monitor events, versions, and rejected observations

Revision ID: 0006_monitor_durable_events
Revises: 0005_monitor_live
"""
from sqlalchemy import Column, Text

from alembic import op
from btx_omni.persistence.models import (
    monitor_events,
    monitor_rejected_observations,
    monitor_source_versions,
)

revision = "0006_monitor_durable_events"
down_revision = "0005_monitor_live"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    op.add_column("monitor_observations", Column("title", Text))
    op.add_column("monitor_observations", Column("structured_payload", Text))
    monitor_source_versions.create(bind)
    monitor_events.create(bind)
    monitor_rejected_observations.create(bind)


def downgrade() -> None:
    bind = op.get_bind()
    monitor_rejected_observations.drop(bind)
    monitor_events.drop(bind)
    monitor_source_versions.drop(bind)
    op.drop_column("monitor_observations", "structured_payload")
    op.drop_column("monitor_observations", "title")
