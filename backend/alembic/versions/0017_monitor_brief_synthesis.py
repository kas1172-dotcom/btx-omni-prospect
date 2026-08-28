"""Add bounded durable Monitor Signal Brief synthesis cache.

Revision ID: 0017_monitor_brief_synthesis
Revises: 0016_governed_communications
"""

import sqlalchemy as sa

from alembic import op

revision = "0017_monitor_brief_synthesis"
down_revision = "0016_governed_communications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "monitor_brief_syntheses",
        sa.Column("brief_id", sa.String(160), primary_key=True),
        sa.Column("governed_content_hash", sa.String(64), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("provider", sa.String(64)),
        sa.Column("model", sa.String(120)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True)),
        sa.Column("synthesized_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("monitor_brief_syntheses")
