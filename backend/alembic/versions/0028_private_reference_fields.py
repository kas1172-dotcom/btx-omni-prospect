"""Version private source fields separately from public identity and official scores."""
import sqlalchemy as sa

from alembic import op

revision = '0028_private_reference_fields'
down_revision = '0027_memory_create_receipts'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('reference_field_versions',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('row_key', sa.String(220), nullable=False),
        sa.Column('account_id', sa.String(64), nullable=False),
        sa.Column('payload', sa.Text(), nullable=False),
        sa.Column('imported_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_reference_field_versions_row_key', 'reference_field_versions', ['row_key'])
    op.create_index('ix_reference_field_versions_account_id', 'reference_field_versions', ['account_id'])
    op.create_table('reference_field_current',
        sa.Column('row_key', sa.String(220), primary_key=True),
        sa.Column('version_id', sa.String(64), sa.ForeignKey('reference_field_versions.id'), nullable=False, unique=True))
    op.create_table('reference_field_import_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('report', sa.Text(), nullable=False))


def downgrade():
    raise RuntimeError('Keep immutable source versions; use compatible code rollback or a reviewed backup restore.')
