"""Audited strategic-partnership designations and private seller shortlists."""
import sqlalchemy as sa

from alembic import op

revision = "0035_account_planning"
down_revision = "0034_seller_itineraries"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "account_partnership_designations",
        sa.Column("account_id", sa.String(100), primary_key=True),
        sa.Column("designated", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.String(128), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
    )
    op.create_table(
        "account_partnership_audit",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("account_id", sa.String(100), nullable=False),
        sa.Column("designated", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.String(128), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False, unique=True),
        sa.Column("payload_hash", sa.String(64), nullable=False),
    )
    op.create_table(
        "seller_shortlist_items",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("account_id", sa.String(100), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("target_date", sa.String(10)),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "account_id", name="uq_seller_shortlist_user_account"),
    )


def downgrade():
    raise RuntimeError("Retain account planning audit; restore a compatible reviewed backup instead.")
