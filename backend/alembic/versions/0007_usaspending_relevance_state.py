"""persist seller relevance state for source-specific Monitor policy

Revision ID: 0007_usaspending_relevance_state
Revises: 0006_monitor_durable_events
"""
from sqlalchemy import Column, String

from alembic import op

revision = "0007_usaspending_relevance_state"
down_revision = "0006_monitor_durable_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("monitor_events", Column("seller_relevance_state", String(48), nullable=False, server_default="UNRESOLVED"))


def downgrade() -> None:
    op.drop_column("monitor_events", "seller_relevance_state")
