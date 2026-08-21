"""Add durable Organization Candidate promotion result/audit state."""

from alembic import op
from btx_omni.persistence.models import monitor_candidate_promotion_audits

revision = "0012_candidate_promotion_audit"
down_revision = "0011_durable_public_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    monitor_candidate_promotion_audits.create(op.get_bind())


def downgrade() -> None:
    monitor_candidate_promotion_audits.drop(op.get_bind())
