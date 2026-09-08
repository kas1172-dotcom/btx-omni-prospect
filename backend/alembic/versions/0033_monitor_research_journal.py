"""Fenced, bounded research runs in the existing Monitor persistence owner."""
import sqlalchemy as sa

from alembic import op

revision = '0033_monitor_research_journal'
down_revision = '0032_omni_run_receipts'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('monitor_research_runs',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('event_reference', sa.String(200), nullable=False),
        sa.Column('source_revision', sa.String(64), nullable=False),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('lease_token', sa.String(36)), sa.Column('lease_until', sa.DateTime(timezone=True)),
        sa.Column('completed_steps', sa.Integer(), nullable=False),
        sa.Column('attempt_count', sa.Integer(), nullable=False), sa.Column('result', sa.Text()))
    op.create_table('monitor_research_steps',
        sa.Column('run_id', sa.String(64), sa.ForeignKey('monitor_research_runs.id'), primary_key=True),
        sa.Column('number', sa.Integer(), primary_key=True),
        sa.Column('tool', sa.String(80), nullable=False),
        sa.Column('arguments_hash', sa.String(64), nullable=False),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True)), sa.Column('result', sa.Text()))


def downgrade():
    raise RuntimeError('Retain research evidence; use a compatible release or reviewed backup restore.')
