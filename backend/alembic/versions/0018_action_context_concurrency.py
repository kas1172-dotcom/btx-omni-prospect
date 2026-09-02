"""Add bounded Action referents and optimistic concurrency.

Revision ID: 0018_action_context_concurrency
Revises: 0017_monitor_brief_synthesis
"""

import sqlalchemy as sa

from alembic import op

revision = "0018_action_context_concurrency"
down_revision = "0017_monitor_brief_synthesis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {
        item["name"] for item in sa.inspect(op.get_bind()).get_columns("work_items")
    }
    if "context_referents" not in columns:
        op.add_column(
            "work_items",
            sa.Column(
                "context_referents", sa.Text(), nullable=False, server_default="[]"
            ),
        )
    if "version" not in columns:
        op.add_column(
            "work_items",
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        )


def downgrade() -> None:
    columns = {
        item["name"] for item in sa.inspect(op.get_bind()).get_columns("work_items")
    }
    if "version" in columns:
        op.drop_column("work_items", "version")
    if "context_referents" in columns:
        op.drop_column("work_items", "context_referents")
