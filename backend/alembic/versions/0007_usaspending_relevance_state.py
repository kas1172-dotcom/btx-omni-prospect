"""persist seller relevance state for source-specific Monitor policy

Revision ID: 0007_usaspending_relevance_state
Revises: 0006_monitor_durable_events
"""
from sqlalchemy import Column, String, inspect

from alembic import op

revision = "0007_usaspending_relevance_state"
down_revision = "0006_monitor_durable_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("monitor_events")}
    if "seller_relevance_state" not in columns:
        op.add_column("monitor_events", Column("seller_relevance_state", String(48), nullable=False, server_default="UNRESOLVED"))


def downgrade() -> None:
    # The 0006 table definition may already contain this column on a clean install.
    pass
