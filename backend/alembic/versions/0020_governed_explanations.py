"""Add durable governed explanation projections.

Revision ID: 0020_governed_explanations
Revises: 0019_monitor_technical_decomposition
"""
import sqlalchemy as sa

from alembic import op

revision = "0020_governed_explanations"
down_revision = "0019_monitor_technical_decomposition"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("governed_explanations", sa.Column("subject_key", sa.String(200), primary_key=True), sa.Column("explanation_type", sa.String(64), primary_key=True), sa.Column("governed_content_hash", sa.String(64), nullable=False), sa.Column("projection", sa.Text(), nullable=False), sa.Column("provider", sa.String(64)), sa.Column("model", sa.String(120)), sa.Column("status", sa.String(32), nullable=False), sa.Column("attempt_count", sa.Integer(), nullable=False), sa.Column("next_retry_at", sa.DateTime(timezone=True)), sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False))

def downgrade() -> None:
    op.drop_table("governed_explanations")
