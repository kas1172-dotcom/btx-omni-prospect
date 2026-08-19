"""persist normalized Monitor events, versions, and rejected observations

Revision ID: 0006_monitor_durable_events
Revises: 0005_monitor_live
"""
from sqlalchemy import Column, Text, inspect

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
    # 0005 creates its table from the shared model definition.  On a clean
    # install that definition can already contain these additive fields, while
    # an older upgraded database may not.  Add only missing columns so both
    # histories converge without duplicate-column failures.
    existing_columns = {column["name"]: column for column in inspect(bind).get_columns("monitor_observations")}
    for name in ("title", "structured_payload"):
        existing = existing_columns.get(name)
        if existing is not None and (not isinstance(existing["type"], Text) or not existing["nullable"]):
            raise RuntimeError(f"monitor_observations.{name} exists but is not the nullable TEXT column required by revision 0006")
    if "title" not in existing_columns:
        op.add_column("monitor_observations", Column("title", Text))
    if "structured_payload" not in existing_columns:
        op.add_column("monitor_observations", Column("structured_payload", Text))
    monitor_source_versions.create(bind)
    monitor_events.create(bind)
    monitor_rejected_observations.create(bind)


def downgrade() -> None:
    bind = op.get_bind()
    monitor_rejected_observations.drop(bind)
    monitor_events.drop(bind)
    monitor_source_versions.drop(bind)
    # These columns may originate from the table definition used by 0005, so
    # retain them when returning to that revision.
