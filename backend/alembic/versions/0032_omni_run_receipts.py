"""Private bounded Omni run receipts with immutable completion."""
import sqlalchemy as sa

from alembic import op

revision = '0032_omni_run_receipts'
down_revision = '0031_communication_versions'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('omni_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('actor_id', sa.String(128), nullable=False),
        sa.Column('request_hash', sa.String(64), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('result_hash', sa.String(64)), sa.Column('result', sa.Text()))
    op.create_index('ix_omni_runs_actor_started', 'omni_runs', ['actor_id', 'started_at'])


def downgrade():
    raise RuntimeError('Retain private run evidence; use compatible rollback or reviewed backup restore.')
