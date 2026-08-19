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
    columns = {column["name"]: column for column in inspect(bind).get_columns("monitor_events")}
    existing = columns.get("seller_relevance_state")
    if existing is not None:
        default = str(existing.get("default") or "")
        if (
            not isinstance(existing["type"], String)
            or existing["type"].length != 48
            or existing["nullable"]
            or "UNRESOLVED" not in default.upper()
        ):
            raise RuntimeError(
                "monitor_events.seller_relevance_state exists but is not the VARCHAR(48) "
                "NOT NULL column with UNRESOLVED default required by revision 0007"
            )
    if "seller_relevance_state" not in columns:
        op.add_column("monitor_events", Column("seller_relevance_state", String(48), nullable=False, server_default="UNRESOLVED"))


def downgrade() -> None:
    # The 0006 table definition may already contain this column on a clean install.
    pass
