"""Durable bounded model-call reservations; no prompts or private reasoning."""
import sqlalchemy as sa

from alembic import op

revision = '0030_ai_call_receipts'
down_revision = '0029_feedback_source_revision'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('ai_call_receipts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('environment_id', sa.String(80), nullable=False),
        sa.Column('actor_id', sa.String(128), nullable=False),
        sa.Column('purpose', sa.String(40), nullable=False),
        sa.Column('provider', sa.String(32), nullable=False),
        sa.Column('model', sa.String(128), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('policy', sa.Text(), nullable=False),
        sa.Column('usage', sa.Text()))
    op.create_index('ix_ai_calls_environment_started', 'ai_call_receipts', ['environment_id', 'started_at'])
    op.create_index('ix_ai_calls_actor_started', 'ai_call_receipts', ['environment_id', 'actor_id', 'started_at'])
    op.create_index('ix_ai_calls_active_lease', 'ai_call_receipts', ['environment_id', 'status', 'lease_expires_at'])


def downgrade():
    raise RuntimeError('Retain usage audit and budget reservations; use compatible code rollback or a reviewed backup restore.')
