"""Add durable bounded Monitor technical-decomposition cache.

Revision ID: 0019_monitor_technical_decomposition
Revises: 0018_action_context_concurrency
"""
import sqlalchemy as sa

from alembic import op

revision = "0019_monitor_technical_decomposition"
down_revision = "0018_action_context_concurrency"
branch_labels = None
depends_on = None

def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("monitor_technical_decompositions"):
        op.create_table("monitor_technical_decompositions",
            sa.Column("event_id", sa.String(160), primary_key=True), sa.Column("governed_content_hash", sa.String(64), nullable=False),
            sa.Column("projection", sa.Text()), sa.Column("provider", sa.String(64)), sa.Column("model", sa.String(120)),
            sa.Column("status", sa.String(32), nullable=False), sa.Column("attempt_count", sa.Integer(), nullable=False),
            sa.Column("next_retry_at", sa.DateTime(timezone=True)), sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False))

def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("monitor_technical_decompositions"):
        op.drop_table("monitor_technical_decompositions")
