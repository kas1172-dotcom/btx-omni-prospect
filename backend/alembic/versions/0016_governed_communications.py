"""Add durable governed communications and personal preferences.

Revision ID: 0016_governed_communications
Revises: 0015_durable_authorized_actions
"""

import sqlalchemy as sa

from alembic import op

revision = "0016_governed_communications"
down_revision = "0015_durable_authorized_actions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "communication_drafts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.String(64), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("subject", sa.String(300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("recipients", sa.Text(), nullable=False),
        sa.Column("trigger", sa.String(120)),
        sa.Column("evidence_ids", sa.Text(), nullable=False),
        sa.Column("approval_status", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("idempotency_key", sa.String(128), nullable=False, unique=True),
    )
    op.create_table(
        "communication_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("communication_id", sa.String(64), sa.ForeignKey("communication_drafts.id"), nullable=False),
        sa.Column("actor_id", sa.String(128), nullable=False),
        sa.Column("event", sa.String(48), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", sa.Text(), nullable=False),
    )
    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.String(128), primary_key=True),
        sa.Column("compact_density", sa.Boolean(), nullable=False),
        sa.Column("omni_evidence_expanded", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("user_preferences")
    op.drop_table("communication_audit_events")
    op.drop_table("communication_drafts")
