"""Bounded private create receipts prevent duplicate or resurrected preferences."""
import sqlalchemy as sa

from alembic import op

revision = '0027_memory_create_receipts'
down_revision = '0026_market_series'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'omni_memory_create_requests',
        sa.Column('user_id', sa.String(128), primary_key=True),
        sa.Column('key_hash', sa.String(64), primary_key=True),
        sa.Column('request_hash', sa.String(64), nullable=False),
        sa.Column('memory_id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    raise RuntimeError('Preserve create receipts to prevent resurrection; use compatible code rollback or a reviewed backup restore.')
