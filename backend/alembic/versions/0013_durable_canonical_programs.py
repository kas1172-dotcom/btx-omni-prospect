"""Add durable canonical Program foundation."""

from alembic import op
from btx_omni.persistence.models import durable_canonical_programs

revision = "0013_durable_canonical_programs"
down_revision = "0012_candidate_promotion_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    durable_canonical_programs.create(op.get_bind())


def downgrade() -> None:
    durable_canonical_programs.drop(op.get_bind())
