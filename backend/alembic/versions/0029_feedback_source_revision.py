"""Keep the reviewed recommendation version with private feedback."""
import sqlalchemy as sa

from alembic import op

revision = '0029_feedback_source_revision'
down_revision = '0028_private_reference_fields'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('work_suggestion_feedback', sa.Column('source_revision', sa.String(64), nullable=True))


def downgrade():
    raise RuntimeError('Retain reviewed source-version history; use compatible code or a reviewed backup restore.')
