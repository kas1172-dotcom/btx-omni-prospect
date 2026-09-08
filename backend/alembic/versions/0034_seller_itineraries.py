"""Durable, principal-scoped seller itineraries in the existing work owner."""
import sqlalchemy as sa

from alembic import op

revision = "0034_seller_itineraries"
down_revision = "0033_monitor_research_journal"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "seller_itineraries",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False, unique=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    raise RuntimeError("Retain seller work; restore a compatible reviewed backup instead.")
