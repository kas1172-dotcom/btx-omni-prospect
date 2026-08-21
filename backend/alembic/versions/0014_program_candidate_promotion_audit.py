"""Add durable Program Candidate promotion audit state."""

from alembic import op
from btx_omni.persistence.models import monitor_program_candidate_promotion_audits

revision = "0014_program_candidate_promotion_audit"
down_revision = "0013_durable_canonical_programs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    monitor_program_candidate_promotion_audits.create(op.get_bind())


def downgrade() -> None:
    monitor_program_candidate_promotion_audits.drop(op.get_bind())
